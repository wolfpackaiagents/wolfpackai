"""Metrics and alert signals emitted by the durable scheduler."""

from __future__ import annotations

from prometheus_client import Counter
from sqlalchemy.orm import Session

from ..models.entities import Alert, ScheduledTaskRun
from .alerts import matching_alert_severity

SCHEDULE_RUNS = Counter(
    "wolfpack_schedule_runs_total",
    "Schedule runs by terminal state.",
    ("status",),
)
SCHEDULE_RETRIES = Counter(
    "wolfpack_schedule_retries_total",
    "Schedule runs moved to retry.",
)


def trace_id_for(run: ScheduledTaskRun) -> str | None:
    if run.trace_id:
        return run.trace_id
    result = run.result if isinstance(run.result, dict) else {}
    trace_id = result.get("trace_id")
    return trace_id if isinstance(trace_id, str) else None


def record_terminal_failure(db: Session, run: ScheduledTaskRun) -> None:
    """Persist a payload-free operator alert for a failed schedule occurrence."""
    event_type = "schedule_deadline_exceeded" if run.status == "deadline_exceeded" else "schedule_failed"
    severity = matching_alert_severity(db, run.project_id, "schedule", event_type) or "error"
    db.add(Alert(
        project_id=run.project_id,
        trace_id=trace_id_for(run),
        source="schedule",
        event_type=event_type,
        severity=severity,
        message=f"Schedule run {run.id} {run.status.replace('_', ' ')}.",
        metadata_field={"schedule_id": run.schedule_id, "run_id": run.id, "attempt": run.attempt},
    ))
