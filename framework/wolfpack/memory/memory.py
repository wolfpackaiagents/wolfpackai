"""Session memory for the Agent (MVP): short-term conversation in memory.
CrewAI pattern: short/long-term with pluggable storage; here the minimalist agno
approach (in-memory session state) for multi-turn conversations.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models.message import Message


class SessionMemory:
    """Stores a session's messages and lets an Agent follow a conversation."""

    def __init__(self, session_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        self.session_id = session_id or "default"
        self.messages: List[Message] = []
        self.metadata: Dict[str, Any] = metadata or {}

    def add_message(self, message: Message) -> None:
        self.messages.append(message)

    def add_user_message(self, content: str) -> Message:
        m = Message(role="user", content=content)
        self.add_message(m)
        return m

    def add_assistant_message(self, content: str) -> Message:
        m = Message(role="assistant", content=content)
        self.add_message(m)
        return m

    def get_messages(self, max_messages: Optional[int] = None) -> List[Dict[str, Any]]:
        msgs = self.messages[-max_messages:] if max_messages else self.messages
        return [m.to_dict() for m in msgs]

    def clear(self) -> None:
        self.messages = []
        self.metadata = {}

    def __len__(self):
        return len(self.messages)


class SessionStore(ABC):
    """Pluggable persistence for short-term session memory."""

    @abstractmethod
    def create_session(self, session_id: Optional[str] = None) -> SessionMemory:
        ...

    @abstractmethod
    def get(self, session_id: str) -> Optional[SessionMemory]:
        ...

    def get_or_create(self, session_id: str) -> SessionMemory:
        return self.get(session_id) or self.create_session(session_id)

    @abstractmethod
    def save(self, session: SessionMemory) -> None:
        ...

    @abstractmethod
    def delete(self, session_id: str) -> None:
        ...


class InMemorySessionStore(SessionStore):
    def __init__(self):
        self._sessions: Dict[str, SessionMemory] = {}
        self._lock = threading.Lock()

    def create_session(self, session_id: Optional[str] = None) -> SessionMemory:
        session_id = session_id or "default"
        with self._lock:
            session = SessionMemory(session_id=session_id)
            self._sessions[session_id] = session
            return session

    def get(self, session_id: str) -> Optional[SessionMemory]:
        with self._lock:
            return self._sessions.get(session_id)

    def get_or_create(self, session_id: str) -> SessionMemory:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionMemory(session_id=session_id)
            return self._sessions[session_id]

    def save(self, session: SessionMemory) -> None:
        with self._lock:
            self._sessions[session.session_id] = session

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


class SQLiteSessionStore(SessionStore):
    """Durable standalone session store used when AMP is not configured."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(Path.home() / ".wolfpack" / "sessions.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        messages TEXT NOT NULL,
                        metadata TEXT NOT NULL,
                        updated_at REAL NOT NULL
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def create_session(self, session_id: Optional[str] = None) -> SessionMemory:
        session = SessionMemory(session_id=session_id)
        self.save(session)
        return session

    def get(self, session_id: str) -> Optional[SessionMemory]:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT messages, metadata FROM sessions WHERE session_id=?", (session_id,)
                ).fetchone()
            finally:
                conn.close()
        if row is None:
            return None
        session = SessionMemory(session_id=session_id, metadata=json.loads(row["metadata"]))
        session.messages = [Message(**message) for message in json.loads(row["messages"])]
        return session

    def save(self, session: SessionMemory) -> None:
        messages = [message.to_dict() for message in session.messages]
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO sessions (session_id, messages, metadata, updated_at) VALUES (?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        messages=excluded.messages, metadata=excluded.metadata, updated_at=excluded.updated_at
                    """,
                    (session.session_id, json.dumps(messages), json.dumps(session.metadata), time.time()),
                )
                conn.commit()
            finally:
                conn.close()

    def delete(self, session_id: str) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
                conn.commit()
            finally:
                conn.close()
