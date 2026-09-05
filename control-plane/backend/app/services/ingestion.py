"""Ingestion service: converts Observer SDK events into Traces and Observations.

Flow: the SDK sends `observation-start` / `observation-end` per span. Here they are
matched by `body.id`: a span without a trace_id is a root (type TRACE) and is
materialized as a Trace; the rest become Observations. An observation with a null
`parent_observation_id` is considered a trace root.

Analogy with langfuse: the trace is the root span; the observation is a span with
`parent_observation_id` when nested. MVP: synchronous merge in this API.

Language: comments in English.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models.entities import Environment, EnvironmentRegistration, MeshDefinition, MeshInteraction, Observation, Score, Trace
from ..schemas.contract import IngestionEvent, IngestionResult
from .cost_estimation import estimate_cost

KIND_TO_OBSERVATION_TYPE = {
    "GENERATION": "GENERATION",
    "llm_call": "GENERATION",
    "TOOL": "TOOL",
    "tool": "TOOL",
    "SPAN": "SPAN",
    "agent_step": "SPAN",
    "TRACE": "TRACE",
    "RETRIEVER": "RETRIEVER",
    "retriever": "RETRIEVER",
    "EVENT": "EVENT",
    "EMBEDDING": "EMBEDDING",
    "GUARDRAIL": "GUARDRAIL",
}


def _parse_iso(v: Optional[str]) -> Optional[datetime]:
    if not v:
        return None
    try:
        s = v.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class IngestionService:
    def __init__(self, db: Session, project_id: str):
        self.db = db
        self.project_id = project_id

    def process_batch(self, payload: Dict[str, Any]) -> IngestionResult:
        events: List[IngestionEvent] = []
        raw_events: List[Any] = payload.get("events", payload if isinstance(payload, list) else [])
        for e in raw_events:
            events.append(e if isinstance(e, IngestionEvent) else IngestionEvent(**e))

        result = IngestionResult()
        seen_ids: set[str] = set()
        pending: Dict[str, Dict[str, Any]] = {}
        starts_first = sorted(events, key=lambda e: 0 if e.type.endswith("-start") else 1)
        for ev in starts_first:
            if ev.id in seen_ids:
                result.successes.append({"id": ev.id, "status": "OK", "note": "duplicate"})
                continue
            seen_ids.add(ev.id)
            try:
                self._apply(ev, pending)
                result.successes.append({"id": ev.id, "status": "OK"})
            except Exception as exc:
                result.errors.append({"id": ev.id, "status": "ERROR", "error": str(exc)})
        # Ensure all trace totals reflect aggregated child observations.
        traced_ids: set[str] = set()
        for ev in events:
            trace_id = ev.body.trace_id if hasattr(ev.body, "trace_id") else ev.body.get("trace_id")
            if trace_id:
                traced_ids.add(trace_id)
        for tid in traced_ids:
            self._aggregate_trace_cost(tid)
        self._auto_evaluate_traces(traced_ids)
        self.db.commit()
        return result

    def _apply(self, ev: IngestionEvent, pending: Dict[str, Dict[str, Any]]) -> None:
        body = ev.body
        if ev.type == "mesh-interaction":
            self._materialize_interaction(body)
            return
        obs_id = body.id or f"obs_{ev.id}"
        obs_type = KIND_TO_OBSERVATION_TYPE.get(body.type, body.type or "SPAN")
        start = _parse_iso(body.start_time or body.timestamp)
        end = _parse_iso(body.end_time)

        if ev.type.endswith("-end"):
            data = pending.pop(obs_id, {})
            if not data:
                existing = self.db.get(Observation, obs_id)
                existing_trace = self.db.get(Trace, existing.trace_id) if existing else None
                data = {
                    "id": obs_id,
                    "type": existing.type if existing else obs_type,
                    "trace_id": existing.trace_id if existing else None,
                    "parent_observation_id": existing.parent_observation_id if existing else None,
                    "name": existing.name if existing else None,
                    "start_time": existing.start_time if existing else None,
                    "input": existing.input if existing else None,
                    "model": existing.model if existing else None,
                    "model_parameters": existing.model_parameters if existing else None,
                    "metadata": existing.metadata_field if existing else None,
                    "cost": existing.cost if existing else None,
                    "cost_currency": existing.cost_currency if existing else None,
                    "cost_source": existing.cost_source if existing else None,
                    "session_id": existing_trace.session_id if existing_trace else None,
                    "environment": existing.environment if existing else None,
                }
            # self-contained observations (no start): read the fields from the body itself
            if body.name:
                data["name"] = body.name
            if body.start_time or not data.get("start_time"):
                data["start_time"] = start
            if body.trace_id:
                data["trace_id"] = body.trace_id
            if body.parent_observation_id:
                data["parent_observation_id"] = body.parent_observation_id
            if body.input is not None:
                data["input"] = body.input
            if body.model:
                data["model"] = body.model
            if body.session_id:
                data["session_id"] = body.session_id
            if body.environment:
                data["environment"] = body.environment
            data["end_time"] = end or datetime.now(timezone.utc)
            data["output"] = body.output
            data["usage"] = body.usage
            if body.cost is not None:
                data["cost"] = body.cost
            if body.cost_currency is not None:
                data["cost_currency"] = body.cost_currency.upper()
            if body.cost_source is not None:
                data["cost_source"] = body.cost_source
            data["level"] = body.level or "DEFAULT"
            if body.error or body.status_message:
                data["status_message"] = body.error or body.status_message
                data["level"] = "ERROR" if body.error else data["level"]
            self._materialize(data, data.get("type") or obs_type)
        else:
            pending[obs_id] = {
                "id": obs_id,
                "type": obs_type,
                "parent_observation_id": body.parent_observation_id,
                "name": body.name or obs_id,
                "start_time": start or datetime.now(timezone.utc),
                "input": body.input,
                "model": body.model,
                "model_parameters": body.model_parameters,
                "metadata": body.metadata,
                "tags": body.tags,
                "session_id": body.session_id,
                "user_id": body.user_id,
                "environment": body.environment,
                "version": body.version,
                "release": body.release,
            }
            if body.cost is not None:
                pending[obs_id]["cost"] = body.cost
            if body.cost_currency is not None:
                pending[obs_id]["cost_currency"] = body.cost_currency.upper()
            if body.cost_source is not None:
                pending[obs_id]["cost_source"] = body.cost_source
            pending[obs_id]["trace_id"] = body.trace_id
            # Starts can arrive in a separate HTTP request from their ends. Persisting
            # them immediately preserves the original timestamp across batch boundaries.
            self._materialize(pending[obs_id], obs_type)

    def _materialize_interaction(self, body: Any) -> None:
        details = (body.metadata or {}).get("mesh_interaction", {})
        source = details.get("source")
        target = details.get("target")
        if not source or not target:
            raise ValueError("Mesh interaction requires source and target")
        self.db.add(MeshInteraction(
            project_id=self.project_id,
            trace_id=body.trace_id,
            source=source,
            target=target,
            source_display_name=details.get("source_display_name"),
            target_display_name=details.get("target_display_name"),
            interaction_type=details.get("interaction_type", "delegation"),
            operation=details.get("operation"),
            tool_name=details.get("tool_name"),
            metadata_field=details.get("metadata") or {},
        ))

    def _materialize(self, data: Dict[str, Any], obs_type: str) -> None:
        obs_id = data["id"]
        trace_id = data.get("trace_id") or (f"trace_{obs_id}" if obs_type == "TRACE" else obs_id)
        parent = data.get("parent_observation_id")

        # root of a trace = parentless observation; the Trace is materialized
        if not parent or obs_type == "TRACE":
            self._upsert_root_trace(trace_id, data)
        else:
            # if the trace has not arrived yet (spans before the root trace), create it
            self._ensure_trace_row(trace_id)

        obs = self.db.get(Observation, obs_id)
        if obs is not None and obs.project_id != self.project_id:
            raise ValueError("Observation ID belongs to another project")
        if obs is None:
            obs = Observation(id=obs_id, project_id=self.project_id, trace_id=trace_id)
            self.db.add(obs)
        obs.parent_observation_id = parent
        obs.type = obs_type
        obs.name = data.get("name") or obs_id
        obs.start_time = data.get("start_time") or datetime.now(timezone.utc)
        obs.end_time = data.get("end_time")
        obs.input = data.get("input")
        obs.output = data.get("output")
        obs.usage = data.get("usage")
        obs.model = data.get("model")
        obs.model_parameters = data.get("model_parameters")
        obs.metadata_field = data.get("metadata")
        obs.level = data.get("level", "DEFAULT")
        obs.status_message = data.get("status_message")
        obs.environment = data.get("environment")
        if "cost" in data:
            obs.cost = data["cost"]
        if "cost_currency" in data:
            obs.cost_currency = data["cost_currency"]
        if "cost_source" in data:
            obs.cost_source = data["cost_source"]
        if obs.cost_source is None and obs.model and obs.usage:
            usage = obs.usage if isinstance(obs.usage, dict) else {}
            input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
            output_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or usage.get("candidates_token_count") or 0
            if input_tokens or output_tokens:
                estimated = estimate_cost(self.db, obs.model, int(input_tokens), int(output_tokens))
                if estimated:
                    obs.cost = estimated["cost"]
                    obs.cost_currency = estimated["cost_currency"]
                    obs.cost_source = estimated["cost_source"]
        self.db.flush()
        self._aggregate_trace_cost(trace_id)

    def _aggregate_trace_cost(self, trace_id: str) -> None:
        """Keep a trace total only when every included amount shares one currency."""
        trace = self.db.get(Trace, trace_id)
        if not trace:
            return
        observations = self.db.query(Observation).filter(
            Observation.project_id == self.project_id,
            Observation.trace_id == trace_id,
            Observation.cost.is_not(None),
            Observation.cost_currency.is_not(None),
        ).all()
        totals: Dict[str, float] = {}
        sources: set[str] = set()
        for observation in observations:
            currency = observation.cost_currency.upper()
            totals[currency] = totals.get(currency, 0.0) + observation.cost
            if observation.cost_source:
                sources.add(observation.cost_source)
        if len(totals) != 1:
            trace.total_cost = None
            trace.total_cost_currency = None
            trace.total_cost_source = None
            return
        currency, amount = next(iter(totals.items()))
        trace.total_cost = amount
        trace.total_cost_currency = currency
        trace.total_cost_source = next(iter(sources)) if len(sources) == 1 else ("aggregated" if sources else None)

    def _auto_evaluate_traces(self, traced_ids: set[str]) -> None:
        """Auto-create scores for completed traces that have input and output."""
        import uuid
        for tid in traced_ids:
            trace = self.db.get(Trace, tid)
            if not trace or not trace.input or not trace.output:
                continue
            name = trace.name or "auto_eval"
            existing = self.db.query(Score).filter_by(
                trace_id= tid, name=f"{name}_completion"
            ).first()
            if existing:
                continue
            score = Score(
                id=uuid.uuid4().hex,
                project_id=self.project_id,
                trace_id=tid,
                name=f"{name}_completion",
                value=1.0,
                source="AUTO_EVAL",
                comment="Auto-evaluated: trace completed with input and output",
            )
            self.db.add(score)

    def _ensure_trace_row(self, trace_id: str) -> None:
        trace = self.db.get(Trace, trace_id)
        if trace is not None and trace.project_id != self.project_id:
            raise ValueError("Trace ID belongs to another project")
        if trace is None:
            self.db.add(Trace(id=trace_id, project_id=self.project_id, name=trace_id))
            self.db.flush()

    def _upsert_root_trace(self, trace_id: str, data: Dict[str, Any]) -> None:
        trace = self.db.get(Trace, trace_id)
        if trace is not None and trace.project_id != self.project_id:
            raise ValueError("Trace ID belongs to another project")
        if trace is None:
            trace = Trace(id=trace_id, project_id=self.project_id, name=data.get("name") or trace_id)
            self.db.add(trace)
        start = data.get("start_time")
        end = data.get("end_time")
        if start and (trace.start_time is None or start < trace.start_time):
            trace.start_time = start
        if end and (trace.end_time is None or end > trace.end_time):
            trace.end_time = end
        if trace.start_time and trace.end_time:
            trace.latency_ms = (_as_utc(trace.end_time) - _as_utc(trace.start_time)).total_seconds() * 1000
        for attr in ("name", "session_id", "user_id", "environment", "version", "release"):
            val = data.get(attr)
            if val:
                setattr(trace, attr, val)
        if data.get("input") is not None:
            trace.input = data.get("input")
        if data.get("output") is not None:
            trace.output = data.get("output")
        if data.get("tags"):
            trace.tags = list(data["tags"]) if isinstance(data["tags"], list) else data["tags"]
        if data.get("metadata"):
            trace.metadata_field = data.get("metadata")
            self._apply_mesh_identity(trace, data["metadata"])
        self.db.flush()

    def _apply_mesh_identity(self, trace: Trace, metadata: Dict[str, Any]) -> None:
        mesh = metadata.get("mesh") if isinstance(metadata, dict) else None
        if not isinstance(mesh, dict):
            return
        environment = self.db.get(Environment, mesh.get("environment_id"))
        registration = self.db.get(EnvironmentRegistration, mesh.get("registration_id"))
        definition = self.db.get(MeshDefinition, registration.definition_id) if registration else None
        if not (environment and registration and definition and environment.project_id == self.project_id and registration.project_id == self.project_id and registration.environment_id == environment.id and registration.enabled and definition.project_id == self.project_id and definition.key == mesh.get("definition_key") and definition.version == mesh.get("definition_version")):
            trace.attribution_status = "invalid"
            return
        trace.environment_id = environment.id
        trace.registration_id = registration.id
        trace.definition_id = definition.id
        trace.definition_version = definition.version
        trace.environment = environment.slug
        trace.attribution_status = "verified"
