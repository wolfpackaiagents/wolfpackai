"""Chat gateway — creates runs and persists results via callback.

The AMP does NOT execute agents or teams inline. The client framework
executes the Agent/Team locally and calls back with the result.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..core.auth import AuthContext, require_role
from ..core.config import get_settings
from ..core.database import get_db
from ..models.entities import ChatConversation, ChatRun, ChatTurn, Environment, EnvironmentRegistration, MeshDefinition, RegistrationHeartbeat
from ..routes.mesh import _registration_out
from ..services.schedule_runtime import safe_endpoint

router = APIRouter(prefix="/api/public/chat", tags=["chat"])


class ConversationCreate(BaseModel):
    registration_id: str
    title: str | None = Field(default=None, max_length=255)
    session_id: str | None = Field(default=None, max_length=64)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ConversationRunRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class RunCompleteBody(BaseModel):
    output: str | None = None
    trace_id: str | None = None
    error: str | None = None
    fencing_token: int | None = None


def _enabled_chat_registration(auth: AuthContext, registration_id: str) -> EnvironmentRegistration:
    registration = auth.db.query(EnvironmentRegistration).filter_by(id=registration_id, project_id=auth.project_id, enabled=True).first()
    if not registration:
        raise HTTPException(status_code=404, detail="Enabled registration not found")
    environment = auth.db.query(Environment).filter_by(id=registration.environment_id, project_id=auth.project_id, status="active").first()
    definition = auth.db.query(MeshDefinition).filter_by(id=registration.definition_id, project_id=auth.project_id).first()
    if not environment or not definition:
        raise HTTPException(status_code=404, detail="Registration environment or definition not found")
    return registration


def _conversation(auth: AuthContext, conversation_id: str) -> ChatConversation:
    conversation = auth.db.query(ChatConversation).filter_by(
        id=conversation_id, project_id=auth.project_id, owner_api_key_id=auth.api_key_id, deleted_at=None,
    ).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def _turn_out(turn: ChatTurn, db=None) -> dict:
    run_id = db.query(ChatRun.id).filter_by(turn_id=turn.id).scalar() if db else None
    return {
        "id": turn.id, "run_id": run_id, "sequence": turn.sequence,
        "message": turn.message, "output": turn.output, "trace_id": turn.trace_id,
        "status": turn.status, "error": turn.error,
        "created_at": turn.created_at.isoformat(),
        "started_at": turn.started_at.isoformat() if turn.started_at else None,
        "completed_at": turn.completed_at.isoformat() if turn.completed_at else None,
    }


def _conversation_out(conversation: ChatConversation, include_turns: bool = False, db=None) -> dict:
    result = {
        "id": conversation.id, "registration_id": conversation.registration_id,
        "session_id": conversation.session_id, "title": conversation.title or "New conversation",
        "created_at": conversation.created_at.isoformat(), "updated_at": conversation.updated_at.isoformat(),
    }
    if include_turns:
        turns = db.query(ChatTurn).filter_by(conversation_id=conversation.id).order_by(ChatTurn.sequence).all()
        result["turns"] = [_turn_out(turn, db) for turn in turns]
        result["messages"] = [
            msg for turn in turns
            for msg in (
                {"id": f"{turn.id}:user", "role": "user", "content": turn.message, "created_at": turn.created_at.isoformat(), "run_id": db.query(ChatRun.id).filter_by(turn_id=turn.id).scalar(), "trace_id": None},
                {"id": f"{turn.id}:assistant", "role": "assistant", "content": turn.output or "", "created_at": (turn.completed_at or turn.created_at).isoformat(), "run_id": db.query(ChatRun.id).filter_by(turn_id=turn.id).scalar(), "trace_id": turn.trace_id} if turn.status != "pending" else None,
            ) if msg is not None
        ]
    return result


# ---- Conversation CRUD ----

@router.post("/conversations", status_code=201)
def create_conversation(body: ConversationCreate, auth: AuthContext = Depends(require_role("editor"))):
    registration = _enabled_chat_registration(auth, body.registration_id)
    conversation = ChatConversation(
        project_id=auth.project_id, owner_api_key_id=auth.api_key_id,
        registration_id=registration.id, session_id=body.session_id or f"chat_{uuid.uuid4().hex[:16]}",
        title=body.title.strip() if body.title and body.title.strip() else "New conversation",
    )
    auth.db.add(conversation)
    auth.db.commit()
    auth.db.refresh(conversation)
    return _conversation_out(conversation)


@router.get("/conversations")
def list_conversations(auth: AuthContext = Depends(require_role("read_only"))):
    conversations = auth.db.query(ChatConversation).filter_by(
        project_id=auth.project_id, owner_api_key_id=auth.api_key_id, deleted_at=None
    ).order_by(ChatConversation.updated_at.desc()).all()
    return [_conversation_out(conversation) for conversation in conversations]


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, auth: AuthContext = Depends(require_role("read_only"))):
    return _conversation_out(_conversation(auth, conversation_id), include_turns=True, db=auth.db)


@router.patch("/conversations/{conversation_id}")
def update_conversation(conversation_id: str, body: ConversationUpdate, auth: AuthContext = Depends(require_role("editor"))):
    conversation = _conversation(auth, conversation_id)
    conversation.title = body.title
    conversation.updated_at = datetime.now(timezone.utc)
    auth.db.commit()
    auth.db.refresh(conversation)
    return _conversation_out(conversation)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, auth: AuthContext = Depends(require_role("editor"))):
    conversation = _conversation(auth, conversation_id)
    conversation.deleted_at = conversation.updated_at = datetime.now(timezone.utc)
    auth.db.commit()
    return Response(status_code=204)


# ---- Run creation (gateway only, no execution) ----

@router.post("/conversations/{conversation_id}/runs", status_code=201)
def create_conversation_run(conversation_id: str, body: ConversationRunRequest, auth: AuthContext = Depends(require_role("editor"))):
    conversation = _conversation(auth, conversation_id)
    if body.idempotency_key:
        existing = auth.db.query(ChatTurn).filter_by(conversation_id=conversation.id, idempotency_key=body.idempotency_key).first()
        if existing:
            return _turn_out(existing, auth.db)
    pending = auth.db.query(ChatTurn).filter(
        ChatTurn.conversation_id == conversation.id, ChatTurn.status.in_(("pending", "running")),
    ).first()
    if pending:
        raise HTTPException(status_code=409, detail="Conversation already has a pending run")
    sequence = (auth.db.query(func.max(ChatTurn.sequence)).filter_by(conversation_id=conversation.id).scalar() or 0) + 1
    if sequence == 1 and conversation.title == "New conversation":
        conversation.title = " ".join(body.message.strip().split())[:80]
    turn = ChatTurn(project_id=auth.project_id, conversation_id=conversation.id, sequence=sequence, idempotency_key=body.idempotency_key, message=body.message)
    auth.db.add(turn)
    auth.db.flush()
    run = ChatRun(project_id=auth.project_id, registration_id=conversation.registration_id, conversation_id=conversation.id, turn_id=turn.id, idempotency_key=body.idempotency_key, session_id=conversation.session_id, message=body.message)
    auth.db.add(run)
    auth.db.flush()
    conversation.updated_at = datetime.now(timezone.utc)
    try:
        auth.db.commit()
    except IntegrityError:
        auth.db.rollback()
        if body.idempotency_key:
            existing = auth.db.query(ChatTurn).filter_by(conversation_id=conversation.id, idempotency_key=body.idempotency_key).first()
            if existing:
                return _turn_out(existing, auth.db)
        raise
    auth.db.refresh(turn)
    return _turn_out(turn, auth.db)


# ---- SSE events (no inline execution) ----

@router.get("/runs/{run_id}/events")
def stream_run(run_id: str, auth: AuthContext = Depends(require_role("editor"))):
    run = auth.db.query(ChatRun).filter_by(id=run_id, project_id=auth.project_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Chat run not found")
    return StreamingResponse(_stream_events(auth.db, run), media_type="text/event-stream")


@router.get("/conversations/{conversation_id}/runs/{run_id}/events")
def stream_conversation_run(conversation_id: str, run_id: str, auth: AuthContext = Depends(require_role("editor"))):
    _conversation(auth, conversation_id)
    run = auth.db.query(ChatRun).filter_by(id=run_id, project_id=auth.project_id, conversation_id=conversation_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Chat run not found")
    return StreamingResponse(_stream_events(auth.db, run), media_type="text/event-stream")


def _stream_events(db, run: ChatRun) -> Iterator[str]:
    """SSE event generator — dispatches to external agent endpoint or fails with a clear message."""
    yield _event("run.started", {"run_id": run.id, "session_id": run.session_id})
    if run.status == "completed":
        yield _event("message.completed", {"run_id": run.id, "content": run.output, "trace_id": run.trace_id})
        yield _event("run.completed", {"run_id": run.id, "status": "completed"})
        return
    if run.status == "failed":
        yield _event("run.failed", {"run_id": run.id, "error": run.error or "Chat runtime failed", "trace_id": run.trace_id})
        return
    if run.status != "pending":
        yield _event("run.pending", {"run_id": run.id, "status": run.status})
        return

    registration = db.get(EnvironmentRegistration, run.registration_id)
    endpoint = registration.chat_endpoint if registration else None
    if endpoint:
        if not safe_endpoint(endpoint, get_settings()):
            run.status = "failed"
            run.error = "Chat endpoint rejected by SSRF protection"
            run.completed_at = datetime.now(timezone.utc)
            if run.turn_id:
                turn = db.get(ChatTurn, run.turn_id)
                if turn:
                    turn.status, turn.error, turn.completed_at = "failed", run.error, run.completed_at
            db.commit()
            yield _event("run.failed", {"run_id": run.id, "error": run.error, "trace_id": None})
            return
        try:
            import httpx
            resp = httpx.post(endpoint, json={"message": run.message}, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("output", "")
                trace_id = data.get("trace_id", run.id)
            else:
                run.status = "failed"
                run.error = f"Agent returned {resp.status_code}"
                db.commit()
                yield _event("run.failed", {"run_id": run.id, "error": run.error, "trace_id": None})
                return
        except Exception as exc:
            run.status = "failed"
            run.error = f"Agent dispatch failed: {exc}"
            db.commit()
            yield _event("run.failed", {"run_id": run.id, "error": run.error, "trace_id": None})
            return
    else:
        run.status = "failed"
        run.error = "This registration has no chat_endpoint configured. The agent runtime is not available for chat."
        run.completed_at = datetime.now(timezone.utc)
        if run.turn_id:
            turn = db.get(ChatTurn, run.turn_id)
            if turn:
                turn.status, turn.error, turn.completed_at = "failed", run.error, run.completed_at
        db.commit()
        yield _event("run.failed", {"run_id": run.id, "error": run.error, "trace_id": None})
        return

    run.status = "completed"
    run.output = content
    run.trace_id = trace_id
    run.completed_at = datetime.now(timezone.utc)
    if run.turn_id:
        turn = db.get(ChatTurn, run.turn_id)
        if turn:
            turn.output, turn.trace_id, turn.status, turn.completed_at = content, trace_id, "completed", run.completed_at
    db.commit()
    yield _event("message.completed", {"run_id": run.id, "content": content, "trace_id": trace_id})
    yield _event("run.completed", {"run_id": run.id, "status": "completed"})


def _event(event: str, body: dict) -> str:
    raw = json.dumps(body, separators=(",", ":"), ensure_ascii=True)
    lines = [f"data: {line}" for line in raw.split("\n")]
    return f"event: {event}\n" + "\n".join(lines) + "\n\n"


# ---- Callback (external runtime posts result here) ----

@router.post("/runs/{run_id}/callback/complete")
def complete_run(run_id: str, body: RunCompleteBody, auth: AuthContext = Depends(require_role("editor"))):
    run = auth.db.query(ChatRun).filter_by(id=run_id, project_id=auth.project_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Chat run not found")
    if run.status == "completed":
        raise HTTPException(status_code=409, detail="Chat run is already completed")
    run.status = "completed"
    run.output = body.output
    run.trace_id = body.trace_id
    run.error = None
    run.completed_at = datetime.now(timezone.utc)
    if run.turn_id:
        turn = auth.db.get(ChatTurn, run.turn_id)
        if turn:
            turn.output, turn.trace_id, turn.status, turn.error, turn.completed_at = body.output, body.trace_id, "completed", None, run.completed_at
    auth.db.commit()
    return {"run_id": run.id, "status": "completed"}


@router.post("/runs/{run_id}/callback/fail")
def fail_run(run_id: str, body: RunCompleteBody, auth: AuthContext = Depends(require_role("editor"))):
    run = auth.db.query(ChatRun).filter_by(id=run_id, project_id=auth.project_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Chat run not found")
    if run.status == "completed":
        raise HTTPException(status_code=409, detail="Chat run is already completed")
    run.status = "failed"
    run.error = (body.error or "Runtime error")[:2000]
    run.completed_at = datetime.now(timezone.utc)
    if run.turn_id:
        turn = auth.db.get(ChatTurn, run.turn_id)
        turn.status, turn.error, turn.completed_at = "failed", run.error, run.completed_at
    auth.db.commit()
    return {"run_id": run.id, "status": "failed"}


# ---- Legacy: create run without a conversation ----

@router.post("/runs", status_code=201)
def create_run(body: ConversationRunRequest, auth: AuthContext = Depends(require_role("editor"))):
    run = ChatRun(project_id=auth.project_id, registration_id="", session_id=f"chat_{uuid.uuid4().hex[:16]}", message=body.message)
    auth.db.add(run)
    auth.db.commit()
    auth.db.refresh(run)
    return {"run_id": run.id, "session_id": run.session_id, "status": run.status}


# ---- Legacy fallback for channel webhooks ----

def execute_chat_run(db, run: ChatRun) -> ChatRun:
    """Legacy fallback for channel webhooks — produces a deterministic response without a model."""
    if run.status in ("completed", "failed", "running"):
        return run
    run.status = "completed"
    run.output = f"{run.message[:200]} (processed)"
    run.completed_at = datetime.now(timezone.utc)
    if run.turn_id:
        turn = db.get(ChatTurn, run.turn_id)
        if turn:
            turn.output, turn.status, turn.completed_at = run.output, "completed", run.completed_at
    db.commit()
    return run