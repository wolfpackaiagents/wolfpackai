"""Approvals API: list and resolve human-in-the-loop requirements (HITL).

Two entry points:
  - `POST /api/public/approvals`           create a pending approval (from the SDK).
  - `GET  /api/public/approvals?status=...` list approvals for the project.
  - `POST /api/public/approvals/{id}/resolve` resolve an approval (approve/reject/
    user_input/feedback/external_result).

Resolution is centrally audited: `resolved_at`, `resolved_by` and the final status
are stored together with the trace, forming the compliance/audit trail.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.auth import AuthContext, require_role
from ..core.database import get_db
from ..models.entities import Approval, Environment, EnvironmentRegistration, MeshDefinition, Trace
from pydantic import BaseModel

router = APIRouter(prefix="/api/public/approvals")

VALID_ACTIONS = {"approve", "reject", "user_input", "feedback", "external_result"}
VALID_STATUSES = {"pending", "approved", "rejected", "resolved", "unauthorized"}


class ApprovalCreate(BaseModel):
    run_id: str
    approval_id: str
    tool_name: str
    tool_arguments: dict = {}
    requirement: str = "confirmation"
    tool_call_id: str = ""
    metadata: dict = {}


class ApprovalResolve(BaseModel):
    action: str
    note: Optional[str] = None
    values: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    resolved_by: Optional[str] = None


def _trace_context(db: Session, project_id: str, trace_id: str | None) -> dict[str, Any] | None:
    if not trace_id:
        return None
    trace = db.query(Trace).filter(Trace.id == trace_id, Trace.project_id == project_id).first()
    if not trace:
        return None
    environment = db.query(Environment).filter(Environment.id == trace.environment_id, Environment.project_id == project_id).first()
    registration = db.query(EnvironmentRegistration).filter(EnvironmentRegistration.id == trace.registration_id, EnvironmentRegistration.project_id == project_id).first()
    definition = db.query(MeshDefinition).filter(MeshDefinition.id == trace.definition_id, MeshDefinition.project_id == project_id).first()
    if registration and (not environment or registration.environment_id != environment.id):
        registration = None
    if definition and (not registration or definition.id != registration.definition_id):
        definition = None
    return {
        "trace": {"id": trace.id, "name": trace.name},
        "session_id": trace.session_id,
        "environment": {"id": environment.id, "slug": environment.slug, "name": environment.name} if environment else None,
        "registration": {"id": registration.id} if registration else None,
        "definition": {"id": definition.id, "key": definition.key, "name": definition.name, "version": definition.version} if definition else None,
    }


def _to_dict(a: Approval, db: Session, project_id: str) -> Dict[str, Any]:
    return {
        "id": a.id,
        "approval_id": a.approval_id,
        "trace_id": a.trace_id,
        "trace_context": _trace_context(db, project_id, a.trace_id),
        "tool_name": a.tool_name,
        "tool_arguments": a.tool_arguments,
        "requirement": a.requirement,
        "tool_call_id": a.tool_call_id,
        "status": a.status,
        "confirmation": a.confirmation,
        "confirmation_note": a.confirmation_note,
        "user_input": a.user_input,
        "feedback": a.feedback,
        "external_execution_result": (a.metadata_field or {}).get("external_result"),
        "metadata": a.metadata_field,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
        "resolved_by": a.resolved_by,
    }


@router.post("")
def create_approval(
    body: ApprovalCreate,
    auth: AuthContext = Depends(require_role("editor")),
):
    project_id, db = auth
    existing = (
        db.query(Approval)
        .filter(Approval.project_id == project_id, Approval.approval_id == body.approval_id)
        .first()
    )
    if existing:
        return _to_dict(existing, db, project_id)
    # ensure trace row exists for FK
    if body.run_id:
        trace = db.query(Trace).filter(Trace.id == body.run_id, Trace.project_id == project_id).first()
        if trace is None:
            if db.get(Trace, body.run_id) is not None:
                raise HTTPException(status_code=404, detail="Trace not found")
            db.add(Trace(id=body.run_id, project_id=project_id, name="paused-run"))
            db.flush()
    a = Approval(
        id=_mkid(),
        approval_id=body.approval_id,
        project_id=project_id,
        trace_id=body.run_id or None,
        tool_name=body.tool_name,
        tool_arguments=body.tool_arguments,
        requirement=body.requirement,
        tool_call_id=body.tool_call_id,
        status="pending",
        metadata_field=body.metadata,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return _to_dict(a, db, project_id)


@router.get("")
def list_approvals(
    status: Optional[str] = Query("pending"),
    limit: int = 50,
    environment_id: str | None = Query(default=None, max_length=32),
    registration_id: str | None = Query(default=None, max_length=32),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    auth: AuthContext = Depends(require_role("editor")),
):
    from ..models.entities import Trace
    project_id, db = auth
    q = db.query(Approval).filter(Approval.project_id == project_id)
    if status:
        q = q.filter(Approval.status == status)
    if environment_id or registration_id:
        q = q.join(Trace, Approval.trace_id == Trace.id, isouter=True)
        if environment_id:
            q = q.filter(Trace.environment_id == environment_id)
        if registration_id:
            q = q.filter(Trace.registration_id == registration_id)
    if from_:
        q = q.filter(Approval.created_at >= from_)
    if to:
        q = q.filter(Approval.created_at <= to)
    rows = q.order_by(Approval.created_at.desc()).limit(limit).all()
    return [_to_dict(a, db, project_id) for a in rows]


@router.get("/{approval_id}")
def get_approval(approval_id: str, auth: AuthContext = Depends(require_role("editor"))):
    project_id, db = auth
    a = (
        db.query(Approval)
        .filter(Approval.project_id == project_id)
        .filter(Approval.approval_id == approval_id)
        .first()
    )
    if not a:
        raise HTTPException(status_code=404, detail="Approval not found")
    return _to_dict(a, db, project_id)


@router.post("/{approval_id}/resolve")
def resolve_approval(
    approval_id: str,
    body: ApprovalResolve,
    auth: AuthContext = Depends(require_role("editor")),
):
    project_id, db = auth
    a = (
        db.query(Approval)
        .filter(Approval.project_id == project_id)
        .filter(Approval.approval_id == approval_id)
        .first()
    )
    if not a:
        raise HTTPException(status_code=404, detail="Approval not found")
    if a.status != "pending":
        raise HTTPException(status_code=409, detail=f"Approval already resolved as {a.status}")

    from datetime import datetime, timezone

    if body.action == "approve":
        a.confirmation = True
        a.status = "approved"
        try:
            from .schedules import apply_schedule_approval

            apply_schedule_approval(db, a)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
    elif body.action == "reject":
        a.confirmation = False
        a.status = "rejected"
        a.confirmation_note = body.note
    elif body.action == "user_input":
        a.user_input = body.values or {}
        a.status = "resolved"
    elif body.action == "feedback":
        a.feedback = body.values or {}
        a.status = "resolved"
    elif body.action == "external_result":
        a.status = "resolved"
        a.metadata_field = {**(a.metadata_field or {}), "external_result": body.result}
    else:
        raise HTTPException(status_code=422, detail=f"Unknown action {body.action}; use one of {VALID_ACTIONS}")

    a.resolved_at = datetime.now(timezone.utc)
    a.resolved_by = auth.api_key_id
    db.commit()
    db.refresh(a)
    return _to_dict(a, db, project_id)


def _mkid() -> str:
    import uuid

    return uuid.uuid4().hex
