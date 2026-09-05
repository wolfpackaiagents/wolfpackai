"""Ingestion route: `POST /api/public/ingestion` queues authenticated batches."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from ..core.auth import AuthContext, require_role
from ..models.entities import Project
from ..schemas.contract import IngestionAccepted, IngestionRequest
from ..services.ingestion_queue import enqueue_ingestion_job, schedule_ingestion_job
from ..services.privacy import redact_ingestion_payload

router = APIRouter()


@router.post("/ingestion", response_model=IngestionAccepted, status_code=202)
def ingest(
    payload: IngestionRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    auth: AuthContext = Depends(require_role("editor")),
):
    project_id, db = auth
    project = db.get(Project, project_id)
    sanitized_payload = redact_ingestion_payload(
        payload.model_dump(mode="json"), project.pii_redaction_config if project else None
    )
    job = enqueue_ingestion_job(db, project_id, sanitized_payload)
    schedule_ingestion_job(background_tasks, request.app.state.ingestion_session_factory, job.id)
    return IngestionAccepted(
        job_id=job.id,
        events_accepted=len(payload.events),
    )
