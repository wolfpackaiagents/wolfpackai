"""FastAPI app for the Wolfpack AMP (control plane).

Mounts the public routes (ingestion + query), admin (projects/api keys), and an
initial organization/project seed on startup.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import text

from .core.config import get_settings
from .core.database import Base, SessionLocal, engine
from .core.rate_limit import InMemoryRateLimiter, RedisRateLimiter
from .models.entities import ApiKey, Organization, Project
from .routes import admin, alert_destinations, approvals, channels, chat, evals, governance, ingestion, mesh, observability, privacy, provider_secrets, queries, schedule_policies, schedules, scores, sessions
from .services.ingestion_queue import (
    inngest_dispatch_configured,
    next_ingestion_job_id,
    process_ingestion_job,
    send_ingestion_job_to_inngest,
)
from .services.inngest import register_inngest_functions
from .services.price_updater import check_and_update_prices

logger = logging.getLogger(__name__)

HTTP_REQUESTS = Counter("wolfpack_http_requests_total", "HTTP requests handled by AMP.", ("method", "route", "status_code"))
HTTP_DURATION = Histogram("wolfpack_http_request_duration_seconds", "AMP HTTP request duration.", ("method", "route", "status_code"))


def seed_default() -> None:
    """Creates the org/project and development API key if they don't exist."""
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        org = db.query(Organization).first()
        if not org:
            org = Organization(id=uuid.uuid4().hex, name="Default Org")
            db.add(org)
            db.flush()
            project = Project(organization_id=org.id, name="Default Project")
            db.add(project)
            db.flush()
            # dev api key: pk-wp-dev:sk-dev-secret (local development only)
            import hashlib

            key = ApiKey(
                project_id=project.id,
                public_key="pk-wp-dev",
                hashed_secret_key=hashlib.sha256("dev-secret".encode()).hexdigest(),
                display_secret_key="dev-secret",
                note="dev key",
            )
            db.add(key)
            db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import os

    if os.environ.get("WOLFPACK_AUTO_SEED", "1") == "1":
        try:
            seed_default()
        except Exception:
            logger.warning("seed_default skipped (engine not ready)")
    async def recover_ingestion_jobs() -> None:
        while True:
            try:
                job_id = await asyncio.to_thread(next_ingestion_job_id, app.state.ingestion_session_factory)
                if job_id:
                    if inngest_dispatch_configured():
                        await asyncio.to_thread(send_ingestion_job_to_inngest, job_id)
                    else:
                        await asyncio.to_thread(process_ingestion_job, app.state.ingestion_session_factory, job_id)
                        continue
            except Exception:
                logger.exception("Ingestion recovery worker failed")
            await asyncio.sleep(get_settings().ingestion_worker_poll_seconds)

    async def poll_schedules() -> None:
        from .services.schedule_runtime import ScheduleRuntime

        while True:
            try:
                def dispatch() -> int:
                    with app.state.scheduler_session_factory() as db:
                        return ScheduleRuntime(db).dispatch_once("local-poll")

                await asyncio.to_thread(dispatch)
            except Exception:
                logger.exception("Schedule polling worker failed")
            await asyncio.sleep(get_settings().scheduler_poll_seconds)

    worker = asyncio.create_task(recover_ingestion_jobs())
    scheduler = asyncio.create_task(poll_schedules()) if get_settings().scheduler_dispatcher == "local" else None

    async def update_prices() -> None:
        while True:
            try:
                def do_update() -> int:
                    from sqlalchemy.orm import Session
                    with Session(engine) as db:
                        return check_and_update_prices(db)
                count = await asyncio.to_thread(do_update)
                if count:
                    logger.info("Price updater refreshed %d model prices", count)
            except Exception:
                logger.exception("Price updater worker failed")
            await asyncio.sleep(get_settings().price_update_interval_hours * 3600)

    price_worker = asyncio.create_task(update_prices())

    try:
        yield
    finally:
        price_worker.cancel()
        worker.cancel()
        if scheduler:
            scheduler.cancel()
        with suppress(asyncio.CancelledError):
            await worker
        if scheduler:
            with suppress(asyncio.CancelledError):
                await scheduler
        with suppress(asyncio.CancelledError):
            await price_worker


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.ingestion_session_factory = SessionLocal
    app.state.scheduler_session_factory = SessionLocal
    if settings.rate_limit_backend == "redis":
        import redis

        app.state.redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        app.state.rate_limiter = RedisRateLimiter(app.state.redis, settings.api_rate_limit_requests, settings.api_rate_limit_window_seconds, settings.rate_limit_redis_prefix)
    else:
        app.state.redis = None
        app.state.rate_limiter = InMemoryRateLimiter(settings.api_rate_limit_requests, settings.api_rate_limit_window_seconds)
    register_inngest_functions(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def record_http_metrics(request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)
        started = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        HTTP_REQUESTS.labels(request.method, route_path, str(response.status_code)).inc()
        HTTP_DURATION.labels(request.method, route_path, str(response.status_code)).observe(time.perf_counter() - started)
        return response

    @app.get("/metrics", include_in_schema=False)
    def prometheus_metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.include_router(ingestion.router, prefix="/api/public")
    app.include_router(privacy.router)
    app.include_router(governance.router)
    app.include_router(queries.router, prefix="/api/public")
    app.include_router(admin.router)
    app.include_router(approvals.router)
    app.include_router(schedule_policies.router)
    app.include_router(sessions.router)
    app.include_router(scores.router)
    app.include_router(evals.router)
    app.include_router(mesh.router)
    app.include_router(schedules.router)
    app.include_router(chat.router)
    app.include_router(channels.router)
    app.include_router(provider_secrets.router)
    app.include_router(observability.router)
    app.include_router(alert_destinations.router)

    @app.get("/health")
    def health():
        return {"status": "ok", "app": settings.app_name}

    @app.get("/ready")
    def ready():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            if app.state.redis is not None:
                app.state.redis.ping()
        except Exception:
            return Response(status_code=503)
        return {"status": "ready"}

    return app


app = create_app()


def main() -> None:
    import sys

    if len(sys.argv) > 1 and sys.argv[1] in {"seed-demo", "reset-demo"}:
        from .demo_seed import seed_demo

        seed_demo(reset=sys.argv[1] == "reset-demo")
        return
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
