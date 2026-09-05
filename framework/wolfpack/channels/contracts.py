"""Stable channel contracts shared by first-party and custom adapters."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChannelIdentity(BaseModel):
    channel: str = Field(min_length=1, max_length=64)
    scope: str = Field(min_length=1, max_length=255)
    conversation_id: str = Field(min_length=1, max_length=255)
    user_id: str = Field(min_length=1, max_length=255)

    @property
    def session_key(self) -> str:
        return f"{self.channel}:{self.scope}:{self.conversation_id}:{self.user_id}"


class InboundMessage(BaseModel):
    identity: ChannelIdentity
    message_id: str
    text: str = Field(min_length=1)
    idempotency_key: str


class DeliveryReceipt(BaseModel):
    delivery_id: str
    status: str
    provider_message_id: str | None = None
    attempts: int = 1
    error: str | None = None
