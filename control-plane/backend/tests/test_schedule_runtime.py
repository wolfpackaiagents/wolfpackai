"""Focused durable scheduler tests independent of the HTTP API."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import Alert, Environment, EnvironmentRegistration, MeshDefinition, Organization, Project, RegistrationHeartbeat, RuntimeReplica, Schedule, ScheduledTaskRun
from app.services.schedule_runtime import ScheduleRuntime


@pytest.fixture()
def scheduler_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        org = Organization(id="org", name="Org")
        project = Project(id="project", organization_id=org.id, name="Project")
        environment = Environment(id="environment", project_id=project.id, slug="local", name="Local")
        definition = MeshDefinition(id="definition", project_id=project.id, key="worker", kind="agent", name="Worker", version="1")
        registration = EnvironmentRegistration(id="registration", project_id=project.id, environment_id=environment.id, definition_id=definition.id, schedule_endpoint="http://localhost:9009/run")
        db.add_all([org, project, environment, definition, registration])
        db.commit()
        yield db


def test_materialization_is_idempotent_and_claims_fence_retries(scheduler_db):
    now = datetime.now(timezone.utc)
    schedule = Schedule(id="schedule", project_id="project", registration_id="registration", name="every-minute", schedule_type="interval", interval_seconds=60, next_run_at=now - timedelta(seconds=1), max_attempts=2, retry_delay_seconds=1)
    scheduler_db.add(schedule)
    scheduler_db.commit()
    runtime = ScheduleRuntime(scheduler_db)

    assert len(runtime.materialize_due(now=now)) == 1
    run = scheduler_db.query(ScheduledTaskRun).one()
    assert run.attempt == 0
    # A duplicate delivery of the same occurrence cannot create a second run.
    schedule.next_run_at = now - timedelta(seconds=1)
    scheduler_db.commit()
    assert runtime.materialize_due(now=now) == []
    assert scheduler_db.query(ScheduledTaskRun).count() == 1

    first = runtime.claim("worker-a", now=now)[0]
    assert first.attempt == 1 and first.fencing_token == 1
    runtime.fail(first.id, first.fencing_token, "temporary")
    retry = runtime.claim("worker-b", now=now + timedelta(seconds=2))[0]
    assert retry.attempt == 2 and retry.fencing_token == 2
    with pytest.raises(ValueError, match="stale run claim"):
        runtime.complete(retry.id, 1, {})
    completed = runtime.complete(retry.id, 2, {"ok": True, "trace_id": "trace-completed"})
    assert (completed.status, completed.trace_id) == ("succeeded", "trace-completed")


def test_http_dispatch_uses_registration_endpoint_and_fresh_heartbeat_only(scheduler_db, monkeypatch):
    now = datetime.now(timezone.utc)
    run = ScheduledTaskRun(id="run", project_id="project", schedule_id="schedule", registration_id="registration", occurrence_key="manual:test", trigger="manual", status="running", scheduled_for=now, max_attempts=1, attempt=1, fencing_token=7, lease_expires_at=now + timedelta(minutes=1), payload={"task": "report"})
    scheduler_db.add_all([
        Schedule(id="schedule", project_id="project", registration_id="registration", name="manual", schedule_type="interval", interval_seconds=60),
        RegistrationHeartbeat(project_id="project", registration_id="registration", instance_id="fresh", last_seen=now, metadata_field={"capabilities": {"scheduled_task_endpoint": "http://attacker.invalid"}}),
        run,
    ])
    scheduler_db.commit()
    runtime = ScheduleRuntime(scheduler_db)
    runtime.settings.scheduler_allow_insecure_http = True
    runtime.settings.scheduler_dispatch_secret = "dispatch-secret"
    sent = {}

    class Response:
        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, endpoint, **kwargs):
            sent["endpoint"] = endpoint
            sent.update(kwargs)
            return Response()

    monkeypatch.setattr("app.services.schedule_runtime.httpx.Client", Client)
    runtime._dispatch_http(run)

    assert sent["endpoint"] == "http://localhost:9009/run"
    assert b'"target_instance_id":"fresh"' in sent["content"]
    assert sent["headers"]["X-Wolfpack-Schedule-Signature"].startswith("sha256=")


def test_http_dispatch_uses_least_loaded_authorized_replica(scheduler_db, monkeypatch):
    now = datetime.now(timezone.utc)
    scheduler_db.add_all([
        Schedule(id="schedule", project_id="project", registration_id="registration", name="manual", schedule_type="interval", interval_seconds=60),
        RegistrationHeartbeat(project_id="project", registration_id="registration", instance_id="busy", last_seen=now),
        RegistrationHeartbeat(project_id="project", registration_id="registration", instance_id="free", last_seen=now),
        RuntimeReplica(project_id="project", registration_id="registration", instance_id="busy", endpoint="http://localhost:9010/run", capacity=1),
        RuntimeReplica(project_id="project", registration_id="registration", instance_id="free", endpoint="http://localhost:9011/run", capacity=2),
        ScheduledTaskRun(id="occupied", project_id="project", schedule_id="schedule", registration_id="registration", occurrence_key="manual:occupied", trigger="manual", status="running", scheduled_for=now, max_attempts=1, claimed_by="busy"),
        ScheduledTaskRun(id="selected", project_id="project", schedule_id="schedule", registration_id="registration", occurrence_key="manual:selected", trigger="manual", status="running", scheduled_for=now, max_attempts=1, attempt=1, fencing_token=1, lease_expires_at=now + timedelta(minutes=1)),
    ])
    scheduler_db.commit()
    runtime = ScheduleRuntime(scheduler_db)
    runtime.settings.scheduler_allow_insecure_http = True
    runtime.settings.scheduler_dispatch_secret = "dispatch-secret"
    sent = {}

    class Response:
        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, **_kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def post(self, endpoint, **_kwargs): sent["endpoint"] = endpoint; return Response()

    monkeypatch.setattr("app.services.schedule_runtime.httpx.Client", Client)
    runtime._dispatch_http(scheduler_db.get(ScheduledTaskRun, "selected"))
    assert sent["endpoint"] == "http://localhost:9011/run"
    assert scheduler_db.get(ScheduledTaskRun, "selected").claimed_by == "free"


def test_renew_lease_requires_matching_replica_claim(scheduler_db):
    now = datetime.now(timezone.utc)
    run = ScheduledTaskRun(id="renew", project_id="project", schedule_id="schedule", registration_id="registration", occurrence_key="manual:renew", trigger="manual", status="running", scheduled_for=now, max_attempts=1, attempt=1, fencing_token=3, claimed_by="replica", lease_expires_at=now + timedelta(seconds=1))
    scheduler_db.add(run)
    scheduler_db.commit()
    runtime = ScheduleRuntime(scheduler_db)
    with pytest.raises(ValueError, match="stale"):
        runtime.renew_lease(run.id, 3, "other")
    assert runtime.renew_lease(run.id, 3, "replica").lease_expires_at is not None


def test_terminal_failure_creates_a_schedule_alert(scheduler_db):
    now = datetime.now(timezone.utc)
    schedule = Schedule(id="schedule", project_id="project", registration_id="registration", name="failing", schedule_type="interval", interval_seconds=60, max_attempts=1)
    run = ScheduledTaskRun(id="run", project_id="project", schedule_id=schedule.id, registration_id="registration", occurrence_key="manual:failure", trigger="manual", status="running", scheduled_for=now, max_attempts=1, attempt=1, fencing_token=1, lease_expires_at=now + timedelta(minutes=1), result={"trace_id": "trace-1"})
    scheduler_db.add_all([schedule, run])
    scheduler_db.commit()

    ScheduleRuntime(scheduler_db).fail(run.id, 1, "runtime unavailable")

    alert = scheduler_db.query(Alert).one()
    assert (alert.source, alert.event_type, alert.trace_id, alert.metadata_field["schedule_id"]) == ("schedule", "schedule_failed", "trace-1", "schedule")
