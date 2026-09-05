"""Project-scoped privacy settings and LGPD data subject endpoints."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..core.auth import AuthContext, require_role
from ..models.entities import Approval, IngestionJob, Observation, PrivacyAuditLog, Project, Score, Trace
from ..services.privacy import add_privacy_audit_log, delete_subject_data, job_belongs_to_subject

router = APIRouter(prefix="/api/public")


class PiiRedactionConfig(BaseModel):
    enabled: bool = False
    redact_email: bool = True
    redact_phone: bool = True
    redact_cpf: bool = True
    redact_credit_card: bool = True
    custom_patterns: list[str] = Field(default_factory=list)

    @field_validator("custom_patterns")
    @classmethod
    def validate_custom_patterns(cls, patterns: list[str]) -> list[str]:
        for pattern in patterns:
            if not pattern.strip():
                raise ValueError("custom patterns cannot be empty")
            try:
                re.compile(pattern)
            except re.error as error:
                raise ValueError(f"invalid custom pattern: {error.msg}") from error
        return patterns


def _trace_data(trace: Trace, observations: list[Observation], scores: list[Score]) -> dict[str, Any]:
    return {
        "id": trace.id,
        "name": trace.name,
        "user_id": trace.user_id,
        "input": trace.input,
        "output": trace.output,
        "metadata": trace.metadata_field,
        "observations": [
            {"id": row.id, "trace_id": row.trace_id, "input": row.input, "output": row.output, "metadata": row.metadata_field}
            for row in observations
            if row.trace_id == trace.id
        ],
        "scores": [
            {"id": row.id, "trace_id": row.trace_id, "name": row.name, "value": row.value, "string_value": row.string_value}
            for row in scores
            if row.trace_id == trace.id
        ],
    }


@router.get("/privacy/config", response_model=PiiRedactionConfig)
def get_privacy_config(auth: AuthContext = Depends(require_role("admin"))):
    project_id, db = auth
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return PiiRedactionConfig(**(project.pii_redaction_config or {}))


@router.put("/privacy/config", response_model=PiiRedactionConfig)
def update_privacy_config(
    body: PiiRedactionConfig,
    auth: AuthContext = Depends(require_role("admin")),
):
    project_id, db = auth
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project.pii_redaction_config = body.model_dump()
    db.commit()
    return body


@router.get("/users/{user_id}/export")
def export_user_data(user_id: str, auth: AuthContext = Depends(require_role("admin"))):
    project_id, db = auth
    traces = db.query(Trace).filter(Trace.project_id == project_id, Trace.user_id == user_id).all()
    jobs = [
        {"id": job.id, "status": job.status, "payload": job.payload, "created_at": job.created_at.isoformat()}
        for job in db.query(IngestionJob).filter(IngestionJob.project_id == project_id).all()
        if job_belongs_to_subject(job, user_id)
    ]
    if not traces and not jobs:
        raise HTTPException(status_code=404, detail="User data not found")
    trace_ids = [trace.id for trace in traces]
    observations = db.query(Observation).filter(Observation.project_id == project_id, Observation.trace_id.in_(trace_ids)).all()
    scores = db.query(Score).filter(Score.project_id == project_id, Score.trace_id.in_(trace_ids)).all()
    approvals = db.query(Approval).filter(Approval.project_id == project_id, Approval.trace_id.in_(trace_ids)).all()
    result = {
        "user_id": user_id,
        "traces": [_trace_data(trace, observations, scores) for trace in traces],
        "observations": [{"id": row.id, "trace_id": row.trace_id} for row in observations],
        "scores": [{"id": row.id, "trace_id": row.trace_id, "name": row.name, "value": row.value} for row in scores],
        "approvals": [{"id": row.id, "approval_id": row.approval_id, "trace_id": row.trace_id, "status": row.status} for row in approvals],
        "jobs": jobs,
    }
    add_privacy_audit_log(db, project_id, user_id, "export", {"trace_count": len(traces), "job_count": len(jobs)})
    db.commit()
    return result


@router.delete("/users/{user_id}")
def delete_user_data(user_id: str, auth: AuthContext = Depends(require_role("admin"))):
    project_id, db = auth
    deleted = delete_subject_data(db, project_id, user_id)
    if not any(deleted.values()):
        raise HTTPException(status_code=404, detail="User data not found")
    add_privacy_audit_log(db, project_id, user_id, "delete", deleted)
    db.commit()
    return {"deleted": deleted}


@router.get("/privacy/audit")
def list_privacy_audit_log(auth: AuthContext = Depends(require_role("admin"))):
    project_id, db = auth
    records = (
        db.query(PrivacyAuditLog)
        .filter(PrivacyAuditLog.project_id == project_id)
        .order_by(PrivacyAuditLog.created_at.desc())
        .all()
    )
    return [
        {"id": record.id, "action": record.action, "subject_hash": record.subject_hash, "details": record.details, "created_at": record.created_at.isoformat()}
        for record in records
    ]
