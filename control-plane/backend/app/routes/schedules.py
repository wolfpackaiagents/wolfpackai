"""Durable schedule configuration and queued task-run records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.auth import AuthContext, require_role
from ..core.config import get_settings
from ..core.database import get_db
from ..models.entities import EnvironmentRegistration, Project, Schedule, ScheduledTaskRun, Trace
from ..services.schedule_policy import SchedulePolicyService, merge_policy
from ..services.schedule_runtime import ScheduleRuntime, verify_schedule_callback
from ..services.schedule_observability import trace_id_for
from ..services.scheduling import as_utc, next_run_at, occurrence_key, timezone_for, validate_cron

router = APIRouter(prefix="/api/public/schedules", tags=["schedules"])


class ScheduleInput(BaseModel):
    registration_id: str
    name: str = Field(min_length=1, max_length=128)
    schedule_type: Literal["at", "interval", "cron"]
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    at: datetime | None = None
    interval_seconds: int | None = Field(default=None, ge=1)
    cron: str | None = Field(default=None, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    max_attempts: int = Field(default=1, ge=1, le=100)
    retry_delay_seconds: int = Field(default=60, ge=1, le=86_400)
    misfire_policy: Literal["skip", "fire_once"] = "skip"
    misfire_grace_seconds: int = Field(default=60, ge=0, le=86_400)

    @model_validator(mode="after")
    def validate_type_fields(self):
        timezone_for(self.timezone)
        if self.schedule_type == "at":
            if self.at is None:
                raise ValueError("at schedules require 'at'")
            as_utc(self.at)
        elif self.schedule_type == "interval" and self.interval_seconds is None:
            raise ValueError("interval schedules require 'interval_seconds'")
        elif self.schedule_type == "cron":
            if not self.cron:
                raise ValueError("cron schedules require 'cron'")
            validate_cron(self.cron)
        return self


class ScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    schedule_type: Literal["at", "interval", "cron"] | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    at: datetime | None = None
    interval_seconds: int | None = Field(default=None, ge=1)
    cron: str | None = Field(default=None, max_length=128)
    payload: dict[str, Any] | None = None
    max_attempts: int | None = Field(default=None, ge=1, le=100)
    retry_delay_seconds: int | None = Field(default=None, ge=1, le=86_400)
    misfire_policy: Literal["skip", "fire_once"] | None = None
    misfire_grace_seconds: int | None = Field(default=None, ge=0, le=86_400)


class RunNowInput(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=128)


class ClaimInput(BaseModel):
    worker_id: str = Field(min_length=1, max_length=128)
    limit: int = Field(default=1, ge=1, le=100)


class CompleteInput(BaseModel):
    fencing_token: int = Field(ge=1)
    result: dict[str, Any] = Field(default_factory=dict)


class FailInput(BaseModel):
    fencing_token: int = Field(ge=1)
    error: str = Field(min_length=1, max_length=4000)


class RenewLeaseInput(BaseModel):
    fencing_token: int = Field(ge=1)
    worker_id: str = Field(min_length=1, max_length=128)


def _schedule_out(schedule: Schedule) -> dict[str, Any]:
    return {"id": schedule.id, "registration_id": schedule.registration_id, "name": schedule.name, "schedule_type": schedule.schedule_type, "timezone": schedule.timezone, "at": schedule.at, "interval_seconds": schedule.interval_seconds, "cron": schedule.cron, "payload": schedule.payload or {}, "status": schedule.status, "next_run_at": schedule.next_run_at, "last_run_at": schedule.last_run_at, "retry": {"max_attempts": schedule.max_attempts, "delay_seconds": schedule.retry_delay_seconds}, "misfire": {"policy": schedule.misfire_policy, "grace_seconds": schedule.misfire_grace_seconds}, "created_at": schedule.created_at, "updated_at": schedule.updated_at, "paused_at": schedule.paused_at, "cancelled_at": schedule.cancelled_at}


def _run_out(run: ScheduledTaskRun, db: Session | None = None) -> dict[str, Any]:
    trace_id = trace_id_for(run)
    trace = db.query(Trace).filter_by(id=trace_id, project_id=run.project_id).first() if db and trace_id else None
    trace_context = {"id": trace.id, "name": trace.name or trace.id} if trace else None
    return {"id": run.id, "schedule_id": run.schedule_id, "registration_id": run.registration_id, "occurrence_key": run.occurrence_key, "trigger": run.trigger, "status": run.status, "scheduled_for": run.scheduled_for, "attempt": run.attempt, "max_attempts": run.max_attempts, "retry_at": run.retry_at, "started_at": run.started_at, "completed_at": run.completed_at, "lease_expires_at": run.lease_expires_at, "fencing_token": run.fencing_token, "claimed_by": run.claimed_by, "deadline_at": run.deadline_at, "error": run.error, "result": run.result, "trace_id": trace_id, "trace_context": trace_context, "payload": run.payload or {}, "created_at": run.created_at, "updated_at": run.updated_at}


def _enforce_policy(auth: AuthContext, registration: EnvironmentRegistration, action: str, schedule_type: str | None, interval_seconds: int | None, active_count: int, schedule_id: str | None, metadata: dict[str, Any]) -> dict[str, Any] | None:
    project = auth.db.get(Project, auth.project_id)
    outcome = SchedulePolicyService(auth.db, auth.project_id, auth.api_key_id).decide(
        action=action, policy=merge_policy(project.schedule_policy if project else None, registration.schedule_policy),
        registration_id=registration.id, schedule_type=schedule_type, interval_seconds=interval_seconds,
        active_schedule_count=active_count, schedule_id=schedule_id, metadata=metadata,
    )
    if outcome.decision == "deny":
        raise HTTPException(status_code=403, detail={"reasons": outcome.reasons})
    if outcome.decision == "require_approval":
        return {"decision": "require_approval", "approval_id": outcome.approval_id}
    return None


def _schedule_for_project(schedule_id: str, auth: AuthContext) -> Schedule:
    schedule = auth.db.query(Schedule).filter_by(id=schedule_id, project_id=auth.project_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


def _registration_for_project(registration_id: str, auth: AuthContext) -> EnvironmentRegistration:
    registration = auth.db.query(EnvironmentRegistration).filter_by(id=registration_id, project_id=auth.project_id).first()
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")
    return registration


def _next(schedule: Schedule) -> datetime | None:
    return next_run_at(schedule.schedule_type, datetime.now(timezone.utc), at=schedule.at, interval_seconds=schedule.interval_seconds, cron=schedule.cron, timezone_name=schedule.timezone)


def apply_schedule_approval(db: Session, approval) -> None:
    """Apply the immutable mutation captured when a schedule policy was evaluated."""
    mutation = (approval.metadata_field or {}).get("schedule_mutation") or {}
    if (approval.metadata_field or {}).get("source") != "schedule_policy" or mutation.get("mutation") == "decision_preview":
        return
    action, schedule_id, body = mutation.get("action"), mutation.get("schedule_id"), mutation.get("body") or {}
    if action == "schedule.create":
        validated = ScheduleInput(**body)
        if db.query(Schedule).filter_by(project_id=approval.project_id, name=validated.name).first():
            raise ValueError("Schedule name already exists")
        schedule = Schedule(project_id=approval.project_id, **validated.model_dump())
        schedule.at = as_utc(schedule.at) if schedule.at else None
        schedule.next_run_at = _next(schedule)
        db.add(schedule)
    else:
        schedule = db.query(Schedule).filter_by(id=schedule_id, project_id=approval.project_id).first()
        if not schedule:
            raise ValueError("Schedule not found")
        if action == "schedule.update" and mutation.get("mutation") == "pause":
            schedule.status, schedule.paused_at, schedule.next_run_at = "paused", datetime.now(timezone.utc), None
        elif action == "schedule.update" and mutation.get("mutation") == "resume":
            schedule.status, schedule.paused_at, schedule.next_run_at = "active", None, _next(schedule)
        elif action == "schedule.update" and mutation.get("mutation") == "run_now":
            key = occurrence_key("manual", datetime.now(timezone.utc), body["idempotency_key"])
            if not db.query(ScheduledTaskRun).filter_by(schedule_id=schedule.id, occurrence_key=key).first():
                db.add(ScheduledTaskRun(project_id=approval.project_id, schedule_id=schedule.id, registration_id=schedule.registration_id, occurrence_key=key, trigger="manual", status="pending", scheduled_for=datetime.now(timezone.utc), max_attempts=schedule.max_attempts, payload=schedule.payload or {}))
        elif action == "schedule.update":
            validated = ScheduleInput(**{
                "registration_id": schedule.registration_id,
                "name": body.get("name", schedule.name), "schedule_type": body.get("schedule_type", schedule.schedule_type),
                "timezone": body.get("timezone", schedule.timezone), "at": body.get("at", schedule.at),
                "interval_seconds": body.get("interval_seconds", schedule.interval_seconds), "cron": body.get("cron", schedule.cron),
                "payload": body.get("payload", schedule.payload), "max_attempts": body.get("max_attempts", schedule.max_attempts),
                "retry_delay_seconds": body.get("retry_delay_seconds", schedule.retry_delay_seconds), "misfire_policy": body.get("misfire_policy", schedule.misfire_policy),
                "misfire_grace_seconds": body.get("misfire_grace_seconds", schedule.misfire_grace_seconds),
            })
            for field, value in validated.model_dump().items():
                setattr(schedule, field, as_utc(value) if field == "at" and value else value)
            schedule.next_run_at = _next(schedule)
        elif action == "schedule.cancel":
            schedule.status, schedule.cancelled_at, schedule.next_run_at = "cancelled", datetime.now(timezone.utc), None


@router.get("")
def list_schedules(status_filter: Literal["active", "paused", "cancelled", "completed"] | None = Query(default=None, alias="status"), registration_id: str | None = None, auth: AuthContext = Depends(require_role("read_only"))):
    query = auth.db.query(Schedule).filter_by(project_id=auth.project_id)
    if status_filter:
        query = query.filter(Schedule.status == status_filter)
    if registration_id:
        query = query.filter(Schedule.registration_id == registration_id)
    return [_schedule_out(item) for item in query.order_by(Schedule.created_at.desc()).all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_schedule(body: ScheduleInput, auth: AuthContext = Depends(require_role("editor"))):
    registration = _registration_for_project(body.registration_id, auth)
    if not registration.enabled:
        raise HTTPException(status_code=409, detail="Registration is disabled")
    if auth.db.query(Schedule).filter_by(project_id=auth.project_id, name=body.name).first():
        raise HTTPException(status_code=409, detail="Schedule name already exists")
    pending = _enforce_policy(auth, registration, "schedule.create", body.schedule_type, body.interval_seconds, auth.db.query(Schedule).filter_by(project_id=auth.project_id, status="active").count(), None, {"mutation": "create", "body": body.model_dump(mode="json")})
    if pending:
        return pending
    values = body.model_dump()
    values["at"] = as_utc(values["at"]) if values["at"] else None
    schedule = Schedule(project_id=auth.project_id, **values)
    schedule.next_run_at = _next(schedule)
    auth.db.add(schedule)
    auth.db.commit()
    auth.db.refresh(schedule)
    return _schedule_out(schedule)


@router.get("/{schedule_id}")
def get_schedule(schedule_id: str, auth: AuthContext = Depends(require_role("read_only"))):
    return _schedule_out(_schedule_for_project(schedule_id, auth))


@router.patch("/{schedule_id}")
def update_schedule(schedule_id: str, body: ScheduleUpdate, auth: AuthContext = Depends(require_role("editor"))):
    schedule = _schedule_for_project(schedule_id, auth)
    if schedule.status == "cancelled":
        raise HTTPException(status_code=409, detail="Cancelled schedules cannot be updated")
    updates = body.model_dump(exclude_unset=True)
    candidate = {"registration_id": schedule.registration_id, "name": updates.get("name", schedule.name), "schedule_type": updates.get("schedule_type", schedule.schedule_type), "timezone": updates.get("timezone", schedule.timezone), "at": updates.get("at", schedule.at), "interval_seconds": updates.get("interval_seconds", schedule.interval_seconds), "cron": updates.get("cron", schedule.cron), "payload": updates.get("payload", schedule.payload), "max_attempts": updates.get("max_attempts", schedule.max_attempts), "retry_delay_seconds": updates.get("retry_delay_seconds", schedule.retry_delay_seconds), "misfire_policy": updates.get("misfire_policy", schedule.misfire_policy), "misfire_grace_seconds": updates.get("misfire_grace_seconds", schedule.misfire_grace_seconds)}
    try:
        validated = ScheduleInput(**candidate)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    registration = _registration_for_project(schedule.registration_id, auth)
    pending = _enforce_policy(auth, registration, "schedule.update", validated.schedule_type, validated.interval_seconds, auth.db.query(Schedule).filter(Schedule.project_id == auth.project_id, Schedule.status == "active", Schedule.id != schedule.id).count(), schedule.id, {"mutation": "update", "body": body.model_dump(mode="json", exclude_unset=True)})
    if pending:
        return pending
    for field, value in validated.model_dump().items():
        setattr(schedule, field, as_utc(value) if field == "at" and value else value)
    schedule.next_run_at = _next(schedule)
    auth.db.commit()
    auth.db.refresh(schedule)
    return _schedule_out(schedule)


@router.post("/{schedule_id}/pause")
def pause_schedule(schedule_id: str, auth: AuthContext = Depends(require_role("editor"))):
    schedule = _schedule_for_project(schedule_id, auth)
    if schedule.status != "active":
        raise HTTPException(status_code=409, detail="Only active schedules can be paused")
    pending = _enforce_policy(auth, _registration_for_project(schedule.registration_id, auth), "schedule.update", schedule.schedule_type, schedule.interval_seconds, 0, schedule.id, {"mutation": "pause"})
    if pending:
        return pending
    schedule.status, schedule.paused_at, schedule.next_run_at = "paused", datetime.now(timezone.utc), None
    auth.db.commit()
    auth.db.refresh(schedule)
    return _schedule_out(schedule)


@router.post("/{schedule_id}/resume")
def resume_schedule(schedule_id: str, auth: AuthContext = Depends(require_role("editor"))):
    schedule = _schedule_for_project(schedule_id, auth)
    if schedule.status != "paused":
        raise HTTPException(status_code=409, detail="Only paused schedules can be resumed")
    if not _registration_for_project(schedule.registration_id, auth).enabled:
        raise HTTPException(status_code=409, detail="Registration is disabled")
    pending = _enforce_policy(auth, _registration_for_project(schedule.registration_id, auth), "schedule.update", schedule.schedule_type, schedule.interval_seconds, auth.db.query(Schedule).filter(Schedule.project_id == auth.project_id, Schedule.status == "active").count(), schedule.id, {"mutation": "resume"})
    if pending:
        return pending
    schedule.status, schedule.paused_at, schedule.next_run_at = "active", None, _next(schedule)
    auth.db.commit()
    auth.db.refresh(schedule)
    return _schedule_out(schedule)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_schedule(schedule_id: str, auth: AuthContext = Depends(require_role("editor"))):
    schedule = _schedule_for_project(schedule_id, auth)
    pending = _enforce_policy(auth, _registration_for_project(schedule.registration_id, auth), "schedule.cancel", schedule.schedule_type, schedule.interval_seconds, 0, schedule.id, {"mutation": "cancel"})
    if pending:
        return pending
    if schedule.status != "cancelled":
        schedule.status, schedule.cancelled_at, schedule.next_run_at = "cancelled", datetime.now(timezone.utc), None
        auth.db.query(ScheduledTaskRun).filter(
            ScheduledTaskRun.schedule_id == schedule.id,
            ScheduledTaskRun.status.in_(["pending", "retrying"]),
        ).update({"status": "cancelled", "completed_at": datetime.now(timezone.utc)}, synchronize_session=False)
        auth.db.commit()


@router.post("/{schedule_id}/run-now", status_code=status.HTTP_201_CREATED)
def run_now(schedule_id: str, body: RunNowInput, auth: AuthContext = Depends(require_role("editor"))):
    schedule = _schedule_for_project(schedule_id, auth)
    if schedule.status != "active":
        raise HTTPException(status_code=409, detail="Only active schedules can run now")
    if not _registration_for_project(schedule.registration_id, auth).enabled:
        raise HTTPException(status_code=409, detail="Registration is disabled")
    pending = _enforce_policy(auth, _registration_for_project(schedule.registration_id, auth), "schedule.update", schedule.schedule_type, schedule.interval_seconds, 0, schedule.id, {"mutation": "run_now", "body": body.model_dump(mode="json")})
    if pending:
        return pending
    key = occurrence_key("manual", datetime.now(timezone.utc), body.idempotency_key)
    existing = auth.db.query(ScheduledTaskRun).filter_by(schedule_id=schedule.id, occurrence_key=key).first()
    if existing:
        return _run_out(existing)
    now = datetime.now(timezone.utc)
    run = ScheduledTaskRun(project_id=auth.project_id, schedule_id=schedule.id, registration_id=schedule.registration_id, occurrence_key=key, trigger="manual", status="pending", scheduled_for=now, max_attempts=schedule.max_attempts, payload=schedule.payload or {})
    auth.db.add(run)
    try:
        auth.db.commit()
    except IntegrityError:
        auth.db.rollback()
        return _run_out(auth.db.query(ScheduledTaskRun).filter_by(schedule_id=schedule.id, occurrence_key=key).one())
    auth.db.refresh(run)
    return _run_out(run)


@router.post("/runs/claim")
def claim_runs(body: ClaimInput, auth: AuthContext = Depends(require_role("editor"))):
    runs = ScheduleRuntime(auth.db).claim(body.worker_id, body.limit, project_id=auth.project_id)
    return [_run_out(run) for run in runs]


@router.post("/runs/{run_id}/complete")
def complete_run(run_id: str, body: CompleteInput, auth: AuthContext = Depends(require_role("editor"))):
    run = auth.db.get(ScheduledTaskRun, run_id)
    if not run or run.project_id != auth.project_id:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        return _run_out(ScheduleRuntime(auth.db).complete(run_id, body.fencing_token, body.result))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/runs/{run_id}/fail")
def fail_run(run_id: str, body: FailInput, auth: AuthContext = Depends(require_role("editor"))):
    run = auth.db.get(ScheduledTaskRun, run_id)
    if not run or run.project_id != auth.project_id:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        return _run_out(ScheduleRuntime(auth.db).fail(run_id, body.fencing_token, body.error))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/runs/{run_id}/renew")
def renew_run_lease(run_id: str, body: RenewLeaseInput, auth: AuthContext = Depends(require_role("editor"))):
    try:
        run = ScheduleRuntime(auth.db).renew_lease(run_id, body.fencing_token, body.worker_id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if not run or run.project_id != auth.project_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_out(run)


@router.post("/runs/{run_id}/callback/complete")
async def complete_run_callback(run_id: str, request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    if not verify_schedule_callback(get_settings().scheduler_callback_secret, body, request.headers.get("X-Wolfpack-Schedule-Signature")):
        raise HTTPException(status_code=401, detail="Invalid schedule callback signature")
    data = CompleteInput.model_validate_json(body)
    try:
        run = ScheduleRuntime(db).complete(run_id, data.fencing_token, data.result)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_out(run)


@router.post("/runs/{run_id}/callback/fail")
async def fail_run_callback(run_id: str, request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    if not verify_schedule_callback(get_settings().scheduler_callback_secret, body, request.headers.get("X-Wolfpack-Schedule-Signature")):
        raise HTTPException(status_code=401, detail="Invalid schedule callback signature")
    data = FailInput.model_validate_json(body)
    try:
        run = ScheduleRuntime(db).fail(run_id, data.fencing_token, data.error)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_out(run)


@router.post("/runs/{run_id}/callback/renew")
async def renew_run_callback(run_id: str, request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    if not verify_schedule_callback(get_settings().scheduler_callback_secret, body, request.headers.get("X-Wolfpack-Schedule-Signature")):
        raise HTTPException(status_code=401, detail="Invalid schedule callback signature")
    data = RenewLeaseInput.model_validate_json(body)
    try:
        run = ScheduleRuntime(db).renew_lease(run_id, data.fencing_token, data.worker_id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_out(run)


@router.get("/{schedule_id}/runs")
def list_runs(schedule_id: str, status_filter: Literal["pending", "running", "succeeded", "failed", "retrying", "cancelled", "missed", "deadline_exceeded"] | None = Query(default=None, alias="status"), limit: int = Query(default=100, ge=1, le=500), auth: AuthContext = Depends(require_role("read_only"))):
    schedule = _schedule_for_project(schedule_id, auth)
    query = auth.db.query(ScheduledTaskRun).filter_by(project_id=auth.project_id, schedule_id=schedule.id)
    if status_filter:
        query = query.filter(ScheduledTaskRun.status == status_filter)
    return [_run_out(run, auth.db) for run in query.order_by(ScheduledTaskRun.scheduled_for.desc(), ScheduledTaskRun.created_at.desc()).limit(limit).all()]
