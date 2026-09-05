"""Opt-in channel webhooks. Telegram uses the Bot API directly, with no SDK dependency."""

from __future__ import annotations

import hmac
import hashlib
import time
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import or_

from wolfpack.channels import ChannelIdentity, DiscordAdapter, SlackAdapter, TelegramAdapter

from ..core.config import get_settings
from ..core.database import get_db
from ..core.auth import AuthContext, require_role
from ..models.entities import ChannelConnection, ChannelDelivery, ChannelSession, ChatRun, Environment, EnvironmentRegistration, MeshDefinition, ProviderSecret
from .chat import execute_chat_run

router = APIRouter(prefix="/api/public/channels", tags=["channels"])
REQUIRED_REFS = {"telegram": {"bot_token", "webhook_secret"}, "slack": {"bot_token", "signing_secret"}, "discord": {"bot_token", "public_key"}}


class ConnectionInput(BaseModel):
    channel: Literal["telegram", "slack", "discord"]
    name: str = Field(min_length=1, max_length=128)
    registration_id: str
    enabled: bool = True
    secret_refs: dict[str, str] = Field(default_factory=dict)
    allowlist: list[str] = Field(default_factory=list, max_length=500)


class ConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    registration_id: str | None = None
    enabled: bool | None = None
    secret_refs: dict[str, str] | None = None
    allowlist: list[str] | None = Field(default=None, max_length=500)


def _validate_secret_refs(auth: AuthContext, channel: str, refs: dict[str, str]) -> dict[str, str]:
    if not REQUIRED_REFS[channel].issubset(refs):
        raise HTTPException(status_code=422, detail=f"{channel} requires references for {', '.join(sorted(REQUIRED_REFS[channel]))}")
    resolved = {}
    for field, reference in refs.items():
        secret = auth.db.query(ProviderSecret).filter(
            ProviderSecret.project_id == auth.project_id,
            ProviderSecret.provider == channel,
            or_(ProviderSecret.id == reference, ProviderSecret.name == reference),
        ).first()
        if not secret:
            raise HTTPException(status_code=422, detail=f"Secret reference for {field} was not found in this project")
        resolved[field] = secret.id
    return resolved


def _connection_out(connection: ChannelConnection, registration: EnvironmentRegistration, environment: Environment, definition: MeshDefinition, delivery: ChannelDelivery | None) -> dict:
    refs = connection.secret_refs or {}
    if not connection.enabled or not registration.enabled:
        health = "disabled"
    elif delivery and delivery.status == "failed":
        health = "degraded"
    elif REQUIRED_REFS[connection.channel].issubset(refs):
        health = "healthy"
    else:
        health = "unknown"
    return {
        "id": connection.id, "channel": connection.channel, "name": connection.name, "enabled": connection.enabled,
        "secret_refs": refs, "allowlist": connection.allowlist or [], "health": health,
        "registration": {"id": registration.id, "enabled": registration.enabled, "environment_id": environment.id, "environment_name": environment.name, "definition_name": definition.name, "definition_version": definition.version},
        "last_delivery": None if not delivery else {"id": delivery.id, "status": delivery.status, "attempts": delivery.attempts, "provider_message_id": delivery.provider_message_id, "error": delivery.error, "created_at": delivery.created_at},
    }


def _connection_rows(auth: AuthContext):
    return auth.db.query(ChannelConnection, EnvironmentRegistration, Environment, MeshDefinition).join(EnvironmentRegistration, ChannelConnection.registration_id == EnvironmentRegistration.id).join(Environment, EnvironmentRegistration.environment_id == Environment.id).join(MeshDefinition, EnvironmentRegistration.definition_id == MeshDefinition.id).filter(ChannelConnection.project_id == auth.project_id)


@router.get("/connections")
def list_connections(auth: AuthContext = Depends(require_role("read_only"))):
    result = []
    for connection, registration, environment, definition in _connection_rows(auth).order_by(ChannelConnection.channel, ChannelConnection.name):
        delivery = auth.db.query(ChannelDelivery).filter_by(project_id=auth.project_id, channel=connection.channel).order_by(ChannelDelivery.created_at.desc()).first()
        result.append(_connection_out(connection, registration, environment, definition, delivery))
    return result


@router.post("/connections", status_code=status.HTTP_201_CREATED)
def create_connection(payload: ConnectionInput, auth: AuthContext = Depends(require_role("editor"))):
    refs = _validate_secret_refs(auth, payload.channel, payload.secret_refs)
    registration = auth.db.query(EnvironmentRegistration).filter_by(id=payload.registration_id, project_id=auth.project_id).first()
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")
    connection = ChannelConnection(project_id=auth.project_id, **payload.model_dump(exclude={"secret_refs"}), secret_refs=refs)
    auth.db.add(connection)
    try:
        auth.db.commit()
    except Exception:
        auth.db.rollback()
        raise HTTPException(status_code=409, detail="A connection with this provider and name already exists")
    environment = auth.db.query(Environment).filter_by(id=registration.environment_id).one()
    definition = auth.db.query(MeshDefinition).filter_by(id=registration.definition_id).one()
    return _connection_out(connection, registration, environment, definition, None)


@router.patch("/connections/{connection_id}")
def update_connection(connection_id: str, payload: ConnectionUpdate, auth: AuthContext = Depends(require_role("editor"))):
    connection = auth.db.query(ChannelConnection).filter_by(id=connection_id, project_id=auth.project_id).first()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    changes = payload.model_dump(exclude_unset=True)
    refs = _validate_secret_refs(auth, connection.channel, changes.get("secret_refs", connection.secret_refs or {}))
    if "secret_refs" in changes:
        changes["secret_refs"] = refs
    if registration_id := changes.get("registration_id"):
        if not auth.db.query(EnvironmentRegistration).filter_by(id=registration_id, project_id=auth.project_id).first():
            raise HTTPException(status_code=404, detail="Registration not found")
    for field, value in changes.items():
        setattr(connection, field, value)
    auth.db.commit()
    registration = auth.db.query(EnvironmentRegistration).filter_by(id=connection.registration_id).one()
    environment = auth.db.query(Environment).filter_by(id=registration.environment_id).one()
    definition = auth.db.query(MeshDefinition).filter_by(id=registration.definition_id).one()
    delivery = auth.db.query(ChannelDelivery).filter_by(project_id=auth.project_id, channel=connection.channel).order_by(ChannelDelivery.created_at.desc()).first()
    return _connection_out(connection, registration, environment, definition, delivery)


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(connection_id: str, auth: AuthContext = Depends(require_role("editor"))):
    connection = auth.db.query(ChannelConnection).filter_by(id=connection_id, project_id=auth.project_id).first()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    # Deliveries are retained as the project audit history and do not contain a connection FK.
    auth.db.delete(connection)
    auth.db.commit()


@router.get("/deliveries")
def list_deliveries(channel: Literal["telegram", "slack", "discord"] | None = None, limit: int = 50, auth: AuthContext = Depends(require_role("read_only"))):
    rows = auth.db.query(ChannelDelivery).filter_by(project_id=auth.project_id)
    if channel:
        rows = rows.filter_by(channel=channel)
    return [{"id": item.id, "channel": item.channel, "session_id": item.session_id, "chat_run_id": item.chat_run_id, "trace_id": item.trace_id, "status": item.status, "attempts": item.attempts, "provider_message_id": item.provider_message_id, "error": item.error, "created_at": item.created_at} for item in rows.order_by(ChannelDelivery.created_at.desc()).limit(min(limit, 200))]


def send_telegram_message(token: str, chat_id: str, text: str) -> str:
    adapter = TelegramAdapter(bot_token=token, retry_attempts=get_settings().telegram_delivery_attempts)
    receipt = adapter.deliver(ChannelIdentity(channel="telegram", scope=chat_id, conversation_id=chat_id, user_id=chat_id), text, uuid.uuid4().hex)
    if receipt.status != "delivered":
        raise OSError(receipt.error or "Telegram delivery failed")
    return receipt.provider_message_id or ""


def send_slack_message(token: str, channel_id: str, text: str) -> str:
    receipt = SlackAdapter("", bot_token=token).deliver(
        ChannelIdentity(channel="slack", scope="", conversation_id=channel_id, user_id=""), text, uuid.uuid4().hex
    )
    if receipt.status != "delivered":
        raise OSError(receipt.error or "Slack delivery failed")
    return receipt.provider_message_id or ""


def send_discord_message(token: str, channel_id: str, text: str) -> str:
    receipt = DiscordAdapter("", bot_token=token).deliver(
        ChannelIdentity(channel="discord", scope="", conversation_id=channel_id, user_id=""), text, uuid.uuid4().hex
    )
    if receipt.status != "delivered":
        raise OSError(receipt.error or "Discord delivery failed")
    return receipt.provider_message_id or ""


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(default=None), db=Depends(get_db)):
    settings = get_settings()
    if not settings.telegram_enabled or not settings.telegram_bot_token or not settings.telegram_registration_id:
        raise HTTPException(status_code=404, detail="Telegram channel is not enabled")
    if not settings.telegram_webhook_secret or not x_telegram_bot_api_secret_token or not hmac.compare_digest(settings.telegram_webhook_secret, x_telegram_bot_api_secret_token):
        raise HTTPException(status_code=401, detail="Invalid Telegram webhook signature")
    adapter = TelegramAdapter(settings.telegram_bot_token, settings.telegram_webhook_secret, {item.strip() for item in settings.telegram_allowed_chat_ids.split(",") if item.strip()})
    incoming = adapter.parse_webhook(await request.body(), x_telegram_bot_api_secret_token)
    if not incoming:
        raise HTTPException(status_code=403, detail="Telegram chat is not allowed or update is unsupported")
    registration = db.query(EnvironmentRegistration).filter_by(id=settings.telegram_registration_id, enabled=True).first()
    if not registration:
        raise HTTPException(status_code=409, detail="Telegram registration is not enabled")
    delivery = db.query(ChannelDelivery).filter_by(project_id=registration.project_id, idempotency_key=incoming.idempotency_key).first()
    if delivery:
        return _receipt(delivery)
    session = db.query(ChannelSession).filter_by(project_id=registration.project_id, channel="telegram", scoped_key=incoming.identity.session_key).first()
    if not session:
        # ChatRun predates channel identities and limits session IDs to 64 chars.
        session = ChannelSession(project_id=registration.project_id, channel="telegram", scoped_key=incoming.identity.session_key, session_id=f"channel_{hashlib.sha256(incoming.identity.session_key.encode()).hexdigest()[:48]}")
        db.add(session)
        db.flush()
    delivery = ChannelDelivery(project_id=registration.project_id, channel="telegram", idempotency_key=incoming.idempotency_key, session_id=session.session_id)
    db.add(delivery)
    run = ChatRun(project_id=registration.project_id, registration_id=registration.id, session_id=session.session_id, message=incoming.text)
    db.add(run)
    db.flush()
    delivery.chat_run_id = run.id
    db.commit()
    try:
        execute_chat_run(db, run)
        delivery.trace_id = run.trace_id
        delivery.attempts += 1
        delivery.provider_message_id = send_telegram_message(settings.telegram_bot_token, incoming.identity.conversation_id, run.output or "")
        delivery.status = "delivered"
    except Exception as error:
        delivery.attempts += 1
        delivery.status, delivery.error = "failed", str(error)
    db.commit()
    return _receipt(delivery)


@router.post("/slack/webhook")
async def slack_webhook(request: Request, x_slack_request_timestamp: str | None = Header(default=None), x_slack_signature: str | None = Header(default=None), db=Depends(get_db)):
    settings = get_settings()
    if not settings.slack_enabled or not settings.slack_signing_secret:
        raise HTTPException(status_code=404, detail="Slack channel is not enabled")
    adapter = SlackAdapter(
        settings.slack_signing_secret,
        bot_token=settings.slack_bot_token,
        allowed_team_ids={item.strip() for item in settings.slack_allowed_team_ids.split(",") if item.strip()},
        max_timestamp_age_seconds=settings.slack_replay_window_seconds,
        clock=time.time,
    )
    body = await request.body()
    if not adapter.verify_request(body, x_slack_request_timestamp, x_slack_signature):
        raise HTTPException(status_code=401, detail="Invalid Slack webhook signature")
    if challenge := adapter.url_verification_challenge(body, x_slack_request_timestamp, x_slack_signature):
        return {"challenge": challenge}
    if not settings.slack_bot_token or not settings.slack_registration_id:
        raise HTTPException(status_code=404, detail="Slack channel is not enabled")
    incoming = adapter.parse_webhook(body, x_slack_request_timestamp, x_slack_signature)
    if not incoming:
        raise HTTPException(status_code=403, detail="Slack event is not allowed or unsupported")
    registration = db.query(EnvironmentRegistration).filter_by(id=settings.slack_registration_id, enabled=True).first()
    if not registration:
        raise HTTPException(status_code=409, detail="Slack registration is not enabled")
    return _deliver_inbound(db, registration, incoming, lambda text: send_slack_message(settings.slack_bot_token, incoming.identity.conversation_id, text))


@router.post("/discord/interactions")
async def discord_interactions(request: Request, x_signature_timestamp: str | None = Header(default=None), x_signature_ed25519: str | None = Header(default=None), db=Depends(get_db)):
    settings = get_settings()
    if not settings.discord_enabled or not settings.discord_public_key:
        raise HTTPException(status_code=404, detail="Discord channel is not enabled")
    adapter = DiscordAdapter(
        settings.discord_public_key,
        bot_token=settings.discord_bot_token,
        allowed_guild_ids={item.strip() for item in settings.discord_allowed_guild_ids.split(",") if item.strip()},
        clock=time.time,
    )
    body = await request.body()
    if not adapter.verify_request(body, x_signature_timestamp, x_signature_ed25519):
        raise HTTPException(status_code=401, detail="Invalid Discord interaction signature")
    if adapter.is_ping(body, x_signature_timestamp, x_signature_ed25519):
        return {"type": 1}
    if not settings.discord_bot_token or not settings.discord_registration_id:
        raise HTTPException(status_code=404, detail="Discord channel is not enabled")
    incoming = adapter.parse_interaction(body, x_signature_timestamp, x_signature_ed25519)
    if not incoming:
        raise HTTPException(status_code=403, detail="Discord interaction is not allowed or unsupported")
    registration = db.query(EnvironmentRegistration).filter_by(id=settings.discord_registration_id, enabled=True).first()
    if not registration:
        raise HTTPException(status_code=409, detail="Discord registration is not enabled")
    return _deliver_inbound(db, registration, incoming, lambda text: send_discord_message(settings.discord_bot_token, incoming.identity.conversation_id, text))


def _deliver_inbound(db, registration: EnvironmentRegistration, incoming, send) -> dict:
    delivery = db.query(ChannelDelivery).filter_by(project_id=registration.project_id, idempotency_key=incoming.idempotency_key).first()
    if delivery:
        return _receipt(delivery)
    channel = incoming.identity.channel
    session = db.query(ChannelSession).filter_by(project_id=registration.project_id, channel=channel, scoped_key=incoming.identity.session_key).first()
    if not session:
        session = ChannelSession(
            project_id=registration.project_id,
            channel=channel,
            scoped_key=incoming.identity.session_key,
            session_id=f"channel_{hashlib.sha256(incoming.identity.session_key.encode()).hexdigest()[:48]}",
        )
        db.add(session)
        db.flush()
    delivery = ChannelDelivery(project_id=registration.project_id, channel=channel, idempotency_key=incoming.idempotency_key, session_id=session.session_id)
    db.add(delivery)
    run = ChatRun(project_id=registration.project_id, registration_id=registration.id, session_id=session.session_id, message=incoming.text)
    db.add(run)
    db.flush()
    delivery.chat_run_id = run.id
    db.commit()
    try:
        execute_chat_run(db, run)
        delivery.trace_id = run.trace_id
        delivery.attempts += 1
        delivery.provider_message_id = send(run.output or "")
        delivery.status = "delivered"
    except Exception as error:
        delivery.attempts += 1
        delivery.status, delivery.error = "failed", str(error)
    db.commit()
    return _receipt(delivery)


def _receipt(delivery: ChannelDelivery) -> dict:
    return {"delivery_id": delivery.id, "status": delivery.status, "session_id": delivery.session_id, "chat_run_id": delivery.chat_run_id, "trace_id": delivery.trace_id, "attempts": delivery.attempts, "provider_message_id": delivery.provider_message_id}
