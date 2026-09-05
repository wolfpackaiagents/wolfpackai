"""Governance endpoints for trace retention and export."""

from __future__ import annotations

import csv
import io
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ..core.auth import AuthContext, require_role, resolve_project_id
from ..core.config import get_settings
from ..models.entities import Observation, Project, Score, Trace
from ..services.retention import RetentionService
from .queries import _to_obs_dict, _to_score_dict, _trace_to_public

router = APIRouter(prefix="/api/public")


RoleName = Literal["read_only", "editor", "admin"]
PermissionName = Literal["read", "write", "manage"]

DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "read_only": ["read"],
    "editor": ["read", "write"],
    "admin": ["read", "write", "manage"],
}


class GovernanceSettings(BaseModel):
    retention_days: int = Field(ge=1)
    roles: dict[RoleName, list[PermissionName]] = Field(default_factory=lambda: DEFAULT_ROLE_PERMISSIONS.copy())

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, roles: dict[RoleName, list[PermissionName]]) -> dict[RoleName, list[PermissionName]]:
        if set(roles) != set(DEFAULT_ROLE_PERMISSIONS):
            raise ValueError("roles must define read_only, editor, and admin")
        if any(len(permissions) != len(set(permissions)) for permissions in roles.values()):
            raise ValueError("role permissions must not contain duplicates")
        return roles


def _export_trace(trace: Trace, db: Session) -> dict:
    public = _trace_to_public(trace).model_dump()
    public["observations"] = [
        _to_obs_dict(observation)
        for observation in db.query(Observation)
        .filter(Observation.project_id == trace.project_id, Observation.trace_id == trace.id)
        .order_by(Observation.start_time)
        .all()
    ]
    public["scores"] = [
        _to_score_dict(score)
        for score in db.query(Score).filter(Score.project_id == trace.project_id, Score.trace_id == trace.id).all()
    ]
    return public


@router.get("/traces/export")
def export_traces(
    format: str = Query("json", pattern="^(json|csv)$"),
    limit: int = Query(default=100, ge=1, le=get_settings().trace_export_max_records),
    auth: AuthContext = Depends(require_role("read_only")),
):
    project_id, db = auth
    traces = [
        _export_trace(trace, db)
        for trace in db.query(Trace)
        .filter(Trace.project_id == project_id)
        .order_by(Trace.timestamp.desc(), Trace.id.desc())
        .limit(limit)
        .all()
    ]
    if format == "json":
        return JSONResponse(traces, headers={"Content-Disposition": "attachment; filename=traces.json"})

    output = io.StringIO()
    fieldnames = ["id", "name", "timestamp", "start_time", "end_time", "session_id", "environment", "input", "output", "latency_ms", "usage", "cost", "cost_currency", "cost_source", "observations", "scores"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for trace in traces:
        writer.writerow({key: json.dumps(value) if isinstance(value, (dict, list)) else value for key, value in trace.items()})
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=traces.csv"})


@router.post("/traces/cleanup")
def cleanup_expired_traces(auth: AuthContext = Depends(require_role("admin"))):
    project_id, db = auth
    return {"deleted": RetentionService(db, project_id).cleanup_expired_traces()}


@router.get("/governance/settings", response_model=GovernanceSettings)
def get_governance_settings(auth: AuthContext = Depends(resolve_project_id)):
    project_id, db = auth
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return GovernanceSettings(
        retention_days=project.retention_days,
        roles=project.governance_roles or DEFAULT_ROLE_PERMISSIONS,
    )


@router.put("/governance/settings", response_model=GovernanceSettings)
def update_governance_settings(
    body: GovernanceSettings,
    auth: AuthContext = Depends(require_role("admin")),
):
    project_id, db = auth
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project.retention_days = body.retention_days
    project.governance_roles = body.roles
    db.commit()
    return body
