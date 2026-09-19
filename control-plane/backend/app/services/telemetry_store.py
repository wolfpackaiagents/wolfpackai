"""Optional ClickHouse replica for query-heavy trace telemetry.

PostgreSQL remains authoritative for control-plane and ingestion transactions.
ClickHouse receives only post-commit telemetry snapshots, so it cannot make a
successful PostgreSQL ingestion fail.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Iterable

import clickhouse_connect

from ..core.config import get_settings
from ..models.entities import Observation, Trace


TRACE_COLUMNS = [
    "id", "project_id", "name", "timestamp", "created_at", "start_time", "end_time",
    "session_id", "environment", "environment_id", "registration_id", "input", "output",
    "metadata", "latency_ms", "total_cost", "total_cost_currency", "total_cost_source",
    "error", "event_version",
]
OBSERVATION_COLUMNS = [
    "id", "project_id", "trace_id", "parent_observation_id", "type", "name", "start_time",
    "end_time", "level", "status_message", "model", "input", "output", "usage", "cost",
    "cost_currency", "cost_source", "metadata", "environment", "event_version",
]


def _utc(value: datetime | None) -> datetime:
    value = value or datetime.now(timezone.utc)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":")) if value is not None else ""


class ClickHouseTelemetryStore:
    """Native ClickHouse schema and snapshot operations for telemetry only."""

    def __init__(self, client: Any):
        self.client = client

    def bootstrap(self) -> None:
        self.client.command("""
            CREATE TABLE IF NOT EXISTS telemetry_traces (
                id String, project_id String, name String, timestamp DateTime64(3, 'UTC'),
                created_at DateTime64(3, 'UTC'), start_time Nullable(DateTime64(3, 'UTC')),
                end_time Nullable(DateTime64(3, 'UTC')), session_id Nullable(String),
                environment Nullable(String), environment_id Nullable(String), registration_id Nullable(String),
                input String, output String, metadata String, latency_ms Nullable(Float64),
                total_cost Nullable(Float64), total_cost_currency Nullable(String),
                total_cost_source Nullable(String), error Nullable(String), event_version DateTime64(3, 'UTC')
            ) ENGINE = ReplacingMergeTree(event_version) ORDER BY (project_id, id)
        """)
        self.client.command("""
            CREATE TABLE IF NOT EXISTS telemetry_observations (
                id String, project_id String, trace_id String, parent_observation_id Nullable(String),
                type String, name String, start_time DateTime64(3, 'UTC'), end_time Nullable(DateTime64(3, 'UTC')),
                level String, status_message Nullable(String), model Nullable(String), input String, output String,
                usage String, cost Nullable(Float64), cost_currency Nullable(String), cost_source Nullable(String),
                metadata String, environment Nullable(String), event_version DateTime64(3, 'UTC')
            ) ENGINE = ReplacingMergeTree(event_version) ORDER BY (project_id, trace_id, id)
        """)

    def mirror(self, traces: Iterable[Trace], observations: Iterable[Observation]) -> None:
        version = datetime.now(timezone.utc)
        trace_rows = [[
            trace.id, trace.project_id, trace.name or "", _utc(trace.timestamp), _utc(trace.created_at),
            trace.start_time, trace.end_time, trace.session_id, trace.environment, trace.environment_id,
            trace.registration_id, _json(trace.input), _json(trace.output), _json(trace.metadata_field),
            trace.latency_ms, trace.total_cost, trace.total_cost_currency, trace.total_cost_source, trace.error, version,
        ] for trace in traces]
        observation_rows = [[
            observation.id, observation.project_id, observation.trace_id, observation.parent_observation_id,
            observation.type or "SPAN", observation.name or observation.id, _utc(observation.start_time), observation.end_time,
            observation.level or "DEFAULT", observation.status_message, observation.model, _json(observation.input),
            _json(observation.output), _json(observation.usage), observation.cost, observation.cost_currency,
            observation.cost_source, _json(observation.metadata_field), observation.environment, version,
        ] for observation in observations]
        if trace_rows:
            self.client.insert("telemetry_traces", trace_rows, column_names=TRACE_COLUMNS)
        if observation_rows:
            self.client.insert("telemetry_observations", observation_rows, column_names=OBSERVATION_COLUMNS)

    def rows(self, query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        result = self.client.query(query, parameters=parameters)
        if hasattr(result, "named_results"):
            return list(result.named_results())
        return [dict(zip(result.column_names, row)) for row in result.result_rows]


@lru_cache
def get_clickhouse_telemetry_store() -> ClickHouseTelemetryStore:
    settings = get_settings()
    client = clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_username,
        password=settings.clickhouse_password,
        database=settings.clickhouse_database,
        secure=settings.clickhouse_secure,
        connect_timeout=settings.clickhouse_connect_timeout,
    )
    return ClickHouseTelemetryStore(client)
