"""Tests for AI Prediction models, routes, and lifecycle."""
from __future__ import annotations

import uuid


def _admin_key(client):
    return "pk-test:dev"


def _create_pred(client, api_key):
    body = {"name": "test", "horizon_date": "2026-10-01T00:00:00+00:00"}
    resp = client.post("/api/public/predictions", json=body, headers={"X-API-Key": api_key})
    return resp.json()["id"]


def test_list_predictions(client):
    api_key = _admin_key(client)
    prediction_id = _create_pred(client, api_key)
    client.post(f"/api/public/predictions/{prediction_id}/agents", json={
        "persona_name": "Analista", "prediction": {"resultado": "A"},
    }, headers={"X-API-Key": api_key})
    resp = client.get("/api/public/predictions", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    data = resp.json()
    assert "predictions" in data
    assert data["total"] >= 1
    assert next(item for item in data["predictions"] if item["id"] == prediction_id)["agent_count"] == 1


def test_list_predictions_accepts_empty_scope_dates(client):
    api_key = _admin_key(client)
    resp = client.get("/api/public/predictions?from=&to=", headers={"X-API-Key": api_key})
    assert resp.status_code == 200


def test_get_prediction(client):
    api_key = _admin_key(client)
    pred_id = _create_pred(client, api_key)
    resp = client.get(f"/api/public/predictions/{pred_id}", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test"
    assert data["id"] == pred_id


def test_update_prediction(client):
    api_key = _admin_key(client)
    pred_id = _create_pred(client, api_key)
    body = {"name": "eleicoes-2026-v2"}
    resp = client.patch(f"/api/public/predictions/{pred_id}", json=body, headers={"X-API-Key": api_key})
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "eleicoes-2026-v2"


def test_complete_prediction(client):
    api_key = _admin_key(client)
    pred_id = _create_pred(client, api_key)
    resp = client.post(f"/api/public/predictions/{pred_id}/complete", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_add_prediction_agent(client):
    api_key = _admin_key(client)
    pred_id = _create_pred(client, api_key)
    body = {
        "persona_name": "Analista",
        "persona_profile": {"vies": "conservador", "expertise": "política"},
        "prediction": {"resultado": "candidato A vence"},
        "confidence": 0.75,
        "interactions": [{"target": "Economista", "content": "discordo parcialmente", "round": 1}],
    }
    resp = client.post(f"/api/public/predictions/{pred_id}/agents", json=body, headers={"X-API-Key": api_key})
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["persona_name"] == "Analista"
    assert data["confidence"] == 0.75
    assert data["status"] == "completed"


def test_list_prediction_agents(client):
    api_key = _admin_key(client)
    pred_id = _create_pred(client, api_key)
    client.post(f"/api/public/predictions/{pred_id}/agents", json={
        "persona_name": "Agente-1", "prediction": {"r": "a"},
    }, headers={"X-API-Key": api_key})
    resp = client.get(f"/api/public/predictions/{pred_id}/agents", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    assert len(resp.json()["agents"]) == 1


def test_prediction_interactions_graph(client):
    api_key = _admin_key(client)
    pred_id = _create_pred(client, api_key)
    client.post(f"/api/public/predictions/{pred_id}/agents", json={
        "persona_name": "Ana", "prediction": {"r": "x"}, "interactions": [{"target": "Bob", "content": "concordo", "round": 1}],
    }, headers={"X-API-Key": api_key})
    resp = client.get(f"/api/public/predictions/{pred_id}/interactions", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    assert len(resp.json()["nodes"]) >= 1


def test_evaluate_prediction(client):
    api_key = _admin_key(client)
    pred_id = _create_pred(client, _admin_key(client))
    resp = client.post(f"/api/public/predictions/{pred_id}/eval", json={"accuracy_score": 0.85}, headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    assert resp.json()["accuracy_score"] == 0.85
    assert resp.json()["status"] == "evaluated"


def test_prediction_summary(client):
    api_key = _admin_key(client)
    pred_id = _create_pred(client, _admin_key(client))
    client.post(f"/api/public/predictions/{pred_id}/agents", json={
        "persona_name": "Ana", "prediction": {"r": "x"}, "confidence": 0.8,
    }, headers={"X-API-Key": api_key})
    client.post(f"/api/public/predictions/{pred_id}/agents", json={
        "persona_name": "Bob", "prediction": {"r": "x"}, "confidence": 0.9,
    }, headers={"X-API-Key": api_key})
    resp = client.get(f"/api/public/predictions/{pred_id}/summary", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_count"] == 2
    assert len(data["convergences"]) == 1
    assert data["convergences"][0]["rate"] == 1.0


def test_prediction_summary_convergence_partial(client):
    api_key = _admin_key(client)
    pred_id = _create_pred(client, _admin_key(client))
    client.post(f"/api/public/predictions/{pred_id}/agents", json={
        "persona_name": "Ana", "prediction": {"a": "x", "b": "y"}, "confidence": 0.8,
    }, headers={"X-API-Key": api_key})
    client.post(f"/api/public/predictions/{pred_id}/agents", json={
        "persona_name": "Bob", "prediction": {"a": "x", "b": "z"}, "confidence": 0.6,
    }, headers={"X-API-Key": api_key})
    resp = client.get(f"/api/public/predictions/{pred_id}/summary", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["convergences"]) == 1
    assert data["convergences"][0]["rate"] == 0.5


def test_prediction_traces_and_scores_endpoints(client):
    api_key = _admin_key(client)
    pred_id = _create_pred(client, _admin_key(client))
    resp = client.get(f"/api/public/predictions/{pred_id}/traces", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    resp = client.get(f"/api/public/predictions/{pred_id}/scores", headers={"X-API-Key": api_key})
    assert resp.status_code == 200


def test_prediction_404(client):
    api_key = _admin_key(client)
    resp = client.get("/api/public/predictions/nonexistent", headers={"X-API-Key": api_key})
    assert resp.status_code == 404
    resp = client.patch("/api/public/predictions/nonexistent", json={"name": "x"}, headers={"X-API-Key": api_key})
    assert resp.status_code == 404
    resp = client.post("/api/public/predictions/nonexistent/complete", headers={"X-API-Key": api_key})
    assert resp.status_code == 404


def test_prediction_deletion_cascades_agents(client):
    api_key = _admin_key(client)
    pred_id = _create_pred(client, _admin_key(client))
    client.post(f"/api/public/predictions/{pred_id}/agents", json={
        "persona_name": "Agent", "prediction": {"r": "x"},
    }, headers={"X-API-Key": api_key})
    resp = client.delete(f"/api/public/predictions/{pred_id}", headers={"X-API-Key": api_key})
    assert resp.status_code == 204, resp.text
    resp = client.get(f"/api/public/predictions/{pred_id}", headers={"X-API-Key": api_key})
    assert resp.status_code == 404


def test_model_creation():
    from app.models.entities import PredictionAgentRun, PredictionRun
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    run = PredictionRun(
        id="test", project_id="p1", name="test", seed_summary="summary",
        horizon_date=now, scenario_params={"key": "val"}, personas=[{"name": "a"}],
        status="running",
    )
    assert run.name == "test"
    assert run.status == "running"

    agent = PredictionAgentRun(
        id="a1", prediction_run_id="test", project_id="p1", persona_name="Ana",
        persona_profile={"vies": "otimista"}, prediction={"r": "x"}, confidence=0.8,
        interactions=[{"target": "Bob", "content": "ok"}], status="completed",
    )
    assert agent.persona_name == "Ana"
    assert agent.confidence == 0.8


def test_prediction_simulation_ledger_is_scoped_ordered_and_immutable(client):
    api_key = _admin_key(client)
    prediction_id = _create_pred(client, api_key)
    first = client.post(f"/api/public/predictions/{prediction_id}/entities", json={
        "entity_type": "actor", "name": "Ana", "state": {"support": 0.4},
    }, headers={"X-API-Key": api_key})
    second = client.post(f"/api/public/predictions/{prediction_id}/entities", json={
        "entity_type": "actor", "name": "Bob",
    }, headers={"X-API-Key": api_key})
    assert first.status_code == second.status_code == 201
    entity_id = first.json()["id"]
    relationship = client.post(f"/api/public/predictions/{prediction_id}/relationships", json={
        "source_entity_id": entity_id,
        "target_entity_id": second.json()["id"],
        "relationship_type": "influences",
    }, headers={"X-API-Key": api_key})
    assert relationship.status_code == 201
    round_ = client.post(f"/api/public/predictions/{prediction_id}/rounds", json={}, headers={"X-API-Key": api_key})
    assert round_.status_code == 201
    event_body = {"event_type": "message", "entity_id": entity_id, "idempotency_key": "event-1"}
    event = client.post(f"/api/public/predictions/{prediction_id}/events", json=event_body, headers={"X-API-Key": api_key})
    repeated = client.post(f"/api/public/predictions/{prediction_id}/events", json=event_body, headers={"X-API-Key": api_key})
    assert event.status_code == repeated.status_code == 201
    assert event.json()["id"] == repeated.json()["id"]
    assert event.json()["sequence"] == 1
    revision = client.post(f"/api/public/predictions/{prediction_id}/entities/{entity_id}/revisions", json={"state": {"support": 0.5}}, headers={"X-API-Key": api_key})
    assert revision.status_code == 201
    assert revision.json()["revision"] == 1
    simulation = client.get(f"/api/public/predictions/{prediction_id}/simulation", headers={"X-API-Key": api_key})
    assert simulation.status_code == 200
    assert len(simulation.json()["entities"]) == 2
    assert len(simulation.json()["relationships"]) == 1
    assert len(simulation.json()["events"]) == 1
    assert len(simulation.json()["revisions"]) == 1


def test_prediction_simulation_rejects_mutations_after_terminal_lifecycle(client):
    api_key = _admin_key(client)
    prediction_id = _create_pred(client, api_key)
    assert client.post(f"/api/public/predictions/{prediction_id}/complete", headers={"X-API-Key": api_key}).status_code == 200
    response = client.post(f"/api/public/predictions/{prediction_id}/entities", json={"entity_type": "actor", "name": "Ana"}, headers={"X-API-Key": api_key})
    assert response.status_code == 409
