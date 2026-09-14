"""Query API: list traces, detail, and aggregated metrics.

Results are served from the selected telemetry store. Metric: per-time-bucket
count with p50/p95 latency (computed in Python for consistent backend output)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException

from ..core.auth import AuthContext, require_role
from ..core.database import get_db
from ..core.config import get_settings
from ..models.entities import Observation, Score, Trace
from ..schemas.contract import TraceListResponse, TracePublic, MetricPoint
from ..services.telemetry_store import get_clickhouse_telemetry_store

router = APIRouter()


def _trace_to_public(t: Trace) -> TracePublic:
    return TracePublic(
        id=t.id,
        name=t.name,
        timestamp=_utc_isoformat(t.timestamp) if t.timestamp else "",
        start_time=_utc_isoformat(t.start_time) if t.start_time else None,
        end_time=_utc_isoformat(t.end_time) if t.end_time else None,
        session_id=t.session_id,
        environment=t.environment,
        input=t.input,
        output=t.output,
        latency_ms=t.latency_ms,
        cost=t.total_cost,
        cost_currency=t.total_cost_currency,
        cost_source=t.total_cost_source,
    )


def _clickhouse_enabled() -> bool:
    return get_settings().telemetry_storage_backend == "clickhouse"


def _decode_json(value: Any) -> Any:
    if not value:
        return None
    return json.loads(value) if isinstance(value, str) else value


def _clickhouse_trace_to_public(row: Dict[str, Any]) -> TracePublic:
    return TracePublic(
        id=row["id"], name=row["name"], timestamp=_utc_isoformat(row["timestamp"]),
        start_time=_utc_isoformat(row["start_time"]) if row["start_time"] else None,
        end_time=_utc_isoformat(row["end_time"]) if row["end_time"] else None,
        session_id=row["session_id"], environment=row["environment"], input=_decode_json(row["input"]),
        output=_decode_json(row["output"]), latency_ms=row["latency_ms"], cost=row["total_cost"],
        cost_currency=row["total_cost_currency"], cost_source=row["total_cost_source"],
    )


def _clickhouse_filters(project_id: str, **filters: Any) -> tuple[str, dict[str, Any]]:
    clauses = ["project_id = {project_id:String}"]
    parameters = {"project_id": project_id}
    columns = {
        "name": "name", "env": "environment", "session_id": "session_id",
        "environment_id": "environment_id", "registration_id": "registration_id",
        "from_": "timestamp >=", "to": "timestamp <=",
    }
    for key, value in filters.items():
        if value is not None:
            column = columns[key]
            operator = "" if column.endswith((">=", "<=")) else " ="
            clauses.append(
                f"{column}{operator} {{{key}:String}}"
                if key not in {"from_", "to"}
                else f"{column} {{{key}:DateTime64(3, 'UTC')}}"
            )
            parameters[key] = value
    return " AND ".join(clauses), parameters


def _utc_isoformat(value: datetime) -> str:
    """Serialize database datetimes as explicit UTC values across database drivers."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _metric_bucket(value: datetime, group_by: str) -> datetime:
    """Normalize a trace timestamp to the requested UTC metric bucket."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    if group_by == "month":
        return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if group_by == "day":
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    return value.replace(minute=0, second=0, microsecond=0)


def _percentile(values: List[float], percentile: float) -> Optional[float]:
    """Calculate PostgreSQL percentile_cont-compatible linear interpolation."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


@router.get("/traces", response_model=TraceListResponse)
def list_traces(
    auth: AuthContext = Depends(require_role("read_only")),
    name: Optional[str] = None,
    env: Optional[str] = None,
    session_id: Optional[str] = None,
    environment_id: Optional[str] = None,
    registration_id: Optional[str] = None,
    from_: Optional[datetime] = Query(default=None, alias="from"),
    to: Optional[datetime] = None,
    page: int = Query(default=0, ge=0, le=10_000),
    per_page: int = Query(default=20, ge=1, le=100),
):
    project_id, db = auth
    if _clickhouse_enabled():
        where, parameters = _clickhouse_filters(
            project_id, name=name, env=env, session_id=session_id,
            environment_id=environment_id, registration_id=registration_id, from_=from_, to=to,
        )
        store = get_clickhouse_telemetry_store()
        total = store.rows(f"SELECT count() AS total FROM telemetry_traces FINAL WHERE {where}", parameters)[0]["total"]
        parameters.update({"limit": per_page, "offset": page * per_page})
        rows = store.rows(
            f"SELECT * FROM telemetry_traces FINAL WHERE {where} "
            "ORDER BY timestamp DESC, id DESC LIMIT {limit:UInt64} OFFSET {offset:UInt64}",
            parameters,
        )
        return TraceListResponse(traces=[_clickhouse_trace_to_public(row) for row in rows], page=page, per_page=per_page, total=total)
    q = db.query(Trace).filter(Trace.project_id == project_id)
    if name:
        q = q.filter(Trace.name == name)
    if env:
        q = q.filter(Trace.environment == env)
    if session_id:
        q = q.filter(Trace.session_id == session_id)
    if environment_id:
        q = q.filter(Trace.environment_id == environment_id)
    if registration_id:
        q = q.filter(Trace.registration_id == registration_id)
    if from_:
        q = q.filter(Trace.timestamp >= from_)
    if to:
        q = q.filter(Trace.timestamp <= to)
    total = q.count()
    rows = q.order_by(Trace.timestamp.desc(), Trace.id.desc()).offset(page * per_page).limit(per_page).all()
    traces = [_trace_to_public(t) for t in rows]
    return TraceListResponse(traces=traces, page=page, per_page=per_page, total=total)


@router.get("/traces/{trace_id}", response_model=TracePublic)
def trace_detail(trace_id: str, auth: AuthContext = Depends(require_role("read_only"))):
    project_id, db = auth
    if _clickhouse_enabled():
        store = get_clickhouse_telemetry_store()
        parameters = {"project_id": project_id, "trace_id": trace_id}
        rows = store.rows(
            "SELECT * FROM telemetry_traces FINAL WHERE project_id = {project_id:String} "
            "AND id = {trace_id:String} LIMIT 1",
            parameters,
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Trace not found")
        public = _clickhouse_trace_to_public(rows[0])
        observations = store.rows(
            "SELECT * FROM telemetry_observations FINAL WHERE project_id = {project_id:String} "
            "AND trace_id = {trace_id:String} ORDER BY start_time",
            parameters,
        )
        public.observations = [_clickhouse_obs_to_dict(row) for row in observations]
        scores = db.query(Score).filter(Score.project_id == project_id, Score.trace_id == trace_id).all()
        public.scores = [_to_score_dict(score) for score in scores]
        return public
    t = db.query(Trace).filter(Trace.id == trace_id, Trace.project_id == project_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Trace not found")
    obs = (
        db.query(Observation)
        .filter(Observation.project_id == project_id, Observation.trace_id == trace_id)
        .order_by(Observation.start_time)
        .all()
    )
    scores = db.query(Score).filter(Score.project_id == project_id, Score.trace_id == trace_id).all()
    public = _trace_to_public(t)
    public.observations = [_to_obs_dict(o) for o in obs]
    public.scores = [_to_score_dict(s) for s in scores]
    return public


@router.get("/metrics", response_model=List[MetricPoint])
def metrics(
    auth: AuthContext = Depends(require_role("read_only")),
    group_by: str = "hour",
    dimension: Optional[str] = None,
    environment_id: Optional[str] = None,
    registration_id: Optional[str] = None,
    from_: Optional[datetime] = Query(default=None, alias="from"),
    to: Optional[datetime] = None,
):
    project_id, db = auth
    if _clickhouse_enabled():
        where, parameters = _clickhouse_filters(
            project_id, environment_id=environment_id, registration_id=registration_id, from_=from_, to=to,
        )
        store = get_clickhouse_telemetry_store()
        traces = store.rows(f"SELECT * FROM telemetry_traces FINAL WHERE {where}", parameters)
        observations = store.rows(
            "SELECT trace_id, cost_currency, cost FROM telemetry_observations FINAL "
            "WHERE project_id = {project_id:String} AND cost IS NOT NULL AND cost_currency IS NOT NULL",
            {"project_id": project_id},
        )
        return _clickhouse_metrics(traces, observations, group_by)
    buckets: Dict[datetime, List[Trace]] = {}
    query = db.query(Trace).filter(Trace.project_id == project_id)
    if environment_id:
        query = query.filter(Trace.environment_id == environment_id)
    if registration_id:
        query = query.filter(Trace.registration_id == registration_id)
    if from_:
        query = query.filter(Trace.timestamp >= from_)
    if to:
        query = query.filter(Trace.timestamp <= to)
    traces = query.all()
    observation_costs: Dict[str, list[tuple[str, float]]] = {}
    trace_ids = [trace.id for trace in traces]
    if trace_ids:
        for trace_id, currency, cost in db.query(
            Observation.trace_id, Observation.cost_currency, Observation.cost
        ).filter(
            Observation.project_id == project_id,
            Observation.trace_id.in_(trace_ids),
            Observation.cost.is_not(None),
            Observation.cost_currency.is_not(None),
        ):
            observation_costs.setdefault(trace_id, []).append((currency.upper(), cost))
    for trace in traces:
        bucket = _metric_bucket(trace.created_at, group_by)
        buckets.setdefault(bucket, []).append(trace)

    points = []
    for bucket, bucket_traces in sorted(buckets.items()):
        latencies = [trace.latency_ms for trace in bucket_traces if trace.latency_ms is not None]
        tokens = sum(
            int((trace.metadata_field or {}).get("input_tokens") or 0)
            + int((trace.metadata_field or {}).get("output_tokens") or 0)
            for trace in bucket_traces
        )
        cost_by_currency: Dict[str, float] = {}
        for trace in bucket_traces:
            costs = observation_costs.get(trace.id)
            if costs:
                for currency, cost in costs:
                    cost_by_currency[currency] = cost_by_currency.get(currency, 0.0) + cost
            elif trace.total_cost is not None and trace.total_cost_currency:
                currency = trace.total_cost_currency.upper()
                cost_by_currency[currency] = cost_by_currency.get(currency, 0.0) + trace.total_cost
        points.append(
            MetricPoint(
                bucket=_utc_isoformat(bucket),
                count=len(bucket_traces),
                latency_p50=_percentile(latencies, 0.50),
                latency_p95=_percentile(latencies, 0.95),
                total_tokens=tokens,
                total_cost=next(iter(cost_by_currency.values())) if len(cost_by_currency) == 1 else None,
                total_cost_by_currency=cost_by_currency,
                errors=sum(trace.error is not None for trace in bucket_traces),
            )
        )
    return points if dimension == "aggregate" else points


def _to_obs_dict(o: Observation) -> Dict[str, Any]:
    return {
        "id": o.id,
        "type": o.type,
        "name": o.name,
        "parent_observation_id": o.parent_observation_id,
        "start_time": o.start_time.isoformat() if o.start_time else None,
        "end_time": o.end_time.isoformat() if o.end_time else None,
        "model": o.model,
        "usage": o.usage,
        "input": o.input,
        "output": o.output,
        "level": o.level,
        "status_message": o.status_message,
        "cost": o.cost,
        "cost_currency": o.cost_currency,
        "cost_source": o.cost_source,
        "metadata": o.metadata_field,
    }


def _clickhouse_obs_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row["id"], "type": row["type"], "name": row["name"],
        "parent_observation_id": row["parent_observation_id"],
        "start_time": _utc_isoformat(row["start_time"]) if row["start_time"] else None,
        "end_time": _utc_isoformat(row["end_time"]) if row["end_time"] else None,
        "model": row["model"], "usage": _decode_json(row["usage"]), "input": _decode_json(row["input"]),
        "output": _decode_json(row["output"]), "level": row["level"], "status_message": row["status_message"],
        "cost": row["cost"], "cost_currency": row["cost_currency"], "cost_source": row["cost_source"],
        "metadata": _decode_json(row["metadata"]),
    }


def _clickhouse_metrics(traces: List[Dict[str, Any]], observations: List[Dict[str, Any]], group_by: str) -> List[MetricPoint]:
    buckets: Dict[datetime, List[Dict[str, Any]]] = {}
    trace_ids = {trace["id"] for trace in traces}
    observation_costs: Dict[str, List[tuple[str, float]]] = {}
    for observation in observations:
        if observation["trace_id"] in trace_ids:
            observation_costs.setdefault(observation["trace_id"], []).append(
                (observation["cost_currency"].upper(), observation["cost"])
            )
    for trace in traces:
        buckets.setdefault(_metric_bucket(trace["created_at"], group_by), []).append(trace)
    points = []
    for bucket, bucket_traces in sorted(buckets.items()):
        latencies = [trace["latency_ms"] for trace in bucket_traces if trace["latency_ms"] is not None]
        cost_by_currency: Dict[str, float] = {}
        for trace in bucket_traces:
            for currency, cost in observation_costs.get(trace["id"], []):
                cost_by_currency[currency] = cost_by_currency.get(currency, 0.0) + cost
        total_tokens = sum(
            int((_decode_json(trace["metadata"]) or {}).get("input_tokens") or 0)
            + int((_decode_json(trace["metadata"]) or {}).get("output_tokens") or 0)
            for trace in bucket_traces
        )
        points.append(MetricPoint(
            bucket=_utc_isoformat(bucket), count=len(bucket_traces),
            latency_p50=_percentile(latencies, .5), latency_p95=_percentile(latencies, .95),
            total_tokens=total_tokens,
            total_cost=next(iter(cost_by_currency.values())) if len(cost_by_currency) == 1 else None,
            total_cost_by_currency=cost_by_currency,
            errors=sum(trace["error"] is not None for trace in bucket_traces),
        ))
    return points


def _to_score_dict(s: Score) -> Dict[str, Any]:
    return {
        "id": s.id,
        "name": s.name,
        "data_type": s.data_type,
        "value": s.value,
        "string_value": s.string_value,
        "source": s.source,
        "comment": s.comment,
    }


def _metrics_to_public(t: Trace) -> TracePublic:
    return _trace_to_public(t)
