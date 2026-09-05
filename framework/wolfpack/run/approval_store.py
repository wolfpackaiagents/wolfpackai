"""ApprovalStore: where pending run requirements live.

The framework is provider-agnostic and works without AMP:
  - `LocalApprovalStore`  (SQLite file, default) — durable resume without backend.
  - `AmpApprovalStore`    (the Wolfpack Control Plane via `WolfpackObserver`) —
    centralized approvals + audit trail when `WOLFPACK_AMP_URL` is configured.
  - `MemoryApprovalStore` (no persistence, for tests/short-lived processes).

A run pauses by persisting its pending `RunRequirement`s here; `agent.continue_run()`
loads the run's requirements, applies any resolutions, and either resumes the tool
loop or stays paused.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from .requirement import RunRequirement


class ApprovalStore(ABC):
    @abstractmethod
    def create_requirement(self, req: RunRequirement) -> None:
        ...

    @abstractmethod
    def update_requirement(self, req: RunRequirement) -> None:
        ...

    @abstractmethod
    def get_requirements(self, run_id: str) -> List[RunRequirement]:
        ...

    @abstractmethod
    def get_requirement(self, approval_id: str) -> Optional[RunRequirement]:
        ...

    @abstractmethod
    def save_checkpoint(self, run_id: str, payload: List[Dict[str, Any]]) -> None:
        ...

    @abstractmethod
    def get_checkpoint(self, run_id: str) -> Optional[List[Dict[str, Any]]]:
        ...

    def resolve(self, run_id: str, approval_id: str, action: str, **payload: Any) -> RunRequirement:
        req = self.get_requirement(approval_id)
        if req is None:
            raise KeyError(f"No requirement with approval_id={approval_id}")
        if action == "approve":
            req.confirm()
        elif action == "reject":
            req.reject(payload.get("note"))
        elif action == "user_input":
            req.provide_user_input(payload.get("values", {}))
        elif action == "feedback":
            req.provide_feedback(payload.get("values", {}))
        elif action == "external_result":
            req.set_external_execution_result(payload.get("result", ""))
        else:
            raise ValueError(f"Unknown action: {action} (approve|reject|user_input|feedback|external_result)")
        self.update_requirement(req)
        return req


class MemoryApprovalStore(ApprovalStore):
    def __init__(self):
        self._reqs: Dict[str, RunRequirement] = {}
        self._by_run: Dict[str, List[str]] = {}
        self._checkpoints: Dict[str, List[Dict[str, Any]]] = {}

    def create_requirement(self, req: RunRequirement) -> None:
        self._reqs[req.id] = req
        self._by_run.setdefault(req.run_id, []).append(req.id)

    def update_requirement(self, req: RunRequirement) -> None:
        self._reqs[req.id] = req

    def get_requirements(self, run_id: str) -> List[RunRequirement]:
        return [self._reqs[i] for i in self._by_run.get(run_id, []) if i in self._reqs]

    def get_requirement(self, approval_id: str) -> Optional[RunRequirement]:
        for req in self._reqs.values():
            if req.approval_id == approval_id or req.id == approval_id:
                return req
        return None

    def save_checkpoint(self, run_id: str, payload: List[Dict[str, Any]]) -> None:
        self._checkpoints[run_id] = payload

    def get_checkpoint(self, run_id: str) -> Optional[List[Dict[str, Any]]]:
        return self._checkpoints.get(run_id)


class LocalApprovalStore(ApprovalStore):
    """SQLite-backed store. Durable across processes; default for standalone use."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(Path.home() / ".wolfpack" / "approvals.db")
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
                    CREATE TABLE IF NOT EXISTS requirements (
                        id TEXT PRIMARY KEY,
                        run_id TEXT NOT NULL,
                        approval_id TEXT,
                        payload TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        created_at REAL
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS ix_req_run ON requirements(run_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS ix_req_approval ON requirements(approval_id)")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS run_checkpoints (
                        run_id TEXT PRIMARY KEY,
                        payload TEXT NOT NULL
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def _save(self, req: RunRequirement) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO requirements (id, run_id, approval_id, payload, status, created_at)
                    VALUES (?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                        payload=excluded.payload, status=excluded.status
                    """,
                    (req.id, req.run_id, req.approval_id, json.dumps(req.to_dict()), req.status, req.created_at),
                )
                conn.commit()
            finally:
                conn.close()

    def create_requirement(self, req: RunRequirement) -> None:
        self._save(req)

    def update_requirement(self, req: RunRequirement) -> None:
        self._save(req)

    def get_requirements(self, run_id: str) -> List[RunRequirement]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute("SELECT payload FROM requirements WHERE run_id=?", (run_id,)).fetchall()
                return [RunRequirement.from_dict(json.loads(r["payload"])) for r in rows]
            finally:
                conn.close()

    def get_requirement(self, approval_id: str) -> Optional[RunRequirement]:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT payload FROM requirements WHERE approval_id=? OR id=?",
                    (approval_id, approval_id),
                ).fetchone()
                return RunRequirement.from_dict(json.loads(row["payload"])) if row else None
            finally:
                conn.close()

    def save_checkpoint(self, run_id: str, payload: List[Dict[str, Any]]) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO run_checkpoints (run_id, payload) VALUES (?, ?)
                    ON CONFLICT(run_id) DO UPDATE SET payload=excluded.payload
                    """,
                    (run_id, json.dumps(payload)),
                )
                conn.commit()
            finally:
                conn.close()

    def get_checkpoint(self, run_id: str) -> Optional[List[Dict[str, Any]]]:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT payload FROM run_checkpoints WHERE run_id=?", (run_id,)
                ).fetchone()
                return json.loads(row["payload"]) if row else None
            finally:
                conn.close()

    def delete_run(self, run_id: str) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM requirements WHERE run_id=?", (run_id,))
                conn.execute("DELETE FROM run_checkpoints WHERE run_id=?", (run_id,))
                conn.commit()
            finally:
                conn.close()


class AmpApprovalStore(ApprovalStore):
    """Centralized store backed by the AMP Control Plane (via the observer client).

    Requires the observer to expose a synchronous HTTP contract for approval CRUD.
    Falls back gracefully when the AMP is unreachable: requirements are kept in a
    local in-memory copy so the run can still resume.
    """

    def __init__(self, observer: Any = None, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self._observer = observer
        self._base_url = base_url
        self._api_key = api_key
        self._local: MemoryApprovalStore = MemoryApprovalStore()

    def _http(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        import urllib.request

        url = self._base_url or (self._observer.base_url if self._observer else None)
        if not url:
            return None
        req = urllib.request.Request(
            f"{url.rstrip('/')}/api/public{path}",
            data=json.dumps(payload).encode() if payload else None,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": self._api_key or (self._observer.api_key if self._observer else ""),
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            return None  # AMP unreachable -> local mirror stays authoritative

    def create_requirement(self, req: RunRequirement) -> None:
        self._local.create_requirement(req)
        self._http(
            "POST",
            "/approvals",
            {
                "run_id": req.run_id,
                "approval_id": req.approval_id,
                "tool_name": req.tool_name,
                "tool_arguments": req.tool_arguments,
                "requirement": req.requirement,
                "tool_call_id": req.tool_call_id,
                "metadata": req.to_dict(),
            },
        )
        if self._observer:
            self._observer.start_for_approval(req)

    def update_requirement(self, req: RunRequirement) -> None:
        self._local.update_requirement(req)
        if self._observer:
            self._observer.end_for_approval(req)
        action: Optional[str] = None
        body: Dict[str, Any] = {}
        if req.requirement == "confirmation":
            action = "approve" if req.confirmation else "reject"
            body["note"] = req.confirmation_note
        elif req.requirement == "user_input":
            action = "user_input"
            body["values"] = req.user_input
        elif req.requirement == "feedback":
            action = "feedback"
            body["values"] = req.feedback
        elif req.requirement == "external_execution":
            action = "external_result"
            body["result"] = req.external_execution_result
        if req.approval_id and action:
            self._http("POST", f"/approvals/{req.approval_id}/resolve", {"action": action, **body})

    def get_requirements(self, run_id: str) -> List[RunRequirement]:
        requirements = self._local.get_requirements(run_id)
        for req in requirements:
            if not req.approval_id:
                continue
            remote = self._http("GET", f"/approvals/{req.approval_id}")
            if not remote:
                continue
            req.status = remote.get("status", req.status)
            req.confirmation = remote.get("confirmation", req.confirmation)
            req.confirmation_note = remote.get("confirmation_note", req.confirmation_note)
            req.user_input = remote.get("user_input", req.user_input)
            req.feedback = remote.get("feedback", req.feedback)
            req.external_execution_result = remote.get(
                "external_execution_result", req.external_execution_result
            )
            self._local.update_requirement(req)
        return requirements

    def get_requirement(self, approval_id: str) -> Optional[RunRequirement]:
        return self._local.get_requirement(approval_id)

    def save_checkpoint(self, run_id: str, payload: List[Dict[str, Any]]) -> None:
        self._local.save_checkpoint(run_id, payload)

    def get_checkpoint(self, run_id: str) -> Optional[List[Dict[str, Any]]]:
        return self._local.get_checkpoint(run_id)


def default_store(**kwargs: Any) -> ApprovalStore:
    """Returns the store chosen by the environment:
    AMP store when WOLFPACK_AMP_URL is set, else local SQLite.

    The framework works fully without AMP; AMP is recommended but optional.
    """
    import os

    if os.environ.get("WOLFPACK_AMP_URL"):
        return AmpApprovalStore(
            base_url=os.environ.get("WOLFPACK_AMP_URL"),
            api_key=os.environ.get("WOLFPACK_AMP_API_KEY"),
        )
    return LocalApprovalStore(kwargs.get("db_path"))
