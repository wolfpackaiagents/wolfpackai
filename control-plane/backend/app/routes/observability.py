"""Project-scoped operational metrics and privacy-safe alert APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.auth import AuthContext, require_role
from ..models.entities import Alert, AlertDestination, AlertRule, IngestionJob, Project
from ..services.alert_notifier import notify as notify_destinations
from ..services.privacy import redact_ingestion_payload
from ..services.alerts import matching_alert_severity
from ..services.alert_taxonomy import ALERT_EVENT_TAXONOMY, is_valid_alert_rule_match

router = APIRouter(prefix="/api/public")


class FrameworkAlertCreate(BaseModel):
    """Safe framework signal; do not include prompt, tool arguments, or user content."""

    source: Literal["guardrail", "hitl"]
    event_type: str = Field(min_length=1, max_length=64)
    severity: Literal["info", "warning", "error"] = "warning"
    message: str = Field(min_length=1, max_length=500)
    trace_id: str | None = Field(default=None, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AlertRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    source: str | None = Field(default=None, min_length=1, max_length=32)
    event_type: str | None = Field(default=None, min_length=1, max_length=64)
    severity: Literal["info", "warning", "error"] = "warning"
    enabled: bool = True


class AlertRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    source: str | None = Field(default=None, min_length=1, max_length=32)
    event_type: str | None = Field(default=None, min_length=1, max_length=64)
    severity: Literal["info", "warning", "error"] | None = None
    enabled: bool | None = None


class AlertLifecycleUpdate(BaseModel):
    status: Literal["acknowledged", "resolved"]
    resolved_by: str | None = Field(default=None, max_length=128)


def _alert_to_dict(alert: Alert) -> dict[str, Any]:
    return {
        "id": alert.id,
        "ingestion_job_id": alert.ingestion_job_id,
        "trace_id": alert.trace_id,
        "source": alert.source,
        "event_type": alert.event_type,
        "severity": alert.severity,
        "message": alert.message,
        "metadata": alert.metadata_field,
        "status": alert.status,
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "resolved_by": alert.resolved_by,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }


def _alert_rule_to_dict(rule: AlertRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "name": rule.name,
        "source": rule.source,
        "event_type": rule.event_type,
        "severity": rule.severity,
        "enabled": rule.enabled,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


def _validate_alert_rule_match(source: str | None, event_type: str | None) -> None:
    if not is_valid_alert_rule_match(source, event_type):
        raise HTTPException(status_code=422, detail="Unsupported alert rule source/event_type combination")


@router.get("/observability/ingestion-metrics")
def ingestion_metrics(auth: AuthContext = Depends(require_role("read_only"))):
    """Return aggregate queue health without exposing payloads, errors, or job IDs."""
    project_id, db = auth
    jobs = db.query(IngestionJob).filter(IngestionJob.project_id == project_id).all()
    counts = {name: 0 for name in ("pending", "processing", "completed", "failed")}
    latencies = []
    retries = 0
    for job in jobs:
        if job.status in counts:
            counts[job.status] += 1
        retries += max(job.attempts - 1, 0)
        if job.completed_at and job.created_at:
            latencies.append((job.completed_at - job.created_at).total_seconds() * 1000)
    latencies.sort()

    def percentile(percent: float) -> float | None:
        if not latencies:
            return None
        return latencies[round((len(latencies) - 1) * percent)]

    return {
        **counts,
        "retries": retries,
        "latency_ms": {
            "average": sum(latencies) / len(latencies) if latencies else None,
            "p50": percentile(0.50),
            "p95": percentile(0.95),
        },
    }


@router.get("/alerts")
def list_alerts(
    source: str | None = Query(default=None, max_length=32),
    alert_status: Literal["open", "acknowledged", "resolved"] | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    environment_id: str | None = Query(default=None, max_length=32),
    registration_id: str | None = Query(default=None, max_length=32),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    auth: AuthContext = Depends(require_role("read_only")),
):
    """List alerts for the authenticated project with optional scope filters."""
    from ..models.entities import Trace
    project_id, db = auth
    query = db.query(Alert).filter(Alert.project_id == project_id)
    if source:
        query = query.filter(Alert.source == source)
    if alert_status:
        query = query.filter(Alert.status == alert_status)
    if environment_id or registration_id:
        query = query.join(Trace, Alert.trace_id == Trace.id, isouter=True)
        if environment_id:
            query = query.filter(Trace.environment_id == environment_id)
        if registration_id:
            query = query.filter(Trace.registration_id == registration_id)
    if from_:
        query = query.filter(Alert.created_at >= from_)
    if to:
        query = query.filter(Alert.created_at <= to)
    return [_alert_to_dict(alert) for alert in query.order_by(Alert.created_at.desc()).limit(limit).all()]


@router.post("/alerts", status_code=status.HTTP_201_CREATED)
def create_framework_alert(
    body: FrameworkAlertCreate,
    auth: AuthContext = Depends(require_role("editor")),
):
    """Persist a guardrail or HITL signal after applying project PII redaction."""
    project_id, db = auth
    project = db.get(Project, project_id)
    sanitized = redact_ingestion_payload(
        {"message": body.message, "metadata": body.metadata},
        project.pii_redaction_config if project else None,
    )
    alert = Alert(
        project_id=project_id,
        trace_id=body.trace_id,
        source=body.source,
        event_type=body.event_type,
        severity=matching_alert_severity(db, project_id, body.source, body.event_type) or body.severity,
        message=sanitized["message"],
        metadata_field=sanitized["metadata"],
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    destinations = db.query(AlertDestination).filter(
        AlertDestination.project_id == project_id,
        AlertDestination.enabled.is_(True),
    ).all()
    if destinations:
        results = notify_destinations(alert, destinations)
        for r in results:
            dest = db.query(AlertDestination).filter_by(id=r["destination_id"]).first()
            if dest:
                dest.last_error = r.get("error")
                if r["success"]:
                    dest.last_notified_at = datetime.now(timezone.utc)
        db.commit()

    return _alert_to_dict(alert)


@router.get("/alert-rules")
def list_alert_rules(auth: AuthContext = Depends(require_role("read_only"))):
    rules = (
        auth.db.query(AlertRule)
        .filter(AlertRule.project_id == auth.project_id)
        .order_by(AlertRule.name)
        .all()
    )
    return [_alert_rule_to_dict(rule) for rule in rules]


@router.get("/alert-rules/taxonomy")
def get_alert_rule_taxonomy(auth: AuthContext = Depends(require_role("read_only"))):
    return {source: list(event_types) for source, event_types in ALERT_EVENT_TAXONOMY.items()}


@router.post("/alert-rules", status_code=status.HTTP_201_CREATED)
def create_alert_rule(body: AlertRuleCreate, auth: AuthContext = Depends(require_role("editor"))):
    _validate_alert_rule_match(body.source, body.event_type)
    existing = auth.db.query(AlertRule).filter(
        AlertRule.project_id == auth.project_id, AlertRule.name == body.name
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Alert rule name already exists")
    rule = AlertRule(project_id=auth.project_id, **body.model_dump())
    auth.db.add(rule)
    auth.db.commit()
    auth.db.refresh(rule)
    return _alert_rule_to_dict(rule)


@router.patch("/alert-rules/{rule_id}")
def update_alert_rule(rule_id: str, body: AlertRuleUpdate, auth: AuthContext = Depends(require_role("editor"))):
    rule = auth.db.query(AlertRule).filter(AlertRule.id == rule_id, AlertRule.project_id == auth.project_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    changes = body.model_dump(exclude_unset=True)
    _validate_alert_rule_match(changes.get("source", rule.source), changes.get("event_type", rule.event_type))
    if "name" in changes and changes["name"] != rule.name:
        duplicate = auth.db.query(AlertRule).filter(
            AlertRule.project_id == auth.project_id, AlertRule.name == changes["name"], AlertRule.id != rule.id
        ).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="Alert rule name already exists")
    for field, value in changes.items():
        setattr(rule, field, value)
    auth.db.commit()
    auth.db.refresh(rule)
    return _alert_rule_to_dict(rule)


@router.delete("/alert-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert_rule(rule_id: str, auth: AuthContext = Depends(require_role("editor"))):
    rule = auth.db.query(AlertRule).filter(AlertRule.id == rule_id, AlertRule.project_id == auth.project_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    auth.db.delete(rule)
    auth.db.commit()


@router.patch("/alerts/{alert_id}")
def update_alert_lifecycle(alert_id: str, body: AlertLifecycleUpdate, auth: AuthContext = Depends(require_role("editor"))):
    alert = auth.db.query(Alert).filter(Alert.id == alert_id, Alert.project_id == auth.project_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status == "resolved":
        raise HTTPException(status_code=409, detail="Alert is already resolved")
    now = datetime.now(timezone.utc)
    if body.status == "acknowledged":
        alert.status = "acknowledged"
        alert.acknowledged_at = alert.acknowledged_at or now
    else:
        alert.status = "resolved"
        alert.acknowledged_at = alert.acknowledged_at or now
        alert.resolved_at = now
        alert.resolved_by = body.resolved_by
    auth.db.commit()
    auth.db.refresh(alert)
    return _alert_to_dict(alert)
