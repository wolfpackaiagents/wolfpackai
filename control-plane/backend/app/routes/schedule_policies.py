"""Project and registration capability policies for schedule operations."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from ..core.auth import AuthContext, require_role
from ..models.entities import EnvironmentRegistration, PolicyDecisionAudit, Project
from ..services.schedule_policy import SCHEDULE_ACTIONS, SchedulePolicyService, merge_policy, normalize_policy

router = APIRouter(prefix="/api/public/schedule-policies")


class PolicyRules(BaseModel):
    decisions: dict[str, Literal["allow", "deny", "require_approval"]] = Field(default_factory=dict)
    restrictions: dict[str, Any] = Field(default_factory=dict)

    @field_validator("decisions")
    @classmethod
    def validate_decisions(cls, decisions: dict[str, str]) -> dict[str, str]:
        if unknown := set(decisions) - SCHEDULE_ACTIONS:
            raise ValueError(f"unknown schedule actions: {sorted(unknown)}")
        return decisions

    @field_validator("restrictions")
    @classmethod
    def validate_restrictions(cls, restrictions: dict[str, Any]) -> dict[str, Any]:
        allowed = {"max_active_schedules", "allowed_types", "min_interval_seconds"}
        if unknown := set(restrictions) - allowed:
            raise ValueError(f"unknown schedule restrictions: {sorted(unknown)}")
        if "max_active_schedules" in restrictions and (not isinstance(restrictions["max_active_schedules"], int) or isinstance(restrictions["max_active_schedules"], bool) or restrictions["max_active_schedules"] < 0):
            raise ValueError("max_active_schedules must be a non-negative integer")
        if "min_interval_seconds" in restrictions and (not isinstance(restrictions["min_interval_seconds"], int) or isinstance(restrictions["min_interval_seconds"], bool) or restrictions["min_interval_seconds"] < 1):
            raise ValueError("min_interval_seconds must be a positive integer")
        if "allowed_types" in restrictions and (not isinstance(restrictions["allowed_types"], list) or not restrictions["allowed_types"] or not all(isinstance(value, str) and value for value in restrictions["allowed_types"])):
            raise ValueError("allowed_types must be a non-empty list of strings")
        return restrictions


class DecisionRequest(BaseModel):
    action: Literal["schedule.read", "schedule.create", "schedule.update", "schedule.cancel"]
    registration_id: str | None = None
    schedule_id: str | None = None
    schedule_type: str | None = None
    interval_seconds: int | None = Field(default=None, ge=1)
    active_schedule_count: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.get("/project")
def get_project_policy(auth: AuthContext = Depends(require_role("read_only"))):
    project = auth.db.get(Project, auth.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return normalize_policy(project.schedule_policy)


@router.put("/project")
def update_project_policy(body: PolicyRules, auth: AuthContext = Depends(require_role("admin"))):
    project = auth.db.get(Project, auth.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project.schedule_policy = body.model_dump()
    auth.db.commit()
    return normalize_policy(project.schedule_policy)


@router.get("/registrations/{registration_id}")
def get_registration_policy(registration_id: str, auth: AuthContext = Depends(require_role("read_only"))):
    registration = auth.db.query(EnvironmentRegistration).filter_by(id=registration_id, project_id=auth.project_id).first()
    if registration is None:
        raise HTTPException(status_code=404, detail="Registration not found")
    return registration.schedule_policy or {"decisions": {}, "restrictions": {}}


@router.put("/registrations/{registration_id}")
def update_registration_policy(registration_id: str, body: PolicyRules, auth: AuthContext = Depends(require_role("admin"))):
    registration = auth.db.query(EnvironmentRegistration).filter_by(id=registration_id, project_id=auth.project_id).first()
    if registration is None:
        raise HTTPException(status_code=404, detail="Registration not found")
    registration.schedule_policy = body.model_dump()
    auth.db.commit()
    return registration.schedule_policy


@router.post("/decisions")
def decide_schedule_capability(body: DecisionRequest, auth: AuthContext = Depends(require_role("editor"))):
    project = auth.db.get(Project, auth.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    registration = None
    if body.registration_id:
        registration = auth.db.query(EnvironmentRegistration).filter_by(id=body.registration_id, project_id=auth.project_id).first()
        if registration is None:
            raise HTTPException(status_code=404, detail="Registration not found")
    policy = merge_policy(project.schedule_policy, registration.schedule_policy if registration else None)
    outcome = SchedulePolicyService(auth.db, auth.project_id, auth.api_key_id).decide(
        action=body.action,
        policy=policy,
        registration_id=body.registration_id,
        schedule_type=body.schedule_type,
        interval_seconds=body.interval_seconds,
        active_schedule_count=body.active_schedule_count,
        schedule_id=body.schedule_id,
        metadata={"mutation": "decision_preview", **body.metadata},
    )
    return {"decision": outcome.decision, "reasons": outcome.reasons, "approval_id": outcome.approval_id, "policy": outcome.policy}


@router.get("/decisions")
def list_policy_decisions(
    registration_id: str | None = None,
    action: str | None = Query(default=None, pattern="^schedule\\.(read|create|update|cancel)$"),
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(require_role("read_only")),
):
    query = auth.db.query(PolicyDecisionAudit).filter(PolicyDecisionAudit.project_id == auth.project_id)
    if registration_id:
        query = query.filter(PolicyDecisionAudit.registration_id == registration_id)
    if action:
        query = query.filter(PolicyDecisionAudit.action == action)
    return [
        {
            "id": row.id,
            "registration_id": row.registration_id,
            "action": row.action,
            "decision": row.decision,
            "reasons": row.reasons,
            "request": row.request,
            "policy": row.policy,
            "approval_id": row.approval_id,
            "actor_api_key_id": row.actor_api_key_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in query.order_by(PolicyDecisionAudit.created_at.desc(), PolicyDecisionAudit.id.desc()).limit(limit).all()
    ]
