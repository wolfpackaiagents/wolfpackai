"""Privacy helpers for project-level PII redaction and LGPD subject requests."""

from __future__ import annotations

import copy
import hashlib
import re
from typing import Any

from sqlalchemy.orm import Session

from ..models.entities import Alert, Approval, IngestionJob, Observation, PrivacyAuditLog, Score, Trace

_PATTERNS = {
    "email": re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    "phone": re.compile(r"(?<!\d)(?:\+?\d[\s().-]*){8,15}(?!\d)"),
    "cpf": re.compile(r"(?<!\d)\d{3}[.-]?\d{3}[.-]?\d{3}-?\d{2}(?!\d)"),
    "credit_card": re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"),
}


def redact_ingestion_payload(payload: dict[str, Any], config: dict[str, Any] | None) -> dict[str, Any]:
    """Return a sanitized payload before it enters the durable ingestion queue."""
    if not config or not config.get("enabled", False):
        return payload

    patterns = [
        (name, pattern)
        for name, pattern in _PATTERNS.items()
        if config.get(f"redact_{name}", True)
    ]
    for value in config.get("custom_patterns", []):
        try:
            patterns.append(("custom", re.compile(value)))
        except (TypeError, re.error):
            continue

    def redact(value: Any, key: str | None = None) -> Any:
        if key == "user_id":
            # The SDK user ID is the subject lookup key and may already be pseudonymous.
            return value
        if isinstance(value, str):
            for name, pattern in patterns:
                value = pattern.sub(f"[REDACTED_{name.upper()}]", value)
            return value
        if isinstance(value, list):
            return [redact(item) for item in value]
        if isinstance(value, dict):
            return {item_key: redact(item_value, item_key) for item_key, item_value in value.items()}
        return value

    return redact(copy.deepcopy(payload))


def subject_hash(user_id: str) -> str:
    """Hash identifiers retained in audit records to avoid duplicating PII."""
    return hashlib.sha256(user_id.encode()).hexdigest()


def job_belongs_to_subject(job: IngestionJob, user_id: str) -> bool:
    """Match queued SDK events that explicitly identify the data subject."""
    events = job.payload.get("events", []) if isinstance(job.payload, dict) else []
    return any(
        isinstance(event, dict)
        and isinstance(event.get("body"), dict)
        and event["body"].get("user_id") == user_id
        for event in events
    )


def add_privacy_audit_log(
    db: Session, project_id: str, user_id: str, action: str, details: dict[str, Any]
) -> None:
    db.add(
        PrivacyAuditLog(
            project_id=project_id,
            action=action,
            subject_hash=subject_hash(user_id),
            details=details,
        )
    )


def delete_subject_data(db: Session, project_id: str, user_id: str) -> dict[str, int]:
    """Delete a subject's traces and trace-owned records within one project."""
    trace_ids = [
        trace_id
        for (trace_id,) in db.query(Trace.id)
        .filter(Trace.project_id == project_id, Trace.user_id == user_id)
        .all()
    ]
    job_ids = [
        job.id
        for job in db.query(IngestionJob).filter(IngestionJob.project_id == project_id).all()
        if job_belongs_to_subject(job, user_id)
    ]
    deleted = {"traces": 0, "observations": 0, "scores": 0, "approvals": 0, "alerts": 0, "jobs": 0}
    if trace_ids:
        deleted["observations"] = (
            db.query(Observation)
            .filter(Observation.project_id == project_id, Observation.trace_id.in_(trace_ids))
            .delete(synchronize_session=False)
        )
        deleted["scores"] = (
            db.query(Score)
            .filter(Score.project_id == project_id, Score.trace_id.in_(trace_ids))
            .delete(synchronize_session=False)
        )
        deleted["approvals"] = (
            db.query(Approval)
            .filter(Approval.project_id == project_id, Approval.trace_id.in_(trace_ids))
            .delete(synchronize_session=False)
        )
        deleted["alerts"] = (
            db.query(Alert)
            .filter(Alert.project_id == project_id, Alert.trace_id.in_(trace_ids))
            .delete(synchronize_session=False)
        )
        deleted["traces"] = (
            db.query(Trace)
            .filter(Trace.project_id == project_id, Trace.id.in_(trace_ids))
            .delete(synchronize_session=False)
        )
    if job_ids:
        deleted["jobs"] = (
            db.query(IngestionJob)
            .filter(IngestionJob.project_id == project_id, IngestionJob.id.in_(job_ids))
            .delete(synchronize_session=False)
        )
    return deleted
