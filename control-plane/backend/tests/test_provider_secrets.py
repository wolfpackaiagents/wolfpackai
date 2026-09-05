from __future__ import annotations

import uuid

from app.core.config import get_settings
from app.models.entities import ApiKey, Organization, Project, ProviderSecret

from .test_amp import _auth_as, client


def _create_secret(client, headers, *, name="bot-token", value="super-secret-provider-token"):
    response = client.post(
        "/api/public/provider-secrets",
        json={"provider": "telegram", "name": name, "value": value, "rotation_interval_days": 30},
        headers=headers,
    )
    assert response.status_code == 201
    return response


def _registration(client, headers):
    environment = client.post("/api/public/mesh/environments", json={"slug": "secret-test", "name": "Secret test"}, headers=headers).json()
    definition = client.post("/api/public/mesh/definitions", json={"key": "secret-agent", "kind": "agent", "name": "Secret agent", "version": "1"}, headers=headers).json()
    return client.post("/api/public/mesh/registrations", json={"environment_id": environment["id"], "definition_id": definition["id"]}, headers=headers).json()


def test_provider_secret_is_encrypted_masked_rotatable_and_audited(client):
    headers = _auth_as("pk-editor")
    created = _create_secret(client, headers)
    secret = created.json()

    assert secret["value_masked"] == "********"
    assert "super-secret-provider-token" not in created.text
    with client.session_factory() as db:
        stored = db.query(ProviderSecret).filter_by(id=secret["id"]).one()
        assert stored.ciphertext != "super-secret-provider-token"
        assert stored.encrypted_data_key != "super-secret-provider-token"
        assert "super-secret-provider-token" not in stored.ciphertext

    rotated = client.patch(f"/api/public/provider-secrets/{secret['id']}", json={"value": "replacement-token"}, headers=headers)
    listed = client.get("/api/public/provider-secrets", headers=headers)
    audit = client.get(f"/api/public/provider-secrets/{secret['id']}/audit", headers=_auth_as("pk-test"))

    assert rotated.status_code == 200
    assert rotated.json()["version"] == 2
    assert "replacement-token" not in rotated.text
    assert listed.json()[0]["value_masked"] == "********"
    assert [event["action"] for event in audit.json()] == ["rotated", "created"]


def test_provider_secret_storage_requires_a_configured_master_key(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "provider_secrets_master_key", "")

    response = client.post(
        "/api/public/provider-secrets",
        json={"provider": "telegram", "name": "bot-token", "value": "secret"},
        headers=_auth_as("pk-editor"),
    )

    assert response.status_code == 503


def test_provider_secrets_require_editor_and_are_project_scoped(client):
    assert client.post("/api/public/provider-secrets", json={"provider": "telegram", "name": "bot-token", "value": "value"}, headers=_auth_as("pk-read-only")).status_code == 403
    created = _create_secret(client, _auth_as("pk-editor")).json()
    with client.session_factory() as db:
        organization = Organization(id=uuid.uuid4().hex, name="Other org")
        db.add(organization)
        db.flush()
        project = Project(id=uuid.uuid4().hex, organization_id=organization.id, name="Other project")
        db.add(project)
        db.add(ApiKey(project_id=project.id, public_key="pk-other-secret-project", hashed_secret_key="ef260e9aa3c673af240d17a2660480361a8e081d1ffeca2a5ed0e3219fc18567", display_secret_key="dev", role="editor"))
        db.commit()

    other_headers = _auth_as("pk-other-secret-project")
    assert client.get("/api/public/provider-secrets", headers=other_headers).json() == []
    assert client.patch(f"/api/public/provider-secrets/{created['id']}", json={"value": "attacker-value"}, headers=other_headers).status_code == 404
    assert client.get(f"/api/public/provider-secrets/{created['id']}/audit", headers=other_headers).status_code == 403


def test_referenced_provider_secret_cannot_be_deleted_and_connection_stores_id(client):
    headers = _auth_as("pk-editor")
    token = _create_secret(client, headers, name="bot-token").json()
    webhook = _create_secret(client, headers, name="webhook-secret", value="webhook-value").json()
    registration = _registration(client, headers)

    connection = client.post(
        "/api/public/channels/connections",
        json={"channel": "telegram", "name": "Operations", "registration_id": registration["id"], "secret_refs": {"bot_token": "bot-token", "webhook_secret": webhook["id"]}},
        headers=headers,
    )
    blocked = client.delete(f"/api/public/provider-secrets/{token['id']}", headers=headers)
    deleted_connection = client.delete(f"/api/public/channels/connections/{connection.json()['id']}", headers=headers)
    deleted_secret = client.delete(f"/api/public/provider-secrets/{token['id']}", headers=headers)

    assert connection.status_code == 201
    assert connection.json()["secret_refs"] == {"bot_token": token["id"], "webhook_secret": webhook["id"]}
    assert blocked.status_code == 409
    assert deleted_connection.status_code == 204
    assert deleted_secret.status_code == 204
