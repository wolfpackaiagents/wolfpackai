"""Query API: list traces, detail, and aggregated metrics.

Results are served from Postgres. Metric: per-time-bucket count with p50/p95 latency
(percentiles computed in SQL with window functions)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException

from ..core.auth import AuthContext, require_role
from ..core.database import get_db
from ..models.entities import Observation, Score, Trace
from ..schemas.contract import TraceListResponse, TracePublic, MetricPoint

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
