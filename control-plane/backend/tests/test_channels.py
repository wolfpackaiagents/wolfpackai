from __future__ import annotations

import json
import hashlib
import hmac
import uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.config import get_settings
from app.models.entities import ApiKey, ChannelDelivery, Organization, Project
from app.routes import channels

from .test_amp import _auth_as, client


def _channel_secrets(client, headers, channel: str) -> dict[str, str]:
    fields = {"telegram": ("bot-token", "webhook-secret"), "slack": ("bot-token", "signing-secret"), "discord": ("bot-token", "public-key")}[channel]
    return {
        field: client.post("/api/public/provider-secrets", json={"provider": channel, "name": name, "value": f"test-{name}"}, headers=headers).json()["id"]
        for field, name in zip(sorted(channels.REQUIRED_REFS[channel]), fields)
    }


def test_telegram_webhook_is_opt_in(client):
    response = client.post("/api/public/channels/telegram/webhook", content=b"{}")

    assert response.status_code == 404


def test_telegram_webhook_verifies_signature_allowlist_and_deduplicates(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "token")
    monkeypatch.setattr(settings, "telegram_webhook_secret", "secret")
    monkeypatch.setattr(settings, "telegram_allowed_chat_ids", "42")
    environment = client.post("/api/public/mesh/environments", json={"slug": "channels", "name": "Channels"}, headers=_auth_as("pk-editor")).json()
    definition = client.post("/api/public/mesh/definitions", json={"key": "weather-operations", "kind": "agent", "name": "Weather", "version": "1"}, headers=_auth_as("pk-editor")).json()
    registration = client.post("/api/public/mesh/registrations", json={"environment_id": environment["id"], "definition_id": definition["id"]}, headers=_auth_as("pk-editor")).json()
    monkeypatch.setattr(settings, "telegram_registration_id", registration["id"])
    monkeypatch.setattr(channels, "execute_chat_run", lambda db, run: (setattr(run, "output", "hello from AMP"), setattr(run, "trace_id", "telegram-trace"), setattr(run, "status", "completed")))
    sent = []
    monkeypatch.setattr(channels, "send_telegram_message", lambda token, chat_id, text: sent.append((token, chat_id, text)) or "99")
    payload = {"update_id": 10, "message": {"message_id": 4, "chat": {"id": 42}, "from": {"id": 7}, "text": "hello"}}

    rejected = client.post("/api/public/channels/telegram/webhook", content=json.dumps(payload), headers={"X-Telegram-Bot-Api-Secret-Token": "bad"})
    first = client.post("/api/public/channels/telegram/webhook", content=json.dumps(payload), headers={"X-Telegram-Bot-Api-Secret-Token": "secret"})
    second = client.post("/api/public/channels/telegram/webhook", content=json.dumps(payload), headers={"X-Telegram-Bot-Api-Secret-Token": "secret"})

    assert rejected.status_code == 401
    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == "delivered"
    assert first.json()["session_id"].startswith("channel_")
    assert first.json()["trace_id"] == "telegram-trace"
    assert len(sent) == 1
    deliveries = client.get("/api/public/channels/deliveries", headers=_auth_as("pk-read-only")).json()
    assert deliveries[0]["chat_run_id"] and deliveries[0]["trace_id"] == "telegram-trace"


def test_channel_connections_keep_only_secret_reference_names(client):
    headers = _auth_as("pk-editor")
    environment = client.post("/api/public/mesh/environments", json={"slug": "channel-control", "name": "Channel control"}, headers=headers).json()
    definition = client.post("/api/public/mesh/definitions", json={"key": "channel-agent", "kind": "agent", "name": "Channel agent", "version": "1"}, headers=headers).json()
    registration = client.post("/api/public/mesh/registrations", json={"environment_id": environment["id"], "definition_id": definition["id"]}, headers=headers).json()
    refs = _channel_secrets(client, headers, "slack")
    payload = {"channel": "slack", "name": "Ops", "registration_id": registration["id"], "secret_refs": refs, "allowlist": ["C123"]}

    created = client.post("/api/public/channels/connections", json=payload, headers=headers)
    listed = client.get("/api/public/channels/connections", headers=headers)
    rejected = client.post("/api/public/channels/connections", json={**payload, "name": "Unsafe", "secret_refs": {"bot_token": "xoxb-real-secret", "signing_secret": refs["signing_secret"]}}, headers=headers)

    assert created.status_code == 201
    assert listed.json()[0]["secret_refs"] == payload["secret_refs"]
    assert listed.json()[0]["registration"]["id"] == registration["id"]
    assert rejected.status_code == 422


def test_channel_connection_delete_is_project_scoped_and_keeps_delivery_history(client):
    headers = _auth_as("pk-editor")
    environment = client.post("/api/public/mesh/environments", json={"slug": "channel-delete", "name": "Channel delete"}, headers=headers).json()
    definition = client.post("/api/public/mesh/definitions", json={"key": "channel-delete-agent", "kind": "agent", "name": "Channel delete agent", "version": "1"}, headers=headers).json()
    registration = client.post("/api/public/mesh/registrations", json={"environment_id": environment["id"], "definition_id": definition["id"]}, headers=headers).json()
    connection = client.post("/api/public/channels/connections", json={"channel": "telegram", "name": "Delete me", "registration_id": registration["id"], "secret_refs": _channel_secrets(client, headers, "telegram")}, headers=headers).json()
    with client.session_factory() as db:
        delivery = ChannelDelivery(project_id=client.project_id, channel="telegram", idempotency_key="delete-history", session_id="channel-history")
        db.add(delivery)
        organization = Organization(id=uuid.uuid4().hex, name="Other org")
        db.add(organization)
        db.flush()
        project = Project(id=uuid.uuid4().hex, organization_id=organization.id, name="Other project")
        db.add(project)
        db.add(ApiKey(project_id=project.id, public_key="pk-other-project", hashed_secret_key="ef260e9aa3c673af240d17a2660480361a8e081d1ffeca2a5ed0e3219fc18567", display_secret_key="dev", role="editor"))
        db.commit()
        delivery_id = delivery.id

    forbidden = client.delete(f"/api/public/channels/connections/{connection['id']}", headers=_auth_as("pk-other-project"))
    deleted = client.delete(f"/api/public/channels/connections/{connection['id']}", headers=headers)
    listed = client.get("/api/public/channels/connections", headers=headers)
    deliveries = client.get("/api/public/channels/deliveries", headers=headers)

    assert forbidden.status_code == 404
    assert deleted.status_code == 204
    assert listed.json() == []
    assert [delivery["id"] for delivery in deliveries.json()] == [delivery_id]


def test_slack_webhook_handles_url_verification_and_deduplicates_signed_events(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "slack_enabled", True)
    monkeypatch.setattr(settings, "slack_signing_secret", "secret")
    monkeypatch.setattr(settings, "slack_bot_token", "token")
    monkeypatch.setattr(settings, "slack_allowed_team_ids", "T1")
    environment = client.post("/api/public/mesh/environments", json={"slug": "slack", "name": "Slack"}, headers=_auth_as("pk-editor")).json()
    definition = client.post("/api/public/mesh/definitions", json={"key": "slack-agent", "kind": "agent", "name": "Slack", "version": "1"}, headers=_auth_as("pk-editor")).json()
    registration = client.post("/api/public/mesh/registrations", json={"environment_id": environment["id"], "definition_id": definition["id"]}, headers=_auth_as("pk-editor")).json()
    monkeypatch.setattr(settings, "slack_registration_id", registration["id"])
    monkeypatch.setattr(channels, "execute_chat_run", lambda db, run: (setattr(run, "output", "hello from AMP"), setattr(run, "status", "completed")))
    sent = []
    monkeypatch.setattr(channels, "send_slack_message", lambda token, channel_id, text: sent.append((token, channel_id, text)) or "1.2")

    def signed(payload):
        body = json.dumps(payload).encode()
        timestamp = "1777032000"
        signature = "v0=" + hmac.new(b"secret", b"v0:" + timestamp.encode() + b":" + body, hashlib.sha256).hexdigest()
        return body, {"X-Slack-Request-Timestamp": timestamp, "X-Slack-Signature": signature}

    challenge_body, challenge_headers = signed({"type": "url_verification", "challenge": "challenge-1"})
    event_body, event_headers = signed({"type": "event_callback", "event_id": "Ev1", "team_id": "T1", "event": {"type": "message", "channel": "C1", "user": "U1", "text": "hello"}})
    monkeypatch.setattr(channels.time, "time", lambda: 1777032000)

    challenge = client.post("/api/public/channels/slack/webhook", content=challenge_body, headers=challenge_headers)
    first = client.post("/api/public/channels/slack/webhook", content=event_body, headers=event_headers)
    second = client.post("/api/public/channels/slack/webhook", content=event_body, headers=event_headers)

    assert challenge.json() == {"challenge": "challenge-1"}
    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == "delivered"
    assert len(sent) == 1


def test_discord_interaction_ping_and_signed_delivery_are_verified_and_deduplicated(client, monkeypatch):
    settings = get_settings()
    private_key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(settings, "discord_enabled", True)
    monkeypatch.setattr(settings, "discord_public_key", private_key.public_key().public_bytes_raw().hex())
    monkeypatch.setattr(settings, "discord_bot_token", "token")
    monkeypatch.setattr(settings, "discord_allowed_guild_ids", "G1")
    environment = client.post("/api/public/mesh/environments", json={"slug": "discord", "name": "Discord"}, headers=_auth_as("pk-editor")).json()
    definition = client.post("/api/public/mesh/definitions", json={"key": "discord-agent", "kind": "agent", "name": "Discord", "version": "1"}, headers=_auth_as("pk-editor")).json()
    registration = client.post("/api/public/mesh/registrations", json={"environment_id": environment["id"], "definition_id": definition["id"]}, headers=_auth_as("pk-editor")).json()
    monkeypatch.setattr(settings, "discord_registration_id", registration["id"])
    monkeypatch.setattr(channels, "execute_chat_run", lambda db, run: (setattr(run, "output", "hello from AMP"), setattr(run, "status", "completed")))
    sent = []
    monkeypatch.setattr(channels, "send_discord_message", lambda token, channel_id, text: sent.append((token, channel_id, text)) or "M1")

    def signed(payload):
        body = json.dumps(payload).encode()
        timestamp = "1777032000"
        return body, {"X-Signature-Timestamp": timestamp, "X-Signature-Ed25519": private_key.sign(timestamp.encode() + body).hex()}

    ping_body, ping_headers = signed({"id": "P1", "type": 1})
    interaction_body, interaction_headers = signed({"id": "I1", "type": 2, "guild_id": "G1", "channel_id": "C1", "member": {"user": {"id": "U1"}}, "data": {"name": "ask", "options": [{"value": "hello"}]}})
    monkeypatch.setattr(channels.time, "time", lambda: 1777032000)

    ping = client.post("/api/public/channels/discord/interactions", content=ping_body, headers=ping_headers)
    first = client.post("/api/public/channels/discord/interactions", content=interaction_body, headers=interaction_headers)
    second = client.post("/api/public/channels/discord/interactions", content=interaction_body, headers=interaction_headers)

    assert ping.json() == {"type": 1}
    assert first.json()["status"] == "delivered"
    assert second.json()["status"] == "delivered"
    assert len(sent) == 1
