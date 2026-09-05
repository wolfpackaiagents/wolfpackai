"""First-party channel adapters with signed inbound verification."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.request
from typing import Callable, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .contracts import ChannelIdentity, DeliveryReceipt, InboundMessage


class ChatSender(Protocol):
    def send(self, message: str, identity: ChannelIdentity, *, idempotency_key: str) -> DeliveryReceipt: ...


class WebChatAdapter:
    """Maps browser chat identifiers onto the shared scoped session key."""

    def __init__(self, chat: ChatSender, scope: str = "default"):
        self.chat = chat
        self.scope = scope

    def receive(self, text: str, *, user_id: str, conversation_id: str, message_id: str) -> DeliveryReceipt:
        identity = ChannelIdentity(channel="webchat", scope=self.scope, conversation_id=conversation_id, user_id=user_id)
        return self.chat.send(text, identity, idempotency_key=f"webchat:{self.scope}:{message_id}")


class TelegramAdapter:
    """Telegram Bot API adapter using only the Python standard library."""

    def __init__(self, bot_token: str, webhook_secret: str = "", allowed_chat_ids: set[str] | None = None, retry_attempts: int = 3, transport: Callable[[str, dict], dict] | None = None):
        self.bot_token = bot_token
        self.webhook_secret = webhook_secret
        self.allowed_chat_ids = allowed_chat_ids or set()
        self.retry_attempts = retry_attempts
        self.transport = transport or self._post

    def parse_webhook(self, body: bytes, signature: str | None) -> InboundMessage | None:
        if not self.webhook_secret or signature != self.webhook_secret:
            return None
        update = json.loads(body)
        message = update.get("message") or {}
        text = message.get("text")
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        chat_id = str(chat.get("id", ""))
        if not text or not chat_id or not sender.get("id") or self.allowed_chat_ids and chat_id not in self.allowed_chat_ids:
            return None
        return InboundMessage(
            identity=ChannelIdentity(channel="telegram", scope=chat_id, conversation_id=chat_id, user_id=str(sender["id"])),
            message_id=str(message.get("message_id", update["update_id"])),
            text=text,
            idempotency_key=f"telegram:{update['update_id']}",
        )

    def deliver(self, identity: ChannelIdentity, text: str, delivery_id: str) -> DeliveryReceipt:
        for attempt in range(1, self.retry_attempts + 1):
            try:
                result = self.transport(f"https://api.telegram.org/bot{self.bot_token}/sendMessage", {"chat_id": identity.conversation_id, "text": text})
                return DeliveryReceipt(delivery_id=delivery_id, status="delivered", provider_message_id=str(result["result"]["message_id"]), attempts=attempt)
            except (OSError, KeyError, ValueError) as error:
                if attempt == self.retry_attempts:
                    return DeliveryReceipt(delivery_id=delivery_id, status="failed", attempts=attempt, error=str(error))
                time.sleep(0.05 * attempt)
        raise AssertionError("unreachable")

    @staticmethod
    def _post(url: str, payload: dict) -> dict:
        request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read())


class SlackAdapter:
    """Slack Events API adapter using the raw-body ``v0`` signing scheme."""

    def __init__(self, signing_secret: str, bot_token: str = "", allowed_team_ids: set[str] | None = None, allowed_channel_ids: set[str] | None = None, allowed_user_ids: set[str] | None = None, retry_attempts: int = 3, max_timestamp_age_seconds: int = 300, clock: Callable[[], float] = time.time, transport: Callable[[str, dict, dict], dict] | None = None):
        self.signing_secret = signing_secret
        self.bot_token = bot_token
        self.allowed_team_ids = allowed_team_ids or set()
        self.allowed_channel_ids = allowed_channel_ids or set()
        self.allowed_user_ids = allowed_user_ids or set()
        self.retry_attempts = retry_attempts
        self.max_timestamp_age_seconds = max_timestamp_age_seconds
        self.clock = clock
        self.transport = transport or self._post

    def verify_request(self, body: bytes, timestamp: str | None, signature: str | None) -> bool:
        if not self.signing_secret or not timestamp or not signature:
            return False
        try:
            if abs(self.clock() - int(timestamp)) > self.max_timestamp_age_seconds:
                return False
        except ValueError:
            return False
        expected = "v0=" + hmac.new(self.signing_secret.encode(), b"v0:" + timestamp.encode() + b":" + body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def url_verification_challenge(self, body: bytes, timestamp: str | None, signature: str | None) -> str | None:
        if not self.verify_request(body, timestamp, signature):
            return None
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        challenge = payload.get("challenge")
        return challenge if payload.get("type") == "url_verification" and isinstance(challenge, str) else None

    def parse_webhook(self, body: bytes, timestamp: str | None, signature: str | None) -> InboundMessage | None:
        if not self.verify_request(body, timestamp, signature):
            return None
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        event = payload.get("event") or {}
        team_id, channel_id, user_id, event_id = (str(payload.get("team_id", "")), str(event.get("channel", "")), str(event.get("user", "")), str(payload.get("event_id", "")))
        text = event.get("text")
        if payload.get("type") != "event_callback" or event.get("type") != "message" or event.get("subtype") or not isinstance(text, str) or not text or not all((team_id, channel_id, user_id, event_id)):
            return None
        if self.allowed_team_ids and team_id not in self.allowed_team_ids or self.allowed_channel_ids and channel_id not in self.allowed_channel_ids or self.allowed_user_ids and user_id not in self.allowed_user_ids:
            return None
        return InboundMessage(identity=ChannelIdentity(channel="slack", scope=team_id, conversation_id=channel_id, user_id=user_id), message_id=str(event.get("client_msg_id") or event_id), text=text, idempotency_key=f"slack:{event_id}")

    def deliver(self, identity: ChannelIdentity, text: str, delivery_id: str) -> DeliveryReceipt:
        headers = {"Authorization": f"Bearer {self.bot_token}", "Content-Type": "application/json"}
        for attempt in range(1, self.retry_attempts + 1):
            try:
                result = self.transport("https://slack.com/api/chat.postMessage", {"channel": identity.conversation_id, "text": text}, headers)
                if not result.get("ok") or not result.get("ts"):
                    raise ValueError(result.get("error", "Slack delivery failed"))
                return DeliveryReceipt(delivery_id=delivery_id, status="delivered", provider_message_id=str(result["ts"]), attempts=attempt)
            except (OSError, KeyError, ValueError) as error:
                if attempt == self.retry_attempts:
                    return DeliveryReceipt(delivery_id=delivery_id, status="failed", attempts=attempt, error=str(error))
                time.sleep(0.05 * attempt)
        raise AssertionError("unreachable")

    @staticmethod
    def _post(url: str, payload: dict, headers: dict) -> dict:
        request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read())


class DiscordAdapter:
    """Discord interaction adapter with Ed25519 request verification."""

    def __init__(self, public_key: str, bot_token: str = "", allowed_guild_ids: set[str] | None = None, allowed_channel_ids: set[str] | None = None, allowed_user_ids: set[str] | None = None, retry_attempts: int = 3, max_timestamp_age_seconds: int = 300, clock: Callable[[], float] = time.time, transport: Callable[[str, dict, dict], dict] | None = None):
        self.public_key = public_key
        self.bot_token = bot_token
        self.allowed_guild_ids = allowed_guild_ids or set()
        self.allowed_channel_ids = allowed_channel_ids or set()
        self.allowed_user_ids = allowed_user_ids or set()
        self.retry_attempts = retry_attempts
        self.max_timestamp_age_seconds = max_timestamp_age_seconds
        self.clock = clock
        self.transport = transport or SlackAdapter._post

    def verify_request(self, body: bytes, timestamp: str | None, signature: str | None) -> bool:
        if not self.public_key or not timestamp or not signature:
            return False
        try:
            if abs(self.clock() - int(timestamp)) > self.max_timestamp_age_seconds:
                return False
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(self.public_key)).verify(bytes.fromhex(signature), timestamp.encode() + body)
        except (ValueError, InvalidSignature):
            return False
        return True

    def is_ping(self, body: bytes, timestamp: str | None, signature: str | None) -> bool:
        if not self.verify_request(body, timestamp, signature):
            return False
        try:
            return json.loads(body).get("type") == 1
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False

    def parse_interaction(self, body: bytes, timestamp: str | None, signature: str | None) -> InboundMessage | None:
        if not self.verify_request(body, timestamp, signature):
            return None
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        member = payload.get("member") or {}
        user = member.get("user") or payload.get("user") or {}
        data = payload.get("data") or {}
        guild_id, channel_id, user_id, interaction_id = str(payload.get("guild_id") or "dm"), str(payload.get("channel_id", "")), str(user.get("id", "")), str(payload.get("id", ""))
        values = [str(option["value"]) for option in data.get("options", []) if "value" in option]
        text = " ".join(values) or str(data.get("name") or data.get("custom_id") or "")
        if payload.get("type") not in {2, 3} or not text or not all((channel_id, user_id, interaction_id)):
            return None
        if self.allowed_guild_ids and guild_id not in self.allowed_guild_ids or self.allowed_channel_ids and channel_id not in self.allowed_channel_ids or self.allowed_user_ids and user_id not in self.allowed_user_ids:
            return None
        return InboundMessage(identity=ChannelIdentity(channel="discord", scope=guild_id, conversation_id=channel_id, user_id=user_id), message_id=interaction_id, text=text, idempotency_key=f"discord:{interaction_id}")

    def deliver(self, identity: ChannelIdentity, text: str, delivery_id: str) -> DeliveryReceipt:
        headers = {"Authorization": f"Bot {self.bot_token}", "Content-Type": "application/json"}
        url = f"https://discord.com/api/v10/channels/{identity.conversation_id}/messages"
        for attempt in range(1, self.retry_attempts + 1):
            try:
                result = self.transport(url, {"content": text}, headers)
                if not result.get("id"):
                    raise ValueError("Discord delivery response has no message id")
                return DeliveryReceipt(delivery_id=delivery_id, status="delivered", provider_message_id=str(result["id"]), attempts=attempt)
            except (OSError, KeyError, ValueError) as error:
                if attempt == self.retry_attempts:
                    return DeliveryReceipt(delivery_id=delivery_id, status="failed", attempts=attempt, error=str(error))
                time.sleep(0.05 * attempt)
        raise AssertionError("unreachable")
