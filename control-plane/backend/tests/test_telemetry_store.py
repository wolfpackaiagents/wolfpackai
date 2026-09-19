from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.telemetry_store import ClickHouseTelemetryStore, OBSERVATION_COLUMNS, TRACE_COLUMNS


class FakeClickHouseClient:
    def __init__(self):
        self.commands = []
        self.inserts = []

    def command(self, query):
        self.commands.append(query)

    def insert(self, table, rows, column_names):
        self.inserts.append((table, rows, column_names))


def test_clickhouse_telemetry_store_bootstraps_native_tables_and_mirrors_snapshots():
    client = FakeClickHouseClient()
    store = ClickHouseTelemetryStore(client)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    trace = SimpleNamespace(
        id="trace-1", project_id="project-1", name="agent", timestamp=now, created_at=now,
        start_time=now, end_time=None, session_id="session-1", environment="production",
        environment_id=None, registration_id=None, input={"question": "hello"}, output=None,
        metadata_field={"input_tokens": 3}, latency_ms=12.5, total_cost=0.1,
        total_cost_currency="USD", total_cost_source="provider", error=None,
    )
    observation = SimpleNamespace(
        id="obs-1", project_id="project-1", trace_id="trace-1", parent_observation_id=None,
        type="GENERATION", name="model", start_time=now, end_time=None, level="DEFAULT",
        status_message=None, model="gpt-test", input={"prompt": "hello"}, output=None,
        usage={"input_tokens": 3}, cost=0.1, cost_currency="USD", cost_source="provider",
        metadata_field=None, environment="production",
    )

    store.bootstrap()
    store.mirror([trace], [observation])

    assert len(client.commands) == 2
    assert all("ReplacingMergeTree" in command for command in client.commands)
    assert [insert[0] for insert in client.inserts] == ["telemetry_traces", "telemetry_observations"]
    assert client.inserts[0][2] == TRACE_COLUMNS
    assert client.inserts[1][2] == OBSERVATION_COLUMNS
    assert client.inserts[0][1][0][11] == '{"question":"hello"}'
    assert client.inserts[1][1][0][13] == '{"input_tokens":3}'


def test_clickhouse_telemetry_store_does_not_insert_empty_batches():
    client = FakeClickHouseClient()

    ClickHouseTelemetryStore(client).mirror([], [])

    assert client.inserts == []


def test_clickhouse_telemetry_store_materializes_orm_defaults_before_insert():
    client = FakeClickHouseClient()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    trace = SimpleNamespace(
        id="trace-1", project_id="project-1", name=None, timestamp=now, created_at=now,
        start_time=None, end_time=None, session_id=None, environment=None, environment_id=None,
        registration_id=None, input=None, output=None, metadata_field=None, latency_ms=None,
        total_cost=None, total_cost_currency=None, total_cost_source=None, error=None,
    )
    observation = SimpleNamespace(
        id="obs-1", project_id="project-1", trace_id="trace-1", parent_observation_id=None,
        type=None, name=None, start_time=now, end_time=None, level=None, status_message=None,
        model=None, input=None, output=None, usage=None, cost=None, cost_currency=None,
        cost_source=None, metadata_field=None, environment=None,
    )

    ClickHouseTelemetryStore(client).mirror([trace], [observation])

    assert client.inserts[0][1][0][2] == ""
    assert client.inserts[1][1][0][4:6] == ["SPAN", "obs-1"]
    assert client.inserts[1][1][0][8] == "DEFAULT"
