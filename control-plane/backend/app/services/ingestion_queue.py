"""Database-backed ingestion queue and dispatch selection."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import BackgroundTasks
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models.entities import Alert, IngestionJob
from .ingestion import IngestionService
from .alerts import matching_alert_severity

logger = logging.getLogger(__name__)

INNGEST_INGESTION_EVENT = "wolfpack/ingestion.process"


def enqueue_ingestion_job(db: Session, project_id: str, payload: dict[str, Any]) -> IngestionJob:
    """Persist a job before returning so accepted events survive a process restart."""
    job = IngestionJob(project_id=project_id, payload=payload)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def inngest_dispatch_configured() -> bool:
    """Whether this process can send events to Inngest without Cloud credentials in dev."""
    settings = get_settings()
    return settings.ingestion_dispatcher == "inngest" and (
        settings.inngest_dev or (bool(settings.inngest_event_key) and bool(settings.inngest_signing_key))
    )


def send_ingestion_job_to_inngest(job_id: str) -> None:
    """Publish a durable job reference; the database remains the source of truth."""
    try:
        import inngest
    except ImportError as exc:
        raise RuntimeError("Install the 'inngest' optional dependency to enable Inngest dispatch") from exc

    settings = get_settings()
    client = inngest.Inngest(
        app_id=settings.inngest_app_id,
        event_key=settings.inngest_event_key,
        signing_key=settings.inngest_signing_key,
        is_production=not settings.inngest_dev,
    )
    client.send_sync(inngest.Event(name=INNGEST_INGESTION_EVENT, data={"job_id": job_id}))


def schedule_ingestion_job(
    background_tasks: BackgroundTasks,
    session_factory: Callable[[], Session],
    job_id: str,
) -> str:
    """Dispatch through Inngest when configured, otherwise run the local dev worker."""
    if inngest_dispatch_configured():
        background_tasks.add_task(send_ingestion_job_to_inngest, job_id)
        return "inngest"

    background_tasks.add_task(process_ingestion_job, session_factory, job_id)
    return "local"


def process_ingestion_job(session_factory: Callable[[], Session], job_id: str) -> bool:
    """Claim and process one job with a worker-owned database session."""
    settings = get_settings()
    stale_before = datetime.now(timezone.utc) - timedelta(seconds=settings.ingestion_job_lock_seconds)

    with session_factory() as db:
        job = (
            db.query(IngestionJob)
            .filter(IngestionJob.id == job_id)
            .filter(
                or_(
                    IngestionJob.status == "pending",
                    and_(IngestionJob.status == "processing", IngestionJob.locked_at < stale_before),
                )
            )
            .with_for_update(skip_locked=True)
            .first()
        )
        if job is None:
            return False

        job.status = "processing"
        job.locked_at = datetime.now(timezone.utc)
        job.attempts += 1
        db.commit()

        try:
            IngestionService(db, job.project_id).process_batch(job.payload)
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.locked_at = None
            db.commit()
            return True
        except Exception as exc:
            db.rollback()
            job = db.get(IngestionJob, job_id)
            if job is None:
                raise
            job.last_error = str(exc)
            job.locked_at = None
            exhausted = job.attempts >= settings.ingestion_job_max_attempts
            job.status = "failed" if exhausted else "pending"
            event_type = "ingestion_failed" if exhausted else "ingestion_retry"
            default_severity = "error" if exhausted else "warning"
            db.add(
                Alert(
                    project_id=job.project_id,
                    ingestion_job_id=job.id,
                    source="ingestion",
                    event_type=event_type,
                    severity=matching_alert_severity(db, job.project_id, "ingestion", event_type) or default_severity,
                    # Do not copy exception text because it can include event payload data.
                    message="Ingestion job failed permanently." if exhausted else "Ingestion job failed and will be retried.",
                    metadata_field={"attempt": job.attempts},
                )
            )
            db.commit()
            logger.exception("Ingestion job %s failed", job_id)
            return False


def next_ingestion_job_id(session_factory: Callable[[], Session]) -> str | None:
    """Return a pending or abandoned job id for the recovery worker."""
    settings = get_settings()
    stale_before = datetime.now(timezone.utc) - timedelta(seconds=settings.ingestion_job_lock_seconds)
    with session_factory() as db:
        job = (
            db.query(IngestionJob.id)
            .filter(
                or_(
                    IngestionJob.status == "pending",
                    and_(IngestionJob.status == "processing", IngestionJob.locked_at < stale_before),
                )
            )
            .order_by(IngestionJob.created_at)
            .first()
        )
        return job[0] if job else None
