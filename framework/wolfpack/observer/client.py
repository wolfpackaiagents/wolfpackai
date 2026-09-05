"""Observer client: sends spans/observations to the Wolfpack Control Plane (AMP).

`WolfpackObserver` implements the `Tracker` contract and does batched buffering
with retry on flush failure and PII redaction.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..guardrails.base import PIIGuardrail
from ..mesh import MeshIdentity

logger = logging.getLogger(__name__)

KIND_TO_OBS = {"llm_call": "GENERATION", "tool": "TOOL", "agent_step": "SPAN", "retriever": "RETRIEVER"}


def _iso(ts: Optional[float] = None) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


class WolfpackObserver:
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        project: Optional[str] = None,
        max_batch: int = 32,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        deployment: Optional[MeshIdentity] = None,
        redact_pii: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("WOLFPACK_AMP_API_KEY")
        self.project = project
        self.max_batch = max_batch
        self.session_id = session_id
        self.user_id = user_id
        self.metadata = metadata
        self.deployment = deployment
        self._pii_guardrail = PIIGuardrail() if redact_pii else None
        self._buffer: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._trace_for_span: Dict[str, str] = {}  # span id -> trace id (to know the root for non-root spans)

    # --- Tracker contract (used by the Agent) ---

    def start_trace(self, name: str, run_id: Optional[str] = None) -> Dict[str, str]:
        trace_id = run_id or f"trace_{uuid.uuid4().hex}"
        self._trace_for_span[trace_id] = trace_id
        trace = {"id": trace_id, "name": name, "start": time.time(), "trace_id": trace_id, "kind": "TRACE"}
        self.start_event_for({
            "id": trace_id,
            "trace_id": trace_id,
            "type": "TRACE",
            "name": name,
            "start_time": _iso(trace["start"]),
            "environment": self.deployment.environment_slug if self.deployment else None,
            "metadata": self._event_metadata(),
        })
        return trace

    def end_trace(self, trace, input=None, output=None, usage=None, error=None):
        self._enqueue_update(trace, input=input, output=output, usage=usage, error=error, kind="TRACE")

    def start_span(
        self, kind: str, name: str, span_type: Optional[str] = None, parent: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        span_id = f"span_{uuid.uuid4().hex[:12]}"
        trace_id = self._last_trace_id()
        if trace_id:
            self._trace_for_span[span_id] = trace_id
        span = {
            "id": span_id,
            "kind": KIND_TO_OBS.get(kind, span_type or "SPAN"),
            "start": time.time(),
            "name": name,
            "trace_id": trace_id,
            "parent_observation_id": parent.get("id") if parent else trace_id,
        }
        self.start_event_for({
            "id": span_id,
            "trace_id": trace_id,
            "parent_observation_id": span["parent_observation_id"],
            "type": span["kind"],
            "name": name,
            "start_time": _iso(span["start"]),
            "model": name if span["kind"] == "GENERATION" else None,
            "metadata": self._event_metadata(),
        })
        return span

    def end_span(self, span: Dict[str, Any], usage=None, status="OK", error=None, input=None, output=None, cost=None):
        self._enqueue_update(span, input=input, output=output, usage=usage, error=error, cost=cost, span_only=True)

    def end_tool_span(self, span: Dict[str, Any], result=None, error=None):
        self._enqueue_update(span, output=result, error=error, span_only=True)

    def _last_trace_id(self) -> Optional[str]:
        for v in reversed(list(self._trace_for_span.values())):
            return v
        return None

    # --- event assembly in the AMP format ---

    def _enqueue_update(self, span: Dict[str, Any], input=None, output=None, usage=None, error=None, cost=None, kind=None, span_only=False):
        span_id = span.get("id")
        trace_id = span.get("trace_id") or self._trace_for_span.get(span_id)
        body: Dict[str, Any] = {
            "id": trace_id if not span_only and kind == "TRACE" else span_id,
            "type": kind or span.get("kind", "SPAN"),
            "name": span.get("name") or trace_id,
            "start_time": _iso(span.get("start")),
            "end_time": _iso(span.get("end") or time.time()),
            "metadata": self._event_metadata(),
        }
        if not span_only and kind == "TRACE":
            body["trace_id"] = trace_id
            if trace_id:
                self._trace_for_span[trace_id] = trace_id
        else:
            body["trace_id"] = trace_id
            body["parent_observation_id"] = span.get("parent_observation_id") or trace_id
            body["type"] = span.get("kind", "SPAN")
        if input is not None:
            body["input"] = input
        if output is not None:
            body["output"] = output
        if not span_only and kind == "TRACE":
            if self.session_id:
                body["session_id"] = self.session_id
            if self.user_id:
                body["user_id"] = self.user_id
            if self.metadata:
                body["metadata"] = self._event_metadata()
            if self.deployment:
                body["environment"] = self.deployment.environment_slug
        body["model"] = span.get("name") if span.get("kind") == "GENERATION" else None
        if usage:
            body["usage"] = usage
        if cost is not None:
            if hasattr(cost, "to_dict"):
                cost_dict = cost.to_dict()
                body["cost"] = cost_dict.get("amount")
                body["cost_currency"] = cost_dict.get("currency")
                body["cost_source"] = cost_dict.get("source")
            elif isinstance(cost, dict):
                body["cost"] = cost.get("amount")
                body["cost_currency"] = cost.get("currency")
                body["cost_source"] = cost.get("source")
            else:
                body["cost"] = cost
        if error:
            body["error"] = str(error)

        event: Dict[str, Any] = {
            "id": uuid.uuid4().hex,
            "type": "observation-end",
            "timestamp": body["end_time"],
            "body": body,
        }
        self._enqueue(event)

    def start_event_for(self, body: Dict[str, Any], event_type: str = "observation-start") -> None:
        """Helper: emits a manual 'start' event (e.g. before end_scalar)."""
        ev = {"id": uuid.uuid4().hex, "type": event_type, "timestamp": _iso(), "body": body}
        self._enqueue(ev)

    def _event_metadata(self) -> Dict[str, Any]:
        metadata = dict(self.metadata or {})
        if self.deployment:
            metadata["mesh"] = self.deployment.metadata()
        return metadata

    def start_for_approval(self, requirement: Any) -> None:
        """Publishes a pending approval as an observation event (HITL pause)."""
        body = {
            "id": requirement.approval_id or requirement.id,
            "trace_id": requirement.run_id,
            "type": "EVENT",
            "name": f"approval.{requirement.tool_name}",
            "start_time": _iso(requirement.created_at),
            "metadata": {
                "requirement": requirement.requirement,
                "tool_name": requirement.tool_name,
                "tool_arguments": requirement.tool_arguments,
                "status": "pending",
            },
        }
        self._enqueue({"id": uuid.uuid4().hex, "type": "observation-start", "timestamp": _iso(), "body": body})

    def end_for_approval(self, requirement: Any) -> None:
        """Closes the approval observation reflecting the resolution status."""
        body = {
            "id": requirement.approval_id or requirement.id,
            "trace_id": requirement.run_id,
            "parent_observation_id": requirement.run_id,
            "name": f"approval.{requirement.tool_name}",
            "type": "EVENT",
            "start_time": _iso(requirement.created_at),
            "end_time": _iso(),
            "metadata": {
                "requirement": requirement.requirement,
                "status": requirement.status,
                "confirmation": requirement.confirmation,
                "user_input": requirement.user_input,
                "note": requirement.confirmation_note,
            },
        }
        self._enqueue({"id": uuid.uuid4().hex, "type": "observation-end", "timestamp": _iso(), "body": body})

    def record_interaction(self, source: str, target: str, interaction_type: str = "delegation", trace_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None, operation: Optional[str] = None, tool_name: Optional[str] = None, source_display_name: Optional[str] = None, target_display_name: Optional[str] = None) -> None:
        """Publishes an agent-to-agent relation for the Mesh graph."""
        body = {
            "type": "EVENT",
            "trace_id": trace_id,
            "metadata": {"mesh_interaction": {"source": source, "target": target, "interaction_type": interaction_type, "operation": operation, "tool_name": tool_name, "source_display_name": source_display_name, "target_display_name": target_display_name, "metadata": metadata or {}}},
        }
        self._enqueue({"id": uuid.uuid4().hex, "type": "mesh-interaction", "timestamp": _iso(), "body": body})

    def heartbeat(self, instance_id: str, version: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Renew this deployment replica's liveness lease without affecting agent work."""
        if not self.deployment:
            return False
        import urllib.request

        payload = json.dumps({"instance_id": instance_id, "version": version or self.deployment.definition_version, "metadata": metadata or {}}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/public/mesh/registrations/{self.deployment.registration_id}/heartbeat",
            data=payload,
            headers={"Content-Type": "application/json", "X-API-Key": self.api_key or ""},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200
        except Exception:
            return False

    # --- batching / sending ---

    def _enqueue(self, event: Dict[str, Any]) -> None:
        if self._pii_guardrail:
            event = self._redact_event(event)
        with self._lock:
            self._buffer.append(event)
            if len(self._buffer) >= self.max_batch:
                batch = list(self._buffer)
                self._buffer = []
            else:
                batch = None
        if batch:
            self._flush(batch)

    def _redact_event(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._pii_guardrail.check(value).result
        if isinstance(value, dict):
            return {key: self._redact_event(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._redact_event(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self._redact_event(item) for item in value)
        return value

    def flush(self) -> None:
        with self._lock:
            if not self._buffer:
                return
            batch = list(self._buffer)
            self._buffer = []
        self._flush(batch)

    def _flush(self, events: List[Dict[str, Any]]) -> None:
        import urllib.request

        url = f"{self.base_url}/api/public/ingestion"
        payload = json.dumps({"events": events}).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "X-API-Key": self.api_key or ""},
            method="POST",
        )
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp.read()
                return
            except Exception as exc:
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                logger.warning("Failed to flush %d events to AMP after %d attempts: %s", len(events), max_retries, exc)
