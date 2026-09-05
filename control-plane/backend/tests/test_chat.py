from __future__ import annotations

from .test_amp import _auth_as, client


def _registration(client, key: str, kind: str, version: str = "1.0.0") -> dict:
    headers = _auth_as("pk-editor")
    environment = client.post("/api/public/mesh/environments", json={"slug": f"chat-{key}", "name": "Chat"}, headers=headers).json()
    definition = client.post("/api/public/mesh/definitions", json={"key": key, "kind": kind, "name": key, "version": version}, headers=headers).json()
    return client.post("/api/public/mesh/registrations", json={"environment_id": environment["id"], "definition_id": definition["id"]}, headers=headers).json()


def test_chat_allows_only_source_owned_runtime_keys(client):
    allowed = _registration(client, "support-orchestrator", "team")
    unknown = _registration(client, "arbitrary-runtime", "agent")

    # any enabled registration can create a conversation
    convo = client.post("/api/public/chat/conversations", json={"registration_id": allowed["id"]}, headers=_auth_as("pk-editor"))
    assert convo.status_code == 201
    cid = convo.json()["id"]

    # runs always succeed (they just create a pending record for client-side execution)
    accepted = client.post(f"/api/public/chat/conversations/{cid}/runs", json={"message": "help"}, headers=_auth_as("pk-editor"))
    assert accepted.status_code == 201


def test_chat_callback_persists_terminal_output(client):
    registration = _registration(client, "weather-operations", "agent")
    convo = client.post("/api/public/chat/conversations", json={"registration_id": registration["id"]}, headers=_auth_as("pk-editor")).json()
    cid = convo["id"]

    run = client.post(f"/api/public/chat/conversations/{cid}/runs", json={"message": "weather", "idempotency_key": "callback-test"}, headers=_auth_as("pk-editor")).json()
    rid = run["run_id"]

    # SSE fails because weather-operations has no chat_endpoint
    stream = client.get(f"/api/public/chat/runs/{rid}/events", headers=_auth_as("pk-editor"))
    assert "event: run.failed" in stream.text
    assert "chat_endpoint" in stream.text

    # Callback after failure should still work
    cb = client.post(f"/api/public/chat/runs/{rid}/callback/complete", json={"output": "Sunny", "trace_id": "trace-test"}, headers=_auth_as("pk-editor"))
    assert cb.status_code == 200