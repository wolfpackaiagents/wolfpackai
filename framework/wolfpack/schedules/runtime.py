"""HTTP runtime contract for executing AMP scheduled task dispatches."""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field


def sign_schedule_payload(secret: str, body: bytes) -> str:
    """Return the signature used for dispatches and control-plane callbacks."""
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify_schedule_payload(secret: str, body: bytes, signature: str | None) -> bool:
    return bool(secret and signature and hmac.compare_digest(sign_schedule_payload(secret, body), signature))


class RuntimeDispatch(BaseModel):
    """Immutable task attempt sent to the selected runtime replica."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    schedule_id: str = Field(min_length=1)
    fencing_token: int = Field(ge=1)
    attempt: int = Field(ge=1)
    target_instance_id: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    deadline_at: str | None = None


class RuntimeContext:
    """Execution context passed to a runtime task handler."""

    def __init__(self, dispatch: RuntimeDispatch, cancelled: threading.Event):
        self.dispatch = dispatch
        self._cancelled = cancelled

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()


class HttpRuntimeRunner:
    """Verifies signed dispatches, executes them once, and reports the outcome.

    ``handler`` receives a :class:`RuntimeContext` and returns a JSON-compatible
    dictionary. Dispatch acknowledgement is immediate; execution and callbacks
    happen on a bounded worker pool.
    """

    def __init__(self, instance_id: str, dispatch_secret: str, callback_secret: str, control_plane_url: str, handler: Callable[[RuntimeContext], dict[str, Any] | None], max_concurrency: int = 1, timeout: float = 10.0):
        if not instance_id or not dispatch_secret or not callback_secret:
            raise ValueError("instance_id, dispatch_secret, and callback_secret are required")
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least one")
        self.instance_id = instance_id
        self.dispatch_secret = dispatch_secret
        self.callback_secret = callback_secret
        self.control_plane_url = control_plane_url.rstrip("/")
        self.handler = handler
        self.timeout = timeout
        self._executor = ThreadPoolExecutor(max_workers=max_concurrency, thread_name_prefix="wolfpack-runtime")
        self._active: dict[tuple[str, int], threading.Event] = {}
        self._seen: set[tuple[str, int]] = set()
        self._lock = threading.Lock()

    def handle_dispatch(self, body: bytes, signature: str | None) -> dict[str, Any]:
        """Validate and accept a raw HTTP dispatch body for an adapter to return."""
        if not verify_schedule_payload(self.dispatch_secret, body, signature):
            raise PermissionError("invalid schedule dispatch signature")
        dispatch = RuntimeDispatch.model_validate_json(body)
        if dispatch.target_instance_id != self.instance_id:
            raise PermissionError("dispatch targets a different runtime replica")
        key = (dispatch.run_id, dispatch.fencing_token)
        with self._lock:
            if key in self._active or key in self._seen:
                return {"status": "accepted", "duplicate": True}
            cancelled = threading.Event()
            self._active[key] = cancelled
        self._executor.submit(self._run, dispatch, cancelled)
        return {"status": "accepted", "run_id": dispatch.run_id}

    def cancel(self, run_id: str) -> bool:
        """Request cooperative cancellation of an active task."""
        with self._lock:
            cancelled = next((event for (active_run_id, _), event in self._active.items() if active_run_id == run_id), None)
        if not cancelled:
            return False
        cancelled.set()
        return True

    def _run(self, dispatch: RuntimeDispatch, cancelled: threading.Event) -> None:
        try:
            if cancelled.is_set():
                raise RuntimeError("run cancelled")
            result = self.handler(RuntimeContext(dispatch, cancelled)) or {}
            if cancelled.is_set():
                raise RuntimeError("run cancelled")
            self._callback(dispatch.run_id, "complete", {"fencing_token": dispatch.fencing_token, "result": result})
        except Exception as error:
            self._callback(dispatch.run_id, "fail", {"fencing_token": dispatch.fencing_token, "error": str(error)[:4000]})
        finally:
            with self._lock:
                key = (dispatch.run_id, dispatch.fencing_token)
                self._active.pop(key, None)
                self._seen.add(key)

    def renew(self, dispatch: RuntimeDispatch) -> None:
        """Renew a long-running task lease from inside a cooperative handler."""
        self._callback(dispatch.run_id, "renew", {"fencing_token": dispatch.fencing_token, "worker_id": self.instance_id})

    def _callback(self, run_id: str, action: str, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        request = urllib.request.Request(
            f"{self.control_plane_url}/api/public/schedules/runs/{run_id}/callback/{action}",
            data=body,
            headers={"Content-Type": "application/json", "X-Wolfpack-Schedule-Signature": sign_schedule_payload(self.callback_secret, body)},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout):
            pass
