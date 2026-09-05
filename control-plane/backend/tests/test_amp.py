"""AMP integration tests (ingestion + query) with in-memory SQLite and the FastAPI
TestClient. Validates the end-to-end Observer SDK flow without Postgres."""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from fastapi import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main as app_main
from app.core.database import get_db
from app.core.config import get_settings
from app.models.entities import ApiKey, Approval, Base, Environment, EnvironmentRegistration, IngestionJob, MeshDefinition, MeshInteraction, Organization, PolicyDecisionAudit, Project, RegistrationHeartbeat, Score, Trace
from app.models.model_price import ModelPrice
from app.services import ingestion_queue
from app.services.cost_estimation import estimate_cost
from app.services.price_updater import check_and_update_prices
from app.services.scheduling import next_run_at


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(get_settings(), "provider_secrets_master_key", Fernet.generate_key().decode())
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    project_id = uuid.uuid4().hex[:32]

    with Session() as db:
        org = Organization(id=uuid.uuid4().hex[:32], name="Test Org")
        db.add(org)
        db.flush()
        proj = Project(id=project_id, organization_id=org.id, name="Test Proj")
        db.add(proj)
        db.flush()
        db.add(
            ApiKey(
                id="admin-key-00000000000000000000001",
                project_id=proj.id,
                public_key="pk-test",
                hashed_secret_key="ef260e9aa3c673af240d17a2660480361a8e081d1ffeca2a5ed0e3219fc18567",  # sha256("dev")
                display_secret_key="dev",
                note="t",
                role="admin",
            )
        )
        db.add(
            ApiKey(
                project_id=proj.id,
                public_key="pk-read-only",
                hashed_secret_key="ef260e9aa3c673af240d17a2660480361a8e081d1ffeca2a5ed0e3219fc18567",
                display_secret_key="dev",
                note="read-only test key",
                role="read_only",
            )
        )
        db.add(
            ApiKey(
                project_id=proj.id,
                public_key="pk-editor",
                hashed_secret_key="ef260e9aa3c673af240d17a2660480361a8e081d1ffeca2a5ed0e3219fc18567",
                display_secret_key="dev",
                note="editor test key",
                role="editor",
            )
        )
        db.commit()

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app_main.app.dependency_overrides[get_db] = override_get_db
    previous_session_factory = app_main.app.state.ingestion_session_factory
    app_main.app.state.ingestion_session_factory = Session
    with TestClient(app_main.app) as c:
        c.session_factory = Session
        c.project_id = project_id
        yield c
    app_main.app.state.ingestion_session_factory = previous_session_factory
    app_main.app.dependency_overrides.clear()


def _auth():
    return {"X-API-Key": "pk-test:dev"}


def _auth_as(public_key: str):
    return {"X-API-Key": f"{public_key}:dev"}


def test_health(client):
    assert client.get("/health").status_code == 200


def test_schedule_next_runs_are_deterministic_for_at_interval_and_timezone_aware_cron():
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)

    assert next_run_at("at", now, at=datetime(2026, 8, 24, 12, 1, tzinfo=timezone.utc)) == datetime(2026, 8, 24, 12, 1, tzinfo=timezone.utc)
    assert next_run_at("at", now, at=now) is None
    assert next_run_at("interval", now, interval_seconds=90) == datetime(2026, 8, 24, 12, 1, 30, tzinfo=timezone.utc)
    assert next_run_at("cron", datetime(2026, 8, 24, 11, 59, tzinfo=timezone.utc), cron="0 9 * * 1-5", timezone_name="America/Sao_Paulo") == datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def test_schedules_are_durable_scoped_and_run_now_is_idempotent(client):
    environment = client.post("/api/public/mesh/environments", json={"slug": "scheduling", "name": "Scheduling"}, headers=_auth_as("pk-editor")).json()
    definition = client.post("/api/public/mesh/definitions", json={"key": "scheduled-agent", "kind": "agent", "name": "Scheduled Agent", "version": "1"}, headers=_auth_as("pk-editor")).json()
    registration = client.post("/api/public/mesh/registrations", json={"environment_id": environment["id"], "definition_id": definition["id"]}, headers=_auth_as("pk-editor")).json()

    created = client.post(
        "/api/public/schedules",
        json={"name": "weekday-report", "registration_id": registration["id"], "schedule_type": "cron", "cron": "0 9 * * 1-5", "timezone": "America/Sao_Paulo", "payload": {"report": "daily"}, "max_attempts": 3, "retry_delay_seconds": 30, "misfire_policy": "fire_once", "misfire_grace_seconds": 120},
        headers=_auth_as("pk-editor"),
    )

    assert created.status_code == 201
    schedule = created.json()
    assert schedule["status"] == "active"
    assert schedule["next_run_at"]
    assert schedule["retry"] == {"max_attempts": 3, "delay_seconds": 30}
    assert schedule["misfire"] == {"policy": "fire_once", "grace_seconds": 120}
    assert client.get("/api/public/schedules", headers=_auth_as("pk-read-only")).json()[0]["id"] == schedule["id"]
    updated = client.patch(f"/api/public/schedules/{schedule['id']}", json={"payload": {"report": "daily-v2"}, "max_attempts": 4}, headers=_auth_as("pk-editor"))
    assert updated.status_code == 200
    assert updated.json()["payload"] == {"report": "daily-v2"}
    assert updated.json()["retry"]["max_attempts"] == 4

    first = client.post(f"/api/public/schedules/{schedule['id']}/run-now", json={"idempotency_key": "request-123"}, headers=_auth_as("pk-editor"))
    second = client.post(f"/api/public/schedules/{schedule['id']}/run-now", json={"idempotency_key": "request-123"}, headers=_auth_as("pk-editor"))
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["status"] == "pending"
    assert first.json()["max_attempts"] == 4
    assert first.json()["payload"] == {"report": "daily-v2"}
    assert [run["id"] for run in client.get(f"/api/public/schedules/{schedule['id']}/runs", headers=_auth_as("pk-read-only")).json()] == [first.json()["id"]]

    paused = client.post(f"/api/public/schedules/{schedule['id']}/pause", headers=_auth_as("pk-editor"))
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused" and paused.json()["next_run_at"] is None
    assert client.post(f"/api/public/schedules/{schedule['id']}/run-now", json={"idempotency_key": "paused"}, headers=_auth_as("pk-editor")).status_code == 409
    resumed = client.post(f"/api/public/schedules/{schedule['id']}/resume", headers=_auth_as("pk-editor"))
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "active" and resumed.json()["next_run_at"]
    assert client.delete(f"/api/public/schedules/{schedule['id']}", headers=_auth_as("pk-editor")).status_code == 204
    assert client.get(f"/api/public/schedules/{schedule['id']}", headers=_auth()).json()["status"] == "cancelled"
    assert client.post(f"/api/public/schedules/{schedule['id']}/run-now", json={"idempotency_key": "cancelled"}, headers=_auth_as("pk-editor")).status_code == 409


def test_schedule_validation_rejects_invalid_timing_and_read_only_mutations(client):
    assert client.post("/api/public/schedules", json={"name": "missing-at", "registration_id": "missing", "schedule_type": "at"}, headers=_auth_as("pk-editor")).status_code == 422
    assert client.post("/api/public/schedules", json={"name": "bad-cron", "registration_id": "missing", "schedule_type": "cron", "cron": "bad"}, headers=_auth_as("pk-editor")).status_code == 422
    assert client.post("/api/public/schedules", json={"name": "read-only", "registration_id": "missing", "schedule_type": "interval", "interval_seconds": 60}, headers=_auth_as("pk-read-only")).status_code == 403


def test_approved_schedule_policy_mutation_is_applied(client):
    environment = client.post("/api/public/mesh/environments", json={"slug": "approval", "name": "Approval"}, headers=_auth()).json()
    definition = client.post("/api/public/mesh/definitions", json={"key": "approval-worker", "kind": "agent", "name": "Approval Worker", "version": "1"}, headers=_auth()).json()
    registration = client.post("/api/public/mesh/registrations", json={"environment_id": environment["id"], "definition_id": definition["id"]}, headers=_auth()).json()
    assert client.put("/api/public/schedule-policies/project", json={"decisions": {"schedule.create": "require_approval"}}, headers=_auth()).status_code == 200

    pending = client.post("/api/public/schedules", json={"name": "approved-schedule", "registration_id": registration["id"], "schedule_type": "interval", "interval_seconds": 300}, headers=_auth_as("pk-editor"))
    assert pending.status_code == 201
    approval_id = pending.json()["approval_id"]
    assert client.get("/api/public/schedules", headers=_auth()).json() == []

    resolved = client.post(f"/api/public/approvals/{approval_id}/resolve", json={"action": "approve"}, headers=_auth())
    assert resolved.status_code == 200
    schedules = client.get("/api/public/schedules", headers=_auth()).json()
    assert [(item["name"], item["status"]) for item in schedules] == [("approved-schedule", "active")]


def test_mesh_environment_and_registration_lifecycle(client):
    environment = client.post(
        "/api/public/mesh/environments",
        json={"slug": "staging", "name": "Staging", "description": "Release validation"},
        headers=_auth_as("pk-editor"),
    )
    assert environment.status_code == 201
    environment_id = environment.json()["id"]

    definition = client.post(
        "/api/public/mesh/definitions",
        json={
            "key": "support-triage",
            "kind": "agent",
            "name": "Support Triage",
            "version": "1.2.0",
            "description": "Routes customer requests.",
            "summary": {"model": "gpt-4o-mini", "tools": ["search_kb"]},
        },
        headers=_auth_as("pk-editor"),
    )
    assert definition.status_code == 201

    registration = client.post(
        "/api/public/mesh/registrations",
        json={"environment_id": environment_id, "definition_id": definition.json()["id"], "enabled": True},
        headers=_auth_as("pk-editor"),
    )
    assert registration.status_code == 201
    assert registration.json()["environment_slug"] == "staging"

    catalog = client.get("/api/public/mesh/catalog", headers=_auth_as("pk-read-only"))
    assert catalog.status_code == 200
    assert catalog.json()["summary"] == {"environments": 1, "registrations": 1, "active_registrations": 1}
    assert catalog.json()["environments"][0]["registrations"][0]["definition_key"] == "support-triage"

    forbidden = client.post(
        "/api/public/mesh/environments",
        json={"slug": "production", "name": "Production"},
        headers=_auth_as("pk-read-only"),
    )
    assert forbidden.status_code == 403


def test_mesh_heartbeats_aggregate_replica_health_without_registration_state(client):
    environment = client.post("/api/public/mesh/environments", json={"slug": "staging", "name": "Staging"}, headers=_auth_as("pk-editor")).json()
    definition = client.post("/api/public/mesh/definitions", json={"key": "support", "kind": "agent", "name": "Support", "version": "1"}, headers=_auth_as("pk-editor")).json()
    registration = client.post("/api/public/mesh/registrations", json={"environment_id": environment["id"], "definition_id": definition["id"]}, headers=_auth_as("pk-editor")).json()

    unknown = client.get("/api/public/mesh/catalog", headers=_auth()).json()["environments"][0]["registrations"][0]
    assert unknown["health_status"] == "unknown" and unknown["online_replicas"] == 0
    assert client.post(f"/api/public/mesh/registrations/{registration['id']}/heartbeat", json={"instance_id": "worker-a", "version": "1", "metadata": {"zone": "a"}}, headers=_auth_as("pk-editor")).status_code == 200
    assert client.post(f"/api/public/mesh/registrations/{registration['id']}/heartbeat", json={"instance_id": "worker-a", "version": "2"}, headers=_auth_as("pk-editor")).status_code == 200
    with client.session_factory() as db:
        assert db.query(RegistrationHeartbeat).filter_by(registration_id=registration["id"], instance_id="worker-a").count() == 1
        db.add(RegistrationHeartbeat(project_id=client.project_id, registration_id=registration["id"], instance_id="worker-old", last_seen=datetime.now(timezone.utc) - timedelta(hours=1)))
        db.commit()
    degraded = client.get("/api/public/mesh/catalog", headers=_auth()).json()["environments"][0]["registrations"][0]
    assert degraded["health_status"] == "degraded" and degraded["online_replicas"] == 1 and degraded["last_seen_at"]
    with client.session_factory() as db:
        db.query(RegistrationHeartbeat).filter_by(registration_id=registration["id"], instance_id="worker-a").update({"last_seen": datetime.now(timezone.utc) - timedelta(hours=1)})
        db.commit()
    offline = client.get("/api/public/mesh/catalog", headers=_auth()).json()["environments"][0]["registrations"][0]
    assert offline["health_status"] == "offline" and offline["online_replicas"] == 0
    assert client.post(f"/api/public/mesh/registrations/{registration['id']}/heartbeat", json={"instance_id": "reader"}, headers=_auth_as("pk-read-only")).status_code == 403


def test_mesh_management_updates_and_preserves_references_on_delete(client):
    environment = client.post("/api/public/mesh/environments", json={"slug": "staging", "name": "Staging"}, headers=_auth_as("pk-editor")).json()
    definition = client.post("/api/public/mesh/definitions", json={"key": "support", "kind": "agent", "name": "Support", "version": "1"}, headers=_auth_as("pk-editor")).json()
    registration = client.post("/api/public/mesh/registrations", json={"environment_id": environment["id"], "definition_id": definition["id"]}, headers=_auth_as("pk-editor")).json()

    updated_environment = client.patch(f"/api/public/mesh/environments/{environment['id']}", json={"name": "Pre-production", "status": "inactive"}, headers=_auth_as("pk-editor"))
    assert updated_environment.status_code == 200
    assert updated_environment.json()["name"] == "Pre-production"
    assert updated_environment.json()["status"] == "inactive"
    assert client.patch(f"/api/public/mesh/registrations/{registration['id']}", json={"enabled": False}, headers=_auth_as("pk-editor")).json()["enabled"] is False
    assert client.delete(f"/api/public/mesh/environments/{environment['id']}", headers=_auth_as("pk-editor")).status_code == 409

    with client.session_factory() as db:
        db.add(Trace(id="registration-reference", project_id=client.project_id, registration_id=registration["id"], environment_id=environment["id"]))
        db.commit()

    blocked = client.delete(f"/api/public/mesh/registrations/{registration['id']}", headers=_auth_as("pk-editor"))
    assert blocked.status_code == 409
    assert "trace" in blocked.json()["detail"]

    with client.session_factory() as db:
        db.query(Trace).filter(Trace.id == "registration-reference").delete()
        db.commit()

    assert client.delete(f"/api/public/mesh/registrations/{registration['id']}", headers=_auth_as("pk-editor")).status_code == 204
    assert client.delete(f"/api/public/mesh/environments/{environment['id']}", headers=_auth_as("pk-editor")).status_code == 204


def test_mesh_interactions_are_ingested_and_aggregated_as_graph_edges(client):
    payload = {
        "events": [
            {
                "id": "interaction-1",
                "type": "mesh-interaction",
                "body": {
                    "type": "EVENT",
                    "trace_id": "mesh-chain-trace",
                    "metadata": {"mesh_interaction": {"source": "triage", "target": "research", "source_display_name": "Support Triage", "target_display_name": "Research Specialist", "interaction_type": "delegation", "operation": "team.delegate", "tool_name": "knowledge_search", "metadata": {"team": "triage"}}},
                },
            },
            {
                "id": "interaction-2",
                "type": "mesh-interaction",
                "body": {
                    "type": "EVENT",
                    "trace_id": "mesh-chain-trace",
                    "metadata": {"mesh_interaction": {"source": "triage", "target": "research", "source_display_name": "Support Triage", "target_display_name": "Research Specialist", "interaction_type": "delegation", "operation": "team.delegate", "tool_name": "knowledge_search"}},
                },
            },
        ]
    }

    assert client.post("/api/public/ingestion", json=payload, headers=_auth()).status_code == 202
    interactions = client.get("/api/public/mesh/interactions", headers=_auth_as("pk-read-only"))
    graph = client.get("/api/public/mesh/graph", headers=_auth_as("pk-read-only"))

    assert interactions.status_code == 200
    assert len(interactions.json()) == 2
    assert graph.json()["nodes"] == [{"id": "research", "label": "Research Specialist"}, {"id": "triage", "label": "Support Triage"}]
    assert graph.json()["edges"][0]["count"] == 2
    assert graph.json()["edges"][0]["interaction_type"] == "delegation"
    enriched_interaction = next(item for item in interactions.json() if item["metadata"] == {"team": "triage"})
    assert enriched_interaction == {
        "id": enriched_interaction["id"],
        "source": "triage",
        "target": "research",
        "source_display_name": "Support Triage",
        "target_display_name": "Research Specialist",
        "interaction_type": "delegation",
        "operation": "team.delegate",
        "tool_name": "knowledge_search",
        "trace_id": "mesh-chain-trace",
        "metadata": {"team": "triage"},
        "created_at": enriched_interaction["created_at"],
    }
    enriched_edge = next(edge for edge in graph.json()["edges"] if edge["operation"] == "team.delegate")
    assert enriched_edge["tool_name"] == "knowledge_search"
    assert enriched_edge["source_display_name"] == "Support Triage"


def test_mesh_interactions_require_editor_to_create(client):
    payload = {"source": "router", "target": "writer", "source_display_name": "Request Router", "target_display_name": "Response Writer", "interaction_type": "route", "operation": "team.route"}

    assert client.post("/api/public/mesh/interactions", json=payload, headers=_auth_as("pk-read-only")).status_code == 403
    created = client.post("/api/public/mesh/interactions", json=payload, headers=_auth_as("pk-editor"))

    assert created.status_code == 201
    assert created.json()["source"] == "router"
    assert created.json()["operation"] == "team.route"
    assert created.json()["target_display_name"] == "Response Writer"


def test_metrics_supports_sqlite_and_empty_projects(client):
    response = client.get("/api/public/metrics", headers=_auth_as("pk-read-only"))

    assert response.status_code == 200
    assert response.json() == []

    with client.session_factory() as db:
        db.add(
            Trace(
                id="metrics-trace",
                project_id=client.project_id,
                created_at=datetime(2026, 8, 23, 10, 37, tzinfo=timezone.utc),
                timestamp=datetime(2026, 8, 23, 10, 37, tzinfo=timezone.utc),
                latency_ms=120.0,
                total_cost=0.25,
                total_cost_currency="USD",
                total_cost_source="provider",
                error="provider unavailable",
                metadata_field={"input_tokens": 3, "output_tokens": 5},
            )
        )
        db.commit()

    response = client.get("/api/public/metrics?group_by=hour", headers=_auth_as("pk-read-only"))

    assert response.status_code == 200
    assert response.json() == [
        {
            "bucket": "2026-08-23T10:00:00+00:00",
            "count": 1,
            "latency_p50": 120.0,
            "latency_p95": 120.0,
            "total_tokens": 8,
            "total_cost": 0.25,
            "total_cost_by_currency": {"USD": 0.25},
            "errors": 1,
        }
    ]


def test_ingestion_aggregates_only_currency_attributed_costs(client):
    trace_id = "cost-trace"
    payload = {
        "events": [
            {"id": "cost-root", "type": "observation-start", "body": {"id": trace_id, "trace_id": trace_id, "type": "TRACE"}},
            {"id": "cost-usd", "type": "observation-end", "body": {"id": "cost-usd", "trace_id": trace_id, "parent_observation_id": trace_id, "type": "GENERATION", "cost": 0.2, "cost_currency": "usd", "cost_source": "provider"}},
            {"id": "cost-eur", "type": "observation-end", "body": {"id": "cost-eur", "trace_id": trace_id, "parent_observation_id": trace_id, "type": "GENERATION", "cost": 0.3, "cost_currency": "EUR", "cost_source": "provider"}},
            {"id": "cost-unknown", "type": "observation-end", "body": {"id": "cost-unknown", "trace_id": trace_id, "parent_observation_id": trace_id, "type": "GENERATION"}},
        ]
    }

    assert client.post("/api/public/ingestion", json=payload, headers=_auth()).status_code == 202

    trace = client.get(f"/api/public/traces/{trace_id}", headers=_auth()).json()
    assert trace["cost"] is None
    assert trace["cost_currency"] is None
    observations = {item["id"]: item for item in trace["observations"]}
    assert observations["cost-usd"]["cost_currency"] == "USD"
    assert observations["cost-usd"]["cost_source"] == "provider"
    assert observations["cost-unknown"]["cost"] is None

    metrics = client.get("/api/public/metrics", headers=_auth()).json()
    point = next(item for item in metrics if item["count"] == 1)
    assert point["total_cost"] is None
    assert point["total_cost_by_currency"] == {"EUR": 0.3, "USD": 0.2}


def test_query_endpoints_apply_environment_registration_and_range_filters(client):
    start = datetime(2026, 8, 23, 10, 0, tzinfo=timezone.utc)
    with client.session_factory() as db:
        first_environment = Environment(id="environment-first", project_id=client.project_id, slug="staging", name="Staging")
        second_environment = Environment(id="environment-second", project_id=client.project_id, slug="production", name="Production")
        first_definition = MeshDefinition(id="definition-first", project_id=client.project_id, key="support", kind="agent", name="Support", version="1")
        second_definition = MeshDefinition(id="definition-second", project_id=client.project_id, key="sales", kind="agent", name="Sales", version="1")
        first_registration = EnvironmentRegistration(id="registration-first", project_id=client.project_id, environment_id=first_environment.id, definition_id=first_definition.id)
        second_registration = EnvironmentRegistration(id="registration-second", project_id=client.project_id, environment_id=second_environment.id, definition_id=second_definition.id)
        first_trace = Trace(id="scoped-trace", project_id=client.project_id, session_id="scoped-session", timestamp=start, created_at=start, environment_id=first_environment.id, registration_id=first_registration.id)
        second_trace = Trace(id="other-trace", project_id=client.project_id, session_id="other-session", timestamp=start, created_at=start, environment_id=second_environment.id, registration_id=second_registration.id)
        db.add_all([first_environment, second_environment, first_definition, second_definition, first_registration, second_registration, first_trace, second_trace])
        db.flush()
        db.add_all([
            Score(id="scoped-score", project_id=client.project_id, trace_id=first_trace.id, name="quality", value=1.0, created_at=start),
            Score(id="other-score", project_id=client.project_id, trace_id=second_trace.id, name="quality", value=0.0, created_at=start),
            MeshInteraction(id="scoped-interaction", project_id=client.project_id, trace_id=first_trace.id, source="support", target="tool", created_at=start),
            MeshInteraction(id="other-interaction", project_id=client.project_id, trace_id=second_trace.id, source="sales", target="tool", created_at=start),
        ])
        db.commit()

    params = {"environment_id": "environment-first", "registration_id": "registration-first", "from": "2026-08-23T09:00:00Z", "to": "2026-08-23T11:00:00Z"}
    assert [trace["id"] for trace in client.get("/api/public/traces", params=params, headers=_auth()).json()["traces"]] == ["scoped-trace"]
    assert client.get("/api/public/metrics", params=params, headers=_auth()).json()[0]["count"] == 1
    assert [session["session_id"] for session in client.get("/api/public/sessions", params=params, headers=_auth()).json()] == ["scoped-session"]
    assert [score["id"] for score in client.get("/api/public/scores", params=params, headers=_auth()).json()] == ["scoped-score"]
    assert client.get("/api/public/quality/overview", params=params, headers=_auth()).json()["scored_count"] == 1
    assert client.get("/api/public/mesh/catalog", params=params, headers=_auth()).json()["summary"]["registrations"] == 1
    assert client.get("/api/public/mesh/graph", params=params, headers=_auth()).json()["nodes"] == [{"id": "support", "label": "support"}, {"id": "tool", "label": "tool"}]
    assert client.get("/api/public/traces", params={**params, "from": "2026-08-23T11:00:01Z"}, headers=_auth()).json()["traces"] == []


def test_ingest_trace_full_lifecycle(client):
    tid = "trace_" + uuid.uuid4().hex[:10]
    payload = {
        "events": [
            {
                "id": uuid.uuid4().hex,
                "type": "observation-start",
                "timestamp": "2026-08-23T10:00:00.000Z",
                "body": {
                    "id": tid,
                    "trace_id": tid,
                    "type": "TRACE",
                    "name": "my-agent",
                    "start_time": "2026-08-23T10:00:00.000Z",
                    "input": {"message": "hola"},
                    "environment": "prod",
                    "session_id": "s1",
                },
            },
            {
                "id": uuid.uuid4().hex,
                "type": "observation-end",
                "timestamp": "2026-08-23T10:00:02.000Z",
                "body": {"id": tid, "type": "TRACE", "end_time": "2026-08-23T10:00:02.000Z", "output": {"content": "resposta final"}},
            },
        ]
    }
    r = client.post("/api/public/ingestion", json=payload, headers=_auth())
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "accepted"
    assert body["events_accepted"] == 2


def test_ingest_trace_lifecycle_across_separate_batches(client):
    tid = "trace_" + uuid.uuid4().hex[:10]
    start = {
        "events": [{"id": uuid.uuid4().hex, "type": "observation-start", "body": {
            "id": tid, "trace_id": tid, "type": "TRACE", "name": "separate-batches",
            "start_time": "2026-08-23T10:00:00.000Z",
        }}]
    }
    end = {
        "events": [{"id": uuid.uuid4().hex, "type": "observation-end", "body": {
            "id": tid, "trace_id": tid, "type": "TRACE",
            "end_time": "2026-08-23T10:00:02.500Z", "output": "complete",
        }}]
    }

    assert client.post("/api/public/ingestion", json=start, headers=_auth()).status_code == 202
    assert client.post("/api/public/ingestion", json=end, headers=_auth()).status_code == 202

    trace = client.get(f"/api/public/traces/{tid}", headers=_auth()).json()
    assert trace["end_time"] == "2026-08-23T10:00:02.500000+00:00", trace
    assert trace["latency_ms"] == 2500.0, trace
    assert trace["output"] == "complete"


def test_ingestion_is_accepted_and_persisted_as_a_job(client):
    response = client.post(
        "/api/public/ingestion",
        json={"events": [{"id": "event_queued", "type": "observation-start", "body": {"id": "trace_queued"}}]},
        headers=_auth(),
    )

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"

    with client.session_factory() as db:
        job = db.get(IngestionJob, response.json()["job_id"])
        assert job is not None
        assert job.project_id == client.project_id
        assert job.payload["events"][0]["id"] == "event_queued"


def test_ingestion_dispatch_uses_local_worker_by_default(monkeypatch):
    monkeypatch.setattr(ingestion_queue, "inngest_dispatch_configured", lambda: False)
    tasks = BackgroundTasks()

    assert ingestion_queue.schedule_ingestion_job(tasks, object, "job_1") == "local"
    assert tasks.tasks[0].func is ingestion_queue.process_ingestion_job


def test_ingestion_dispatch_uses_inngest_when_configured(monkeypatch):
    monkeypatch.setattr(ingestion_queue, "inngest_dispatch_configured", lambda: True)
    tasks = BackgroundTasks()

    assert ingestion_queue.schedule_ingestion_job(tasks, object, "job_1") == "inngest"
    assert tasks.tasks[0].func is ingestion_queue.send_ingestion_job_to_inngest


def test_ingest_generation_and_query_detail(client):
    trace_id = "trace_" + uuid.uuid4().hex[:8]
    llm_id = "obs_llm_" + uuid.uuid4().hex[:8]
    payload = {
        "events": [
            {"id": uuid.uuid4().hex, "type": "observation-start", "body": {"id": trace_id, "type": "TRACE", "name": "my-agent", "start_time": "2026-08-23T10:00:00.000Z"}},
            {
                "id": uuid.uuid4().hex,
                "type": "observation-start",
                "body": {"id": llm_id, "trace_id": trace_id, "type": "llm_call", "name": "gpt-4o", "start_time": "2026-08-23T10:00:00.100Z"},
            },
            {"id": uuid.uuid4().hex, "type": "observation-end", "body": {"id": llm_id, "output": {"response": "oi"}, "usage": {"input_tokens": 8, "output_tokens": 2}}},
            {"id": uuid.uuid4().hex, "type": "observation-end", "body": {"id": trace_id, "output": "resposta"}},
        ]
    }
    r = client.post("/api/public/ingestion", json=payload, headers=_auth())
    assert r.status_code == 202

    q = client.get(f"/api/public/traces/{trace_id}", headers=_auth())
    assert q.status_code == 200
    trace = q.json()
    assert trace["observations"]
    assert any(o["type"] == "GENERATION" for o in trace["observations"])


def test_traces_pagination(client):
    r = client.get("/api/public/traces", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert "traces" in body
    assert "total" in body
    assert client.get("/api/public/traces?page=-1", headers=_auth()).status_code == 422
    assert client.get("/api/public/traces?per_page=101", headers=_auth()).status_code == 422


def test_ingest_batch_error_reported(client):
    payload = {
        "events": [
            {"id": uuid.uuid4().hex, "type": "observation-start", "body": {"id": "trace_xyz", "type": "TRACE", "start_time": "bad-time"}}
        ]
    }
    r = client.post("/api/public/ingestion", json=payload, headers=_auth())
    assert r.status_code == 202
    assert r.json()["events_accepted"] == 1


def test_approval_lifecycle(client):
    created = client.post(
        "/api/public/approvals",
        json={"run_id": "run_ap1", "approval_id": "apr_abc", "tool_name": "send_email", "tool_arguments": {"to": "x"}, "requirement": "confirmation"},
        headers=_auth(),
    )
    assert created.status_code == 200
    assert created.json()["status"] == "pending"
    assert created.json()["tool_call_id"] == ""

    listed = client.get("/api/public/approvals?status=pending", headers=_auth())
    assert listed.status_code == 200
    assert any(a["approval_id"] == "apr_abc" for a in listed.json())

    resolved = client.post(
        "/api/public/approvals/apr_abc/resolve",
        json={"action": "approve"},
        headers=_auth(),
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "approved"
    assert resolved.json()["resolved_by"] == "admin-key-00000000000000000000001"
    assert resolved.json()["confirmation"] is True

    # double resolve rejected (already resolved)
    again = client.post(
        "/api/public/approvals/apr_abc/resolve",
        json={"action": "reject"},
        headers=_auth(),
    )
    assert again.status_code == 409

    pending = client.get("/api/public/approvals?status=pending", headers=_auth())
    assert not any(a["approval_id"] == "apr_abc" for a in pending.json())


def test_schedule_policy_evaluates_project_and_registration_restrictions_and_audits(client):
    policy = {
        "decisions": {
            "schedule.read": "allow",
            "schedule.create": "require_approval",
            "schedule.update": "allow",
            "schedule.cancel": "deny",
        },
        "restrictions": {
            "max_active_schedules": 2,
            "allowed_types": ["cron"],
            "min_interval_seconds": 300,
        },
    }
    updated = client.put("/api/public/schedule-policies/project", json=policy, headers=_auth())
    assert updated.status_code == 200
    assert updated.json() == policy

    denied = client.post(
        "/api/public/schedule-policies/decisions",
        json={"action": "schedule.create", "schedule_type": "interval", "interval_seconds": 60, "active_schedule_count": 2},
        headers=_auth_as("pk-editor"),
    )
    assert denied.status_code == 200
    assert denied.json()["decision"] == "deny"
    assert denied.json()["reasons"] == ["schedule_type_not_allowed", "max_active_schedules_reached", "interval_below_minimum"]
    assert denied.json()["approval_id"] is None

    approval_required = client.post(
        "/api/public/schedule-policies/decisions",
        json={"action": "schedule.create", "schedule_type": "cron", "active_schedule_count": 1, "schedule_id": "schedule-1"},
        headers=_auth_as("pk-editor"),
    )
    assert approval_required.status_code == 200
    assert approval_required.json()["decision"] == "require_approval"
    approval_id = approval_required.json()["approval_id"]
    assert approval_id

    with client.session_factory() as db:
        approval = db.query(Approval).filter_by(project_id=client.project_id, approval_id=approval_id).one()
        audit = db.query(PolicyDecisionAudit).filter_by(project_id=client.project_id, approval_id=approval_id).one()
        assert approval.tool_name == "schedule.create"
        assert approval.metadata_field["source"] == "schedule_policy"
        assert audit.decision == "require_approval"
        assert audit.reasons == []

    audit_log = client.get("/api/public/schedule-policies/decisions", headers=_auth_as("pk-read-only"))
    assert audit_log.status_code == 200
    assert audit_log.json()[0]["approval_id"] == approval_id
    assert audit_log.json()[0]["action"] == "schedule.create"

    registration = client.post("/api/public/mesh/environments", json={"slug": "staging", "name": "Staging"}, headers=_auth_as("pk-editor")).json()
    definition = client.post("/api/public/mesh/definitions", json={"key": "worker", "kind": "agent", "name": "Worker", "version": "1"}, headers=_auth_as("pk-editor")).json()
    registration = client.post("/api/public/mesh/registrations", json={"environment_id": registration["id"], "definition_id": definition["id"]}, headers=_auth_as("pk-editor")).json()
    override = client.put(
        f"/api/public/schedule-policies/registrations/{registration['id']}",
        json={"decisions": {"schedule.cancel": "allow"}, "restrictions": {"max_active_schedules": 5}},
        headers=_auth(),
    )
    assert override.status_code == 200

    allowed = client.post(
        "/api/public/schedule-policies/decisions",
        json={"action": "schedule.cancel", "registration_id": registration["id"]},
        headers=_auth_as("pk-editor"),
    )
    assert allowed.status_code == 200
    assert allowed.json()["decision"] == "allow"


def test_schedule_policy_rejects_unknown_actions_invalid_restrictions_and_foreign_registration(client):
    assert client.put(
        "/api/public/schedule-policies/project",
        json={"decisions": {"schedule.delete": "allow"}},
        headers=_auth(),
    ).status_code == 422
    assert client.put(
        "/api/public/schedule-policies/project",
        json={"restrictions": {"min_interval_seconds": 0}},
        headers=_auth(),
    ).status_code == 422
    assert client.post(
        "/api/public/schedule-policies/decisions",
        json={"action": "schedule.read", "registration_id": "missing"},
        headers=_auth_as("pk-editor"),
    ).status_code == 404


def test_approval_includes_trace_derived_runtime_context(client):
    environment = client.post(
        "/api/public/mesh/environments",
        json={"slug": "staging", "name": "Staging"},
        headers=_auth_as("pk-editor"),
    ).json()
    definition = client.post(
        "/api/public/mesh/definitions",
        json={"key": "support", "kind": "agent", "name": "Support Agent", "version": "2.1.0"},
        headers=_auth_as("pk-editor"),
    ).json()
    registration = client.post(
        "/api/public/mesh/registrations",
        json={"environment_id": environment["id"], "definition_id": definition["id"]},
        headers=_auth_as("pk-editor"),
    ).json()
    with client.session_factory() as db:
        db.add(
            Trace(
                id="approval-context-trace",
                project_id=client.project_id,
                name="Customer support handoff",
                session_id="support-session",
                environment="staging",
                environment_id=environment["id"],
                registration_id=registration["id"],
                definition_id=definition["id"],
                definition_version="2.1.0",
            )
        )
        db.commit()

    response = client.post(
        "/api/public/approvals",
        json={"run_id": "approval-context-trace", "approval_id": "contextual-approval", "tool_name": "reply"},
        headers=_auth(),
    )

    assert response.status_code == 200
    assert response.json()["trace_context"] == {
        "trace": {"id": "approval-context-trace", "name": "Customer support handoff"},
        "session_id": "support-session",
        "environment": {"id": environment["id"], "slug": "staging", "name": "Staging"},
        "registration": {"id": registration["id"]},
        "definition": {"id": definition["id"], "key": "support", "name": "Support Agent", "version": "2.1.0"},
    }


def test_sessions_are_grouped_from_traces(client):
    payload = {"events": [
        {"id": uuid.uuid4().hex, "type": "observation-start", "body": {"id": "trace_session", "type": "TRACE", "name": "chat", "session_id": "session-1", "user_id": "user-7", "start_time": "2026-08-23T10:00:00.000Z"}},
        {"id": uuid.uuid4().hex, "type": "observation-end", "body": {"id": "trace_session", "type": "TRACE", "end_time": "2026-08-23T10:00:01.000Z"}},
    ]}
    assert client.post("/api/public/ingestion", json=payload, headers=_auth()).status_code == 202

    sessions = client.get("/api/public/sessions", headers=_auth())
    assert sessions.status_code == 200
    assert sessions.json()[0]["session_id"] == "session-1"
    assert sessions.json()[0]["trace_count"] == 1

    detail = client.get("/api/public/sessions/session-1", headers=_auth())
    assert detail.status_code == 200
    assert detail.json()["user_id"] == "user-7"


def test_score_configs_and_scores(client):
    trace = {"events": [{"id": uuid.uuid4().hex, "type": "observation-start", "body": {"id": "trace_score", "trace_id": "trace_score", "type": "TRACE", "name": "eval"}}, {"id": uuid.uuid4().hex, "type": "observation-end", "body": {"id": "trace_score", "trace_id": "trace_score", "type": "TRACE"}}]}
    assert client.post("/api/public/ingestion", json=trace, headers=_auth()).status_code == 202
    config = client.post("/api/public/score-configs", json={"name": "correctness", "description": "Answer quality"}, headers=_auth())
    assert config.status_code == 200
    score = client.post("/api/public/scores", json={"trace_id": "trace_score", "name": "correctness", "value": 0.9, "source": "EVAL"}, headers=_auth())
    assert score.status_code == 200
    assert score.json()["value"] == 0.9
    assert client.get("/api/public/scores?trace_id=trace_score", headers=_auth()).json()[0]["name"] == "correctness"


def test_eval_run_publishes_scores_and_aggregates_results(client):
    with client.session_factory() as db:
        db.add_all([
            Trace(id="trace_eval_pass", project_id=client.project_id, name="eval", output="Hello World"),
            Trace(id="trace_eval_fail", project_id=client.project_id, name="eval", output="nope"),
        ])
        db.commit()

    dataset = client.post("/api/public/eval-datasets", json={"name": "answers", "items": [{"trace_id": "trace_eval_pass", "expected_output": " hello world "}, {"trace_id": "trace_eval_fail", "expected_output": "expected"}]}, headers=_auth())
    assert dataset.status_code == 200
    run = client.post("/api/public/eval-runs", json={"dataset_id": dataset.json()["id"], "score_name": "correctness"}, headers=_auth())
    assert run.status_code == 200
    assert run.json()["passed_cases"] == 1
    assert run.json()["average_score"] == 0.5
    assert run.json()["aggregates"] == [{"name": "correctness", "average": 0.5, "count": 2}]
    assert [result["value"] for result in run.json()["results"]] == [1.0, 0.0]

    scores = client.get("/api/public/scores?trace_id=trace_eval_pass", headers=_auth()).json()
    assert scores[0]["name"] == "correctness"
    assert scores[0]["source"] == "EVAL"
    overview = client.get("/api/public/quality/overview", headers=_auth()).json()
    assert overview["numeric_count"] == 2
    assert overview["average"] == 0.5


def test_read_only_key_can_query_but_cannot_mutate(client):
    assert client.get("/api/public/traces", headers=_auth_as("pk-read-only")).status_code == 200
    response = client.post("/api/public/ingestion", json={"events": []}, headers=_auth_as("pk-read-only"))
    assert response.status_code == 403


def test_ingestion_metrics_are_project_scoped_and_read_only_accessible(client):
    from datetime import datetime, timedelta, timezone

    with client.session_factory() as db:
        now = datetime.now(timezone.utc)
        db.add_all(
            [
                IngestionJob(project_id=client.project_id, payload={"events": []}, status="pending"),
                IngestionJob(project_id=client.project_id, payload={"events": []}, status="processing"),
                IngestionJob(
                    project_id=client.project_id,
                    payload={"events": []},
                    status="completed",
                    attempts=2,
                    created_at=now - timedelta(seconds=2),
                    completed_at=now,
                ),
                IngestionJob(project_id=client.project_id, payload={"events": []}, status="failed", attempts=3),
            ]
        )
        db.commit()

    response = client.get("/api/public/observability/ingestion-metrics", headers=_auth_as("pk-read-only"))

    assert response.status_code == 200
    assert response.json()["pending"] == 1
    assert response.json()["processing"] == 1
    assert response.json()["completed"] == 1
    assert response.json()["failed"] == 1
    assert response.json()["retries"] == 3
    assert response.json()["latency_ms"]["average"] == pytest.approx(2000)


def test_ingestion_retries_and_failures_create_sanitized_alerts(client, monkeypatch):
    monkeypatch.setattr(ingestion_queue.IngestionService, "process_batch", lambda *_: (_ for _ in ()).throw(RuntimeError("email person@example.com failed")))
    with client.session_factory() as db:
        job = IngestionJob(project_id=client.project_id, payload={"events": []})
        db.add(job)
        db.commit()
        job_id = job.id

    assert ingestion_queue.process_ingestion_job(client.session_factory, job_id) is False
    assert ingestion_queue.process_ingestion_job(client.session_factory, job_id) is False
    assert ingestion_queue.process_ingestion_job(client.session_factory, job_id) is False
    alerts = client.get("/api/public/alerts", headers=_auth()).json()

    assert {alert["event_type"] for alert in alerts} == {"ingestion_failed", "ingestion_retry"}
    assert all("person@example.com" not in alert["message"] for alert in alerts)
    assert all(alert["ingestion_job_id"] == job_id for alert in alerts)


def test_framework_alerts_are_persisted_project_scoped_and_require_editor(client):
    payload = {
        "source": "guardrail",
        "event_type": "policy_blocked",
        "severity": "warning",
        "message": "A framework guardrail blocked a tool invocation.",
        "trace_id": "guardrail-trace",
        "metadata": {"rule": "external_execution"},
    }

    denied = client.post("/api/public/alerts", json=payload, headers=_auth_as("pk-read-only"))
    created = client.post("/api/public/alerts", json=payload, headers=_auth_as("pk-editor"))
    listed = client.get("/api/public/alerts?source=guardrail", headers=_auth_as("pk-read-only"))

    assert denied.status_code == 403
    assert created.status_code == 201
    assert created.json()["source"] == "guardrail"
    assert created.json()["metadata"] == {"rule": "external_execution"}
    assert [alert["id"] for alert in listed.json()] == [created.json()["id"]]


def test_framework_alerts_apply_project_pii_redaction(client):
    assert client.put("/api/public/privacy/config", json={"enabled": True}, headers=_auth()).status_code == 200

    response = client.post(
        "/api/public/alerts",
        json={
            "source": "hitl",
            "event_type": "approval_required",
            "message": "Approval requested for person@example.com.",
            "metadata": {"operator": "person@example.com"},
        },
        headers=_auth_as("pk-editor"),
    )

    assert response.status_code == 201
    assert response.json()["message"] == "Approval requested for [REDACTED_EMAIL]."
    assert response.json()["metadata"]["operator"] == "[REDACTED_EMAIL]"


def test_managed_alert_rules_can_be_created_updated_listed_and_deleted(client):
    payload = {
        "name": "Permanent ingestion failures",
        "source": "ingestion",
        "event_type": "ingestion_failed",
        "severity": "error",
    }

    denied = client.post("/api/public/alert-rules", json=payload, headers=_auth_as("pk-read-only"))
    created = client.post("/api/public/alert-rules", json=payload, headers=_auth_as("pk-editor"))

    assert denied.status_code == 403
    assert created.status_code == 201
    assert created.json()["enabled"] is True
    rule_id = created.json()["id"]
    assert client.post("/api/public/alert-rules", json=payload, headers=_auth_as("pk-editor")).status_code == 409

    updated = client.patch(
        f"/api/public/alert-rules/{rule_id}",
        json={"enabled": False, "severity": "warning"},
        headers=_auth_as("pk-editor"),
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert updated.json()["severity"] == "warning"
    assert [rule["id"] for rule in client.get("/api/public/alert-rules", headers=_auth_as("pk-read-only")).json()] == [rule_id]

    deleted = client.delete(f"/api/public/alert-rules/{rule_id}", headers=_auth_as("pk-editor"))
    assert deleted.status_code == 204
    assert client.get("/api/public/alert-rules", headers=_auth()).json() == []


def test_alert_rule_taxonomy_and_match_validation(client):
    taxonomy = client.get("/api/public/alert-rules/taxonomy", headers=_auth_as("pk-read-only"))

    assert taxonomy.status_code == 200
    assert taxonomy.json()["ingestion"] == ["ingestion_retry", "ingestion_failed"]
    assert client.post(
        "/api/public/alert-rules",
        json={"name": "All signals"},
        headers=_auth_as("pk-editor"),
    ).status_code == 201
    assert client.post(
        "/api/public/alert-rules",
        json={"name": "Guardrail signals", "source": "guardrail"},
        headers=_auth_as("pk-editor"),
    ).status_code == 201
    assert client.post(
        "/api/public/alert-rules",
        json={"name": "All policy blocks", "event_type": "policy_blocked"},
        headers=_auth_as("pk-editor"),
    ).status_code == 201

    incompatible = client.post(
        "/api/public/alert-rules",
        json={"name": "Bad pair", "source": "ingestion", "event_type": "policy_blocked"},
        headers=_auth_as("pk-editor"),
    )
    unknown = client.post(
        "/api/public/alert-rules",
        json={"name": "Unknown source", "source": "unknown"},
        headers=_auth_as("pk-editor"),
    )

    assert incompatible.status_code == 422
    assert unknown.status_code == 422

    rule_id = client.post(
        "/api/public/alert-rules",
        json={"name": "Change source", "source": "guardrail", "event_type": "policy_blocked"},
        headers=_auth_as("pk-editor"),
    ).json()["id"]
    update = client.patch(
        f"/api/public/alert-rules/{rule_id}",
        json={"source": "ingestion"},
        headers=_auth_as("pk-editor"),
    )

    assert update.status_code == 422

    wildcard_update = client.patch(
        f"/api/public/alert-rules/{rule_id}",
        json={"source": None, "event_type": None},
        headers=_auth_as("pk-editor"),
    )
    assert wildcard_update.status_code == 200
    assert wildcard_update.json()["source"] is None
    assert wildcard_update.json()["event_type"] is None


def test_matching_alert_rule_classifies_new_alerts(client):
    assert client.post(
        "/api/public/alert-rules",
        json={"name": "Escalate policy blocks", "source": "guardrail", "event_type": "policy_blocked", "severity": "error"},
        headers=_auth_as("pk-editor"),
    ).status_code == 201

    matched = client.post(
        "/api/public/alerts",
        json={"source": "guardrail", "event_type": "policy_blocked", "severity": "info", "message": "Blocked"},
        headers=_auth_as("pk-editor"),
    )
    unmatched = client.post(
        "/api/public/alerts",
        json={"source": "guardrail", "event_type": "policy_allowed", "severity": "info", "message": "Allowed"},
        headers=_auth_as("pk-editor"),
    )

    assert matched.status_code == 201
    assert matched.json()["severity"] == "error"
    assert unmatched.status_code == 201
    assert unmatched.json()["severity"] == "info"


def test_alert_lifecycle_is_project_scoped_and_rejects_transitions_after_resolution(client):
    created = client.post(
        "/api/public/alerts",
        json={"source": "guardrail", "event_type": "policy_blocked", "message": "Blocked"},
        headers=_auth_as("pk-editor"),
    )
    alert_id = created.json()["id"]
    assert created.json()["status"] == "open"

    acknowledged = client.patch(
        f"/api/public/alerts/{alert_id}",
        json={"status": "acknowledged"},
        headers=_auth_as("pk-editor"),
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"
    assert acknowledged.json()["acknowledged_at"]

    resolved = client.patch(
        f"/api/public/alerts/{alert_id}",
        json={"status": "resolved", "resolved_by": "alice"},
        headers=_auth_as("pk-editor"),
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolved_by"] == "alice"
    assert resolved.json()["resolved_at"]
    assert client.get("/api/public/alerts?status=resolved", headers=_auth()).json()[0]["id"] == alert_id
    assert client.patch(
        f"/api/public/alerts/{alert_id}",
        json={"status": "acknowledged"},
        headers=_auth_as("pk-editor"),
    ).status_code == 409


def test_editor_key_can_ingest_but_cannot_run_retention_cleanup(client):
    assert client.post("/api/public/ingestion", json={"events": []}, headers=_auth_as("pk-editor")).status_code == 202
    response = client.post("/api/public/traces/cleanup", headers=_auth_as("pk-editor"))
    assert response.status_code == 403


def test_governance_settings_are_project_scoped_and_read_only_accessible(client):
    with client.session_factory() as db:
        other_project = Project(
            id="governance-other-project",
            organization_id=db.get(Project, client.project_id).organization_id,
            name="Other governance project",
            retention_days=7,
        )
        db.add_all(
            [
                other_project,
                ApiKey(
                    project_id=other_project.id,
                    public_key="pk-governance-other",
                    hashed_secret_key="ef260e9aa3c673af240d17a2660480361a8e081d1ffeca2a5ed0e3219fc18567",
                    display_secret_key="dev",
                    role="read_only",
                ),
            ]
        )
        db.commit()

    response = client.get("/api/public/governance/settings", headers=_auth_as("pk-read-only"))
    other_response = client.get("/api/public/governance/settings", headers=_auth_as("pk-governance-other"))

    assert response.status_code == 200
    assert response.json() == {"retention_days": 30, "roles": {"read_only": ["read"], "editor": ["read", "write"], "admin": ["read", "write", "manage"]}}
    assert other_response.json() == {"retention_days": 7, "roles": {"read_only": ["read"], "editor": ["read", "write"], "admin": ["read", "write", "manage"]}}


def test_governance_settings_can_only_be_updated_by_admin(client):
    denied = client.put(
        "/api/public/governance/settings",
        json={"retention_days": 90, "roles": {"read_only": ["read"], "editor": ["read", "write"], "admin": ["read", "write", "manage"]}},
        headers=_auth_as("pk-editor"),
    )
    updated = client.put(
        "/api/public/governance/settings",
        json={"retention_days": 90, "roles": {"read_only": ["read"], "editor": ["read", "write"], "admin": ["read", "write", "manage"]}},
        headers=_auth(),
    )

    assert denied.status_code == 403
    assert updated.status_code == 200
    assert updated.json() == {"retention_days": 90, "roles": {"read_only": ["read"], "editor": ["read", "write"], "admin": ["read", "write", "manage"]}}
    assert client.get("/api/public/governance/settings", headers=_auth_as("pk-read-only")).json() == {"retention_days": 90, "roles": {"read_only": ["read"], "editor": ["read", "write"], "admin": ["read", "write", "manage"]}}


def test_governance_settings_validate_retention_days(client):
    response = client.put(
        "/api/public/governance/settings",
        json={"retention_days": 0},
        headers=_auth(),
    )

    assert response.status_code == 422


def test_governance_role_permissions_are_persisted_and_validated(client):
    roles = {"read_only": ["read"], "editor": ["read"], "admin": ["read", "write", "manage"]}

    response = client.put(
        "/api/public/governance/settings",
        json={"retention_days": 30, "roles": roles},
        headers=_auth(),
    )

    assert response.status_code == 200
    assert response.json()["roles"] == roles
    assert client.get("/api/public/governance/settings", headers=_auth()).json()["roles"] == roles
    assert client.put(
        "/api/public/governance/settings",
        json={"retention_days": 30, "roles": {"editor": ["read"]}},
        headers=_auth(),
    ).status_code == 422


def test_privacy_config_rejects_invalid_custom_patterns(client):
    response = client.put(
        "/api/public/privacy/config",
        json={"enabled": True, "custom_patterns": ["["]},
        headers=_auth(),
    )

    assert response.status_code == 422


def test_trace_export_supports_json_and_csv(client):
    trace_id = "trace_export"
    payload = {"events": [
        {"id": uuid.uuid4().hex, "type": "observation-start", "body": {"id": trace_id, "trace_id": trace_id, "type": "TRACE", "name": "exportable"}},
        {"id": uuid.uuid4().hex, "type": "observation-end", "body": {"id": trace_id, "trace_id": trace_id, "type": "TRACE", "output": {"answer": "yes"}}},
    ]}
    assert client.post("/api/public/ingestion", json=payload, headers=_auth()).status_code == 202

    json_export = client.get("/api/public/traces/export?format=json", headers=_auth())
    assert json_export.status_code == 200
    assert any(trace["id"] == trace_id for trace in json_export.json())
    assert json_export.headers["content-type"].startswith("application/json")

    csv_export = client.get("/api/public/traces/export?format=csv", headers=_auth())
    assert csv_export.status_code == 200
    assert trace_id in csv_export.text
    assert csv_export.headers["content-type"].startswith("text/csv")


def test_trace_export_is_bounded_stable_and_project_scoped(client):
    from datetime import datetime, timezone

    with client.session_factory() as db:
        organization_id = db.get(Project, client.project_id).organization_id
        other_project = Project(id="export-other-project", organization_id=organization_id, name="Other export project")
        db.add_all(
            [
                Trace(id="export-current", project_id=client.project_id, name="current", timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc), created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
                Trace(id="export-other", project_id=other_project.id, name="other", timestamp=datetime(2026, 1, 3, tzinfo=timezone.utc), created_at=datetime(2026, 1, 3, tzinfo=timezone.utc)),
                other_project,
            ]
        )
        db.commit()

    exported = client.get("/api/public/traces/export?format=json&limit=1", headers=_auth())

    assert exported.status_code == 200
    assert exported.headers["content-disposition"] == "attachment; filename=traces.json"
    assert exported.json() == [
        {
            "id": "export-current",
            "name": "current",
            "timestamp": "2026-01-02T00:00:00+00:00",
            "start_time": None,
            "end_time": None,
            "session_id": None,
            "environment": None,
            "input": None,
            "output": None,
            "latency_ms": None,
                "usage": None,
                "cost": None,
                "cost_currency": None,
                "cost_source": None,
            "observations": [],
            "scores": [],
        }
    ]
    assert client.get("/api/public/traces/export?format=json&limit=1001", headers=_auth()).status_code == 422


def test_api_key_rate_limit_rejects_abuse(client):
    class AllowTwoRequests:
        def __init__(self):
            self.requests = 0

        def check(self, _key):
            self.requests += 1
            return self.requests <= 2, 60

    previous_limiter = getattr(app_main.app.state, "rate_limiter", None)
    app_main.app.state.rate_limiter = AllowTwoRequests()
    try:
        assert client.get("/api/public/traces", headers=_auth()).status_code == 200
        assert client.get("/api/public/traces", headers=_auth()).status_code == 200
        limited = client.get("/api/public/traces", headers=_auth())
    finally:
        app_main.app.state.rate_limiter = previous_limiter

    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "60"
    assert limited.json() == {"detail": "Rate limit exceeded"}


def test_admin_cleanup_removes_expired_project_traces(client):
    from datetime import datetime, timedelta, timezone

    with client.session_factory() as db:
        project = db.get(Project, client.project_id)
        project.retention_days = 1
        db.add(
            Trace(
                id="trace_expired",
                project_id=client.project_id,
                name="expired",
                created_at=datetime.now(timezone.utc) - timedelta(days=2),
            )
        )
        db.commit()

    response = client.post("/api/public/traces/cleanup", headers=_auth())
    assert response.status_code == 200
    assert response.json()["deleted"] == 1
    assert client.get("/api/public/traces/trace_expired", headers=_auth()).status_code == 404
    assert client.get("/api/public/traces", headers=_auth()).json()["total"] == 0


def test_privacy_redaction_happens_before_the_ingestion_job_is_persisted(client):
    configuration = client.put(
        "/api/public/privacy/config",
        json={"enabled": True},
        headers=_auth(),
    )
    assert configuration.status_code == 200

    response = client.post(
        "/api/public/ingestion",
        json={
            "events": [
                {
                    "id": "redaction-event",
                    "type": "observation-start",
                    "body": {
                        "id": "redaction-trace",
                        "trace_id": "redaction-trace",
                        "type": "TRACE",
                        "user_id": "subject-1",
                        "input": {"email": "person@example.com"},
                    },
                }
            ]
        },
        headers=_auth(),
    )
    assert response.status_code == 202

    with client.session_factory() as db:
        job = db.get(IngestionJob, response.json()["job_id"])
        assert job.payload["events"][0]["body"]["input"]["email"] == "[REDACTED_EMAIL]"


def test_lgpd_export_and_delete_are_tenant_isolated_and_audited(client):
    trace_id = "subject-trace"
    payload = {
        "events": [
            {
                "id": "subject-start",
                "type": "observation-start",
                "body": {
                    "id": trace_id,
                    "trace_id": trace_id,
                    "type": "TRACE",
                    "user_id": "subject-1",
                    "name": "chat",
                },
            },
            {
                "id": "subject-end",
                "type": "observation-end",
                "body": {"id": trace_id, "trace_id": trace_id, "type": "TRACE", "output": "answer"},
            },
        ]
    }
    assert client.post("/api/public/ingestion", json=payload, headers=_auth()).status_code == 202
    assert client.post(
        "/api/public/approvals",
        json={"run_id": trace_id, "approval_id": "subject-approval", "tool_name": "reply"},
        headers=_auth(),
    ).status_code == 200
    assert client.post(
        "/api/public/scores",
        json={"trace_id": trace_id, "name": "quality", "value": 1},
        headers=_auth(),
    ).status_code == 200

    exported = client.get("/api/public/users/subject-1/export", headers=_auth())
    assert exported.status_code == 200
    assert [trace["id"] for trace in exported.json()["traces"]] == [trace_id]
    assert exported.json()["approvals"][0]["approval_id"] == "subject-approval"
    assert exported.json()["scores"][0]["trace_id"] == trace_id

    with client.session_factory() as db:
        other_project = Project(id="other-project", organization_id=db.get(Project, client.project_id).organization_id, name="Other")
        db.add(other_project)
        db.add(
            ApiKey(
                project_id=other_project.id,
                public_key="pk-other",
                hashed_secret_key="ef260e9aa3c673af240d17a2660480361a8e081d1ffeca2a5ed0e3219fc18567",
                display_secret_key="dev",
                role="admin",
            )
        )
        db.add(Trace(id="other-subject-trace", project_id=other_project.id, name="other", user_id="subject-1"))
        db.commit()

    assert client.get("/api/public/users/subject-1/export", headers=_auth_as("pk-other")).status_code == 200
    assert client.get("/api/public/users/subject-1/export", headers=_auth_as("pk-other")).json()["traces"][0]["id"] == "other-subject-trace"

    deleted = client.delete("/api/public/users/subject-1", headers=_auth())
    assert deleted.status_code == 200
    assert deleted.json()["deleted"]["traces"] == 1
    assert client.get(f"/api/public/traces/{trace_id}", headers=_auth()).status_code == 404
    assert client.get("/api/public/users/subject-1/export", headers=_auth_as("pk-other")).status_code == 200

    audit = client.get("/api/public/privacy/audit", headers=_auth())
    assert audit.status_code == 200
    assert [record["action"] for record in audit.json()] == ["delete", "export"]


def test_estimate_cost_with_known_model_and_tokens(client):
    with client.session_factory() as db:
        db.add(ModelPrice(
            id="mp1", model_key="gpt-4o-mini", provider="openai",
            input_price_per_1k=0.00015, output_price_per_1k=0.0006, currency="USD",
        ))
        db.commit()

        result = estimate_cost(db, "gpt-4o-mini", input_tokens=1000, output_tokens=500)
        assert result is not None
        # 1000 input tokens = (1000/1000)*0.00015 = 0.00015
        # 500 output tokens = (500/1000)*0.0006 = 0.0003
        # total = 0.00045
        assert result["cost"] == 0.00045
        assert result["cost_currency"] == "USD"
        assert result["cost_source"] == "catalog_estimated"


def test_estimate_cost_returns_none_for_unknown_model(client):
    with client.session_factory() as db:
        result = estimate_cost(db, "nonexistent-model", input_tokens=100, output_tokens=50)
        assert result is None


def test_estimate_cost_returns_none_without_tokens(client):
    with client.session_factory() as db:
        db.add(ModelPrice(
            id="mp2", model_key="gpt-4o", provider="openai",
            input_price_per_1k=0.0025, output_price_per_1k=0.01, currency="USD",
        ))
        db.commit()

        result = estimate_cost(db, "gpt-4o", input_tokens=0, output_tokens=0)
        assert result is None


def test_ingestion_calls_estimation_and_stores_catalog_estimated(client):
    trace_id = "estimation-trace"
    payload = {
        "events": [
            {"id": "est-root", "type": "observation-start", "body": {"id": trace_id, "trace_id": trace_id, "type": "TRACE"}},
            {"id": "est-llm", "type": "observation-start", "body": {"id": "est-llm", "trace_id": trace_id, "parent_observation_id": trace_id, "type": "llm_call", "model": "gpt-4o-mini", "start_time": "2026-08-23T10:00:00.000Z"}},
            {"id": "est-llm-end", "type": "observation-end", "body": {"id": "est-llm", "trace_id": trace_id, "parent_observation_id": trace_id, "type": "llm_call", "model": "gpt-4o-mini", "usage": {"input_tokens": 2000, "output_tokens": 400}, "end_time": "2026-08-23T10:00:01.000Z"}},
            {"id": "est-root-end", "type": "observation-end", "body": {"id": trace_id, "trace_id": trace_id, "type": "TRACE", "end_time": "2026-08-23T10:00:02.000Z"}},
        ]
    }

    with client.session_factory() as db:
        db.add(ModelPrice(
            id="mp3", model_key="gpt-4o-mini", provider="openai",
            input_price_per_1k=0.00015, output_price_per_1k=0.0006, currency="USD",
        ))
        db.commit()

    assert client.post("/api/public/ingestion", json=payload, headers=_auth()).status_code == 202

    trace = client.get(f"/api/public/traces/{trace_id}", headers=_auth()).json()
    observations = {item["id"]: item for item in trace["observations"]}
    obs = observations["est-llm"]
    # 2000 input = 2 * 0.00015 = 0.0003; 400 output = 0.4 * 0.0006 = 0.00024; total = 0.00054
    assert obs["cost"] == 0.00054
    assert obs["cost_currency"] == "USD"
    assert obs["cost_source"] == "catalog_estimated"


def test_price_updater_adds_and_updates_prices(client):
    with client.session_factory() as db:
        db.add(ModelPrice(
            id="mp4", model_key="gpt-4o-mini", provider="openai",
            input_price_per_1k=0.00015, output_price_per_1k=0.0006, currency="USD",
        ))
        db.commit()

        count = check_and_update_prices(db)
        assert count > 0

        row = db.query(ModelPrice).filter(ModelPrice.model_key == "gpt-4o-mini").first()
        assert row is not None
        assert row.input_price_per_1k == 0.00015

        row2 = db.query(ModelPrice).filter(ModelPrice.model_key == "gpt-4o").first()
        assert row2 is not None
