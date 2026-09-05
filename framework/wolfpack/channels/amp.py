"""AMP-backed WebChat adapter built on the existing Chat runs endpoint."""

from __future__ import annotations

import json
import urllib.request

from .contracts import ChannelIdentity, DeliveryReceipt


class AmpWebChatAdapter:
    """Creates AMP Chat runs; clients can stream the returned run through the existing SSE endpoint."""

    def __init__(self, base_url: str, registration_id: str, api_key: str, scope: str = "default", timeout: float = 10):
        self.base_url = base_url.rstrip("/")
        self.registration_id = registration_id
        self.api_key = api_key
        self.scope = scope
        self.timeout = timeout

    def receive(self, text: str, *, user_id: str, conversation_id: str, message_id: str) -> DeliveryReceipt:
        identity = ChannelIdentity(channel="webchat", scope=self.scope, conversation_id=conversation_id, user_id=user_id)
        payload = json.dumps({"registration_id": self.registration_id, "message": text, "session_id": identity.session_key}).encode()
        request = urllib.request.Request(f"{self.base_url}/api/public/chat/runs", data=payload, headers={"Content-Type": "application/json", "X-API-Key": self.api_key, "Idempotency-Key": f"webchat:{self.scope}:{message_id}"}, method="POST")
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read())
        return DeliveryReceipt(delivery_id=body["run_id"], provider_message_id=body["run_id"], status=body["status"])
