"""Pydantic schemas for ingestion/query. Modeled on the langfuse contract
(HTTP 207 per event, observation types, trace fields).

Note: the Observer SDK sends `observation-start`/`observation-end` events with
generic fields; the backend combines them in pairs to build Traces and Observations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

ObservationType = Literal[
    "TRACE", "SPAN", "GENERATION", "TOOL", "EVENT", "RETRIEVER", "AGENT", "CHAIN", "EMBEDDING", "GUARDRAIL"
]


class EventBody(BaseModel):
    """Body of an ingestion event (server side). Tolerant: fields are not
    strict so that events the SDK emits with padding are not rejected."""

    type: str = "SPAN"
    name: Optional[str] = None
    trace_id: Optional[str] = None
    id: Optional[str] = None
    parent_observation_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    timestamp: Optional[str] = None
    input: Optional[Any] = None
    output: Optional[Any] = None
    usage: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    model_parameters: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: List[str] = Field(default_factory=list)
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    environment: Optional[str] = None
    level: Optional[str] = "DEFAULT"
    status_message: Optional[str] = None
    error: Optional[str] = None
    version: Optional[str] = None
    release: Optional[str] = None
    cost: Optional[float] = None
    cost_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    cost_source: Optional[str] = Field(default=None, min_length=1, max_length=64)


class IngestionEvent(BaseModel):
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex, description="UUID del evento (dedup key del cliente).")
    type: str = Field(default="observation-start")
    timestamp: Optional[str] = Field(default=None, description="ISO 8601 con ms.")
    body: EventBody = Field(default_factory=EventBody)


class IngestionRequest(BaseModel):
    events: List[IngestionEvent]


class IngestionResult(BaseModel):
    successes: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)


class IngestionAccepted(BaseModel):
    job_id: str
    status: Literal["accepted"] = "accepted"
    events_accepted: int


# ---------------- response schemas ----------------


class TracePublic(BaseModel):
    id: str
    name: str
    timestamp: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    session_id: Optional[str] = None
    environment: Optional[str] = None
    input: Optional[Any] = None
    output: Optional[Any] = None
    latency_ms: Optional[float] = None
    usage: Optional[Dict[str, Any]] = None
    cost: Optional[float] = None
    cost_currency: Optional[str] = None
    cost_source: Optional[str] = None
    observations: List[Dict[str, Any]] = Field(default_factory=list)
    scores: List[Dict[str, Any]] = Field(default_factory=list)


class TraceListResponse(BaseModel):
    traces: List[TracePublic]
    page: int = 0
    per_page: int = 20
    total: int = 0


class MetricQuery(BaseModel):
    group_by: str = "hour"
    dimension: Optional[str] = None


class MetricPoint(BaseModel):
    bucket: str
    count: int = 0
    latency_p50: Optional[float] = None
    latency_p95: Optional[float] = None
    total_tokens: Optional[int] = None
    total_cost: Optional[float] = None
    total_cost_by_currency: Dict[str, float] = Field(default_factory=dict)
    errors: int = 0
