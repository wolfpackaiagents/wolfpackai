"""Optional Inngest orchestration for durable ingestion and scheduled runs."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from .ingestion_queue import INNGEST_INGESTION_EVENT, inngest_dispatch_configured, process_ingestion_job

logger = logging.getLogger(__name__)


def register_inngest_functions(app: FastAPI) -> None:
    """Expose one Inngest endpoint when either durable workload uses it."""
    from ..core.config import get_settings

    settings = get_settings()
    if not inngest_dispatch_configured() and settings.scheduler_dispatcher != "inngest":
        return

    try:
        import inngest
        import inngest.fast_api
    except ImportError as exc:
        raise RuntimeError("Install the 'inngest' optional dependency to enable Inngest dispatch") from exc

    client = inngest.Inngest(
        app_id=settings.inngest_app_id,
        event_key=settings.inngest_event_key,
        signing_key=settings.inngest_signing_key,
        is_production=not settings.inngest_dev,
    )

    functions = []
    if inngest_dispatch_configured():
        @client.create_function(fn_id="process-ingestion-job", trigger=inngest.TriggerEvent(event=INNGEST_INGESTION_EVENT))
        def process_job(ctx: inngest.ContextSync) -> dict[str, bool]:
            return {"processed": process_ingestion_job(app.state.ingestion_session_factory, ctx.event.data["job_id"])}
        functions.append(process_job)
    if settings.scheduler_dispatcher == "inngest":
        @client.create_function(fn_id="poll-scheduled-runs", trigger=inngest.TriggerCron(cron="* * * * *"))
        def poll_scheduled_runs(_ctx: inngest.ContextSync) -> dict[str, int]:
            from .schedule_runtime import ScheduleRuntime

            with app.state.scheduler_session_factory() as db:
                return {"dispatched": ScheduleRuntime(db).dispatch_once(worker_id="inngest")}
        functions.append(poll_scheduled_runs)
    inngest.fast_api.serve(app, client, functions)


def register_ingestion_function(app: FastAPI) -> None:
    """Compatibility wrapper for callers that only knew ingestion registration."""
    register_inngest_functions(app)
