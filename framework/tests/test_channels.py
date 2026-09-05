from __future__ import annotations

import json
import hashlib
import hmac

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from wolfpack.channels import AmpWebChatAdapter, ChannelIdentity, DeliveryReceipt, DiscordAdapter, SlackAdapter, TelegramAdapter, WebChatAdapter


class FakeChat:
    def __init__(self):
        self.calls = []

    def send(self, message, identity, *, idempotency_key):
        self.calls.append((message, identity, idempotency_key))
        return DeliveryReceipt(delivery_id="run-1", status="accepted")


def test_web_chat_scopes_sessions_and_forwards_idempotency():
    chat = FakeChat()
    adapter = WebChatAdapter(chat)

    receipt = adapter.receive("hello", user_id="user-7", conversation_id="tab-3", message_id="browser-9")

    assert receipt.status == "accepted"
    assert chat.calls[0][1].session_key == "webchat:default:tab-3:user-7"
    assert chat.calls[0][2] == "webchat:default:browser-9"


def test_telegram_verifies_secret_allowlist_and_builds_scoped_identity():
    adapter = TelegramAdapter(bot_token="token", webhook_secret="secret", allowed_chat_ids={"42"})
    payload = json.dumps({"update_id": 3, "message": {"message_id": 9, "chat": {"id": 42}, "from": {"id": 7}, "text": "hi"}}).encode()

    message = adapter.parse_webhook(payload, "secret")

    assert message.identity.session_key == "telegram:42:42:7"
    assert message.idempotency_key == "telegram:3"
    assert adapter.parse_webhook(payload, "wrong") is None


def test_telegram_delivery_retries_transient_failures():
    attempts = []

    def transport(url, payload):
        attempts.append((url, payload))
        if len(attempts) == 1:
            raise OSError("temporary")
        return {"ok": True, "result": {"message_id": 12}}

    adapter = TelegramAdapter(bot_token="token", transport=transport, retry_attempts=2)

    receipt = adapter.deliver(ChannelIdentity(channel="telegram", scope="42", conversation_id="42", user_id="7"), "reply", "delivery-1")

    assert receipt.status == "delivered"
    assert receipt.provider_message_id == "12"
    assert len(attempts) == 2


def test_slack_verifies_signed_event_replay_allowlist_and_scoped_identity():
    body = json.dumps({"type": "event_callback", "event_id": "Ev1", "team_id": "T1", "event": {"type": "message", "channel": "C1", "user": "U1", "text": "hello"}}).encode()
    timestamp = "1000"
    signature = "v0=" + hmac.new(b"secret", b"v0:" + timestamp.encode() + b":" + body, hashlib.sha256).hexdigest()
    adapter = SlackAdapter("secret", allowed_team_ids={"T1"}, allowed_channel_ids={"C1"}, allowed_user_ids={"U1"}, clock=lambda: 1001)

    message = adapter.parse_webhook(body, timestamp, signature)

    assert message.identity.session_key == "slack:T1:C1:U1"
    assert message.idempotency_key == "slack:Ev1"
    assert adapter.parse_webhook(body, "1", signature) is None
    assert adapter.parse_webhook(body, timestamp, "v0=bad") is None


def test_slack_url_verification_and_outbound_retry():
    body = b'{"type":"url_verification","challenge":"challenge-1"}'
    timestamp = "1000"
    signature = "v0=" + hmac.new(b"secret", b"v0:" + timestamp.encode() + b":" + body, hashlib.sha256).hexdigest()
    calls = []

    def transport(url, payload, headers):
        calls.append((url, payload, headers))
        if len(calls) == 1:
            raise OSError("temporary")
        return {"ok": True, "ts": "123.4"}

    adapter = SlackAdapter("secret", bot_token="token", clock=lambda: 1000, transport=transport, retry_attempts=2)

    assert adapter.url_verification_challenge(body, timestamp, signature) == "challenge-1"
    receipt = adapter.deliver(ChannelIdentity(channel="slack", scope="T1", conversation_id="C1", user_id="U1"), "reply", "delivery-1")

    assert receipt.status == "delivered"
    assert receipt.provider_message_id == "123.4"
    assert len(calls) == 2
    assert calls[-1][2]["Authorization"] == "Bearer token"


def test_discord_verifies_interaction_allowlist_and_retries_outbound_delivery():
    private_key = Ed25519PrivateKey.generate()
    body = json.dumps({"id": "I1", "type": 2, "guild_id": "G1", "channel_id": "C1", "member": {"user": {"id": "U1"}}, "data": {"name": "ask", "options": [{"value": "hello"}]}}).encode()
    timestamp = "1000"
    signature = private_key.sign(timestamp.encode() + body).hex()
    calls = []

    def transport(url, payload, headers):
        calls.append((url, payload, headers))
        if len(calls) == 1:
            raise OSError("temporary")
        return {"id": "M1"}

    adapter = DiscordAdapter(private_key.public_key().public_bytes_raw().hex(), bot_token="token", allowed_guild_ids={"G1"}, allowed_channel_ids={"C1"}, allowed_user_ids={"U1"}, transport=transport, retry_attempts=2, clock=lambda: 1000)

    message = adapter.parse_interaction(body, timestamp, signature)
    receipt = adapter.deliver(message.identity, "reply", "delivery-1")

    assert message.identity.session_key == "discord:G1:C1:U1"
    assert message.text == "hello"
    assert message.idempotency_key == "discord:I1"
    assert receipt.provider_message_id == "M1"
    assert len(calls) == 2
    assert calls[-1][2]["Authorization"] == "Bot token"


def test_discord_ping_and_invalid_signature_are_rejected():
    private_key = Ed25519PrivateKey.generate()
    body = b'{"id":"I1","type":1}'
    timestamp = "1000"
    signature = private_key.sign(timestamp.encode() + body).hex()
    adapter = DiscordAdapter(private_key.public_key().public_bytes_raw().hex(), clock=lambda: 1000)

    assert adapter.is_ping(body, timestamp, signature)
    assert adapter.parse_interaction(body, timestamp, "00") is None


def test_amp_web_chat_creates_a_run_with_scoped_session(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return b'{"run_id": "run-4", "status": "pending"}'

    captured = []
    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: captured.append(request) or Response())

    receipt = AmpWebChatAdapter("https://amp.test", "registration-1", "key", scope="tenant-1").receive("hello", user_id="u1", conversation_id="c1", message_id="m1")

    assert receipt.delivery_id == "run-4"
    assert b"webchat:tenant-1:c1:u1" in captured[0].data
