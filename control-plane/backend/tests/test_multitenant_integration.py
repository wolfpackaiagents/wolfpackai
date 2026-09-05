"""End-to-end tenant isolation coverage for public control-plane APIs."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main as app_main
from app.core.database import get_db
from app.models.entities import ApiKey, Base, IngestionJob, Observation, Organization, Project, Score


SECRET_HASH = "ef260e9aa3c673af240d17a2660480361a8e081d1ffeca2a5ed0e3219fc18567"


@pytest.fixture()
def tenant_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    project_ids = {"alpha": uuid.uuid4().hex[:32], "bravo": uuid.uuid4().hex[:32]}

    with Session() as db:
        organization = Organization(id=uuid.uuid4().hex[:32], name="Tenant test organization")
        db.add(organization)
        for tenant, project_id in project_ids.items():
            db.add(Project(id=project_id, organization_id=organization.id, name=tenant))
            db.add(
                ApiKey(
                    project_id=project_id,
                    public_key=f"pk-{tenant}",
                    hashed_secret_key=SECRET_HASH,
                    display_secret_key="dev",
                    role="admin",
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
    with TestClient(app_main.app) as client:
        yield client, Session, project_ids
    app_main.app.state.ingestion_session_factory = previous_session_factory
    app_main.app.dependency_overrides.clear()


def _auth(tenant: str) -> dict[str, str]:
    return {"X-API-Key": f"pk-{tenant}:dev"}


def _trace_events(trace_id: str, session_id: str, user_id: str, name: str) -> dict:
    return {
        "events": [
            {
                "id": f"{trace_id}-start",
                "type": "observation-start",
                "body": {
                    "id": trace_id,
                    "trace_id": trace_id,
                    "type": "TRACE",
                    "name": name,
                    "session_id": session_id,
                    "user_id": user_id,
                    "input": {"tenant": name},
                    "start_time": "2026-08-23T10:00:00.000Z",
                },
            },
            {
                "id": f"{trace_id}-generation-start",
                "type": "observation-start",
                "body": {
                    "id": f"{trace_id}-generation",
                    "trace_id": trace_id,
                    "parent_observation_id": trace_id,
                    "type": "llm_call",
                    "name": "model",
                    "start_time": "2026-08-23T10:00:00.100Z",
                },
            },
            {
                "id": f"{trace_id}-generation-end",
                "type": "observation-end",
                "body": {"id": f"{trace_id}-generation", "output": {"answer": name}},
            },
            {
                "id": f"{trace_id}-end",
                "type": "observation-end",
                "body": {"id": trace_id, "trace_id": trace_id, "type": "TRACE", "output": {"answer": name}},
            },
        ]
    }


def test_multi_tenant_isolation_and_representative_flow(tenant_client):
    client, Session, project_ids = tenant_client
    alpha_trace = "alpha-trace"
    bravo_trace = "bravo-trace"
    user_id = "shared-subject"

    alpha_ingest = client.post(
        "/api/public/ingestion",
        json=_trace_events(alpha_trace, "shared-session", user_id, "alpha-agent"),
        headers=_auth("alpha"),
    )
    bravo_ingest = client.post(
        "/api/public/ingestion",
        json=_trace_events(bravo_trace, "shared-session", user_id, "bravo-agent"),
        headers=_auth("bravo"),
    )
    assert alpha_ingest.status_code == bravo_ingest.status_code == 202
    with Session() as db:
        assert db.get(IngestionJob, alpha_ingest.json()["job_id"]).status == "completed"
        assert db.get(IngestionJob, bravo_ingest.json()["job_id"]).status == "completed"

    alpha_detail = client.get(f"/api/public/traces/{alpha_trace}", headers=_auth("alpha"))
    assert alpha_detail.status_code == 200
    assert alpha_detail.json()["name"] == "alpha-agent"
    assert [item["type"] for item in alpha_detail.json()["observations"]] == ["TRACE", "GENERATION"]
    assert client.get(f"/api/public/traces/{alpha_trace}", headers=_auth("bravo")).status_code == 404
    assert client.get("/api/public/traces", headers=_auth("bravo")).json()["traces"][0]["id"] == bravo_trace

    for tenant, trace_id, tool_name in (("alpha", alpha_trace, "alpha-tool"), ("bravo", bravo_trace, "bravo-tool")):
        assert client.post(
            "/api/public/scores",
            json={"trace_id": trace_id, "name": "quality", "value": 1.0},
            headers=_auth(tenant),
        ).status_code == 200
        assert client.post(
            "/api/public/approvals",
            json={"run_id": trace_id, "approval_id": "shared-approval", "tool_name": tool_name},
            headers=_auth(tenant),
        ).status_code == 200
        assert client.post(
            "/api/public/alerts",
            json={"source": "guardrail", "event_type": "policy", "message": f"{tenant} alert", "trace_id": trace_id},
            headers=_auth(tenant),
        ).status_code == 201

    assert client.get(f"/api/public/scores?trace_id={alpha_trace}", headers=_auth("bravo")).json() == []
    assert client.get("/api/public/approvals/shared-approval", headers=_auth("bravo")).json()["tool_name"] == "bravo-tool"
    assert client.post(
        "/api/public/approvals/shared-approval/resolve",
        json={"action": "approve"},
        headers=_auth("bravo"),
    ).json()["trace_id"] == bravo_trace
    bravo_session = client.get("/api/public/sessions/shared-session", headers=_auth("bravo"))
    assert [trace["id"] for trace in bravo_session.json()["traces"]] == [bravo_trace]
    assert [alert["message"] for alert in client.get("/api/public/alerts", headers=_auth("bravo")).json()] == ["bravo alert"]

    alpha_export = client.get(f"/api/public/users/{user_id}/export", headers=_auth("alpha"))
    bravo_export = client.get(f"/api/public/users/{user_id}/export", headers=_auth("bravo"))
    assert [trace["id"] for trace in alpha_export.json()["traces"]] == [alpha_trace]
    assert [trace["id"] for trace in bravo_export.json()["traces"]] == [bravo_trace]
    assert client.delete(f"/api/public/users/{user_id}", headers=_auth("alpha")).status_code == 200
    assert client.get(f"/api/public/traces/{alpha_trace}", headers=_auth("alpha")).status_code == 404
    assert client.get(f"/api/public/users/{user_id}/export", headers=_auth("bravo")).json()["traces"][0]["id"] == bravo_trace
    assert client.get("/api/public/privacy/audit", headers=_auth("alpha")).json()[0]["action"] == "delete"
    assert project_ids["alpha"] != project_ids["bravo"]


def test_trace_detail_excludes_children_from_another_project(tenant_client):
    client, Session, project_ids = tenant_client
    trace_id = "alpha-trace-with-foreign-children"
    assert client.post(
        "/api/public/ingestion",
        json=_trace_events(trace_id, "alpha-session", "alpha-user", "alpha-agent"),
        headers=_auth("alpha"),
    ).status_code == 202
    with Session() as db:
        db.add_all(
            [
                Observation(
                    id="foreign-observation",
                    project_id=project_ids["bravo"],
                    trace_id=trace_id,
                    type="GENERATION",
                    name="foreign model",
                    start_time=datetime.now(timezone.utc),
                ),
                Score(
                    id="foreign-score",
                    project_id=project_ids["bravo"],
                    trace_id=trace_id,
                    name="foreign quality",
                    value=0.0,
                ),
            ]
        )
        db.commit()

    detail = client.get(f"/api/public/traces/{trace_id}", headers=_auth("alpha")).json()
    assert all(item["id"] != "foreign-observation" for item in detail["observations"])
    assert all(item["id"] != "foreign-score" for item in detail["scores"])


def test_ingestion_does_not_overwrite_trace_ids_owned_by_another_project(tenant_client):
    client, Session, _ = tenant_client
    trace_id = "tenant-owned-trace"
    assert client.post(
        "/api/public/ingestion",
        json=_trace_events(trace_id, "alpha-session", "alpha-user", "alpha-agent"),
        headers=_auth("alpha"),
    ).status_code == 202
    rejected = client.post(
        "/api/public/ingestion",
        json=_trace_events(trace_id, "bravo-session", "bravo-user", "bravo-agent"),
        headers=_auth("bravo"),
    )

    assert rejected.status_code == 202
    with Session() as db:
        assert db.get(IngestionJob, rejected.json()["job_id"]).status == "completed"
    assert client.get(f"/api/public/traces/{trace_id}", headers=_auth("bravo")).status_code == 404
    assert client.get(f"/api/public/traces/{trace_id}", headers=_auth("alpha")).json()["name"] == "alpha-agent"
