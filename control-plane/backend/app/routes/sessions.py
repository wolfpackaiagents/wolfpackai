"""Session views derived from project traces."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.auth import resolve_project_id
from ..models.entities import Trace

router = APIRouter(prefix="/api/public/sessions")


@router.get("")
def list_sessions(
    environment_id: Optional[str] = None,
    registration_id: Optional[str] = None,
    from_: Optional[datetime] = Query(default=None, alias="from"),
    to: Optional[datetime] = None,
    auth: Tuple[str, Session] = Depends(resolve_project_id),
):
    project_id, db = auth
    query = db.query(Trace).filter(Trace.project_id == project_id, Trace.session_id.is_not(None))
    if environment_id:
        query = query.filter(Trace.environment_id == environment_id)
    if registration_id:
        query = query.filter(Trace.registration_id == registration_id)
    if from_:
        query = query.filter(Trace.timestamp >= from_)
    if to:
        query = query.filter(Trace.timestamp <= to)
    traces = query.order_by(Trace.timestamp.desc()).all()
    sessions: Dict[str, dict] = {}
    for trace in traces:
        session = sessions.setdefault(
            trace.session_id,
            {"session_id": trace.session_id, "trace_count": 0, "last_trace_at": None, "user_id": trace.user_id},
        )
        session["trace_count"] += 1
        if session["last_trace_at"] is None:
            session["last_trace_at"] = trace.timestamp.isoformat() if trace.timestamp else None
    return list(sessions.values())


@router.get("/{session_id}")
def get_session(session_id: str, auth: Tuple[str, Session] = Depends(resolve_project_id)):
    project_id, db = auth
    traces = (
        db.query(Trace)
        .filter(Trace.project_id == project_id, Trace.session_id == session_id)
        .order_by(Trace.timestamp.asc())
        .all()
    )
    if not traces:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session_id,
        "user_id": traces[0].user_id,
        "traces": [
            {
                "id": trace.id,
                "name": trace.name,
                "timestamp": trace.timestamp.isoformat() if trace.timestamp else None,
                "input": trace.input,
                "output": trace.output,
                "error": trace.error,
            }
            for trace in traces
        ],
    }
