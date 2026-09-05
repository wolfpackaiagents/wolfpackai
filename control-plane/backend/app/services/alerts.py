"""Alert rule matching shared by alert producers."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models.entities import AlertRule


def matching_alert_severity(db: Session, project_id: str, source: str, event_type: str) -> str | None:
    """Return the most specific enabled rule's severity for an alert event."""
    rules = (
        db.query(AlertRule)
        .filter(AlertRule.project_id == project_id, AlertRule.enabled.is_(True))
        .filter((AlertRule.source.is_(None)) | (AlertRule.source == source))
        .filter((AlertRule.event_type.is_(None)) | (AlertRule.event_type == event_type))
        .order_by(AlertRule.created_at, AlertRule.name)
        .all()
    )
    if not rules:
        return None
    rules.sort(key=lambda rule: (bool(rule.source) + bool(rule.event_type)), reverse=True)
    return rules[0].severity
