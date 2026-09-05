"""Supported sources and event types for managed alert rules."""

ALERT_EVENT_TAXONOMY: dict[str, tuple[str, ...]] = {
    "ingestion": ("ingestion_retry", "ingestion_failed"),
    "guardrail": ("policy_allowed", "policy_blocked", "policy_warning"),
    "hitl": ("approval_required", "approval_approved", "approval_rejected", "approval_expired"),
    "mesh": ("delegation_failed", "handoff_failed", "route_failed", "agent_unavailable"),
    "schedule": ("schedule_failed", "schedule_deadline_exceeded"),
}


def is_valid_alert_rule_match(source: str | None, event_type: str | None) -> bool:
    """Validate a source/event pair while preserving either wildcard dimension."""
    if source is not None and source not in ALERT_EVENT_TAXONOMY:
        return False
    if event_type is None:
        return True
    if source is None:
        return any(event_type in event_types for event_types in ALERT_EVENT_TAXONOMY.values())
    return event_type in ALERT_EVENT_TAXONOMY[source]
