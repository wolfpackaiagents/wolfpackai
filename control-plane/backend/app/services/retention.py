"""Project-scoped trace retention cleanup."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..models.entities import Approval, Observation, Project, Score, Trace


class RetentionService:
    def __init__(self, db: Session, project_id: str):
        self.db = db
        self.project_id = project_id

    def cleanup_expired_traces(self) -> int:
        """Deletes traces and dependent records older than the project retention period."""
        project = self.db.get(Project, self.project_id)
        if not project:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=project.retention_days)
        trace_ids = [
            trace_id
            for (trace_id,) in self.db.query(Trace.id)
            .filter(Trace.project_id == self.project_id, Trace.created_at < cutoff)
            .all()
        ]
        if not trace_ids:
            return 0
        self.db.query(Approval).filter(Approval.project_id == self.project_id, Approval.trace_id.in_(trace_ids)).delete(synchronize_session=False)
        self.db.query(Score).filter(Score.project_id == self.project_id, Score.trace_id.in_(trace_ids)).delete(synchronize_session=False)
        self.db.query(Observation).filter(Observation.project_id == self.project_id, Observation.trace_id.in_(trace_ids)).delete(synchronize_session=False)
        deleted = self.db.query(Trace).filter(Trace.project_id == self.project_id, Trace.id.in_(trace_ids)).delete(synchronize_session=False)
        self.db.commit()
        return deleted
