"""Read-only SQL tools with bounded, server-side policy enforcement."""

from __future__ import annotations

import re
from typing import Any

from ..tools.toolkit import Toolkit
from .policy import DataAccessPolicy, DataPolicyError


_WRITE_KEYWORDS = re.compile(
    r"\b(ALTER|ANALYZE|ATTACH|CREATE|DELETE|DETACH|DROP|GRANT|INSERT|MERGE|PRAGMA|REINDEX|REPLACE|REVOKE|TRUNCATE|UPDATE|VACUUM)\b",
    re.IGNORECASE,
)
_TABLE_REFERENCE = re.compile(r"\b(?:FROM|JOIN)\s+([\w.\"`\[\]]+)", re.IGNORECASE)


class SqlToolkit(Toolkit):
    """Expose bounded read-only SQL operations over a DB-API connection.

    Production connections must still use a read-only database identity or replica.
    The policy is a second boundary, not a substitute for database permissions.
    """

    def __init__(self, connection: Any, *, policy: DataAccessPolicy, dialect: str = "sqlite") -> None:
        super().__init__("sql")
        self.connection = connection
        self.policy = policy
        self.dialect = dialect
        self.register(self.list_tables, description="List the SQL tables permitted for this data source.")
        self.register(self.describe_table, description="Describe columns for one permitted SQL table.")
        self.register(self.query, description="Run one bounded read-only SQL query against permitted tables.")

    def list_tables(self) -> dict[str, Any]:
        if self.dialect == "sqlite":
            rows = self._execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name").fetchall()
            names = [row[0] for row in rows if not str(row[0]).startswith("sqlite_")]
        else:
            rows = self._execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_type = 'BASE TABLE' ORDER BY table_name"
            ).fetchall()
            names = [row[0] for row in rows]
        if self.policy.allowed_tables:
            allowed = {name.lower() for name in self.policy.allowed_tables}
            names = [name for name in names if str(name).lower() in allowed]
        return {"source_id": self.policy.source_id, "tables": names}

    def describe_table(self, table: str) -> dict[str, Any]:
        self.policy.require_table(table)
        if self.dialect == "sqlite":
            self._validate_identifier(table)
            rows = self._execute(f"PRAGMA table_info({table})").fetchall()
            columns = [{"name": row[1], "type": row[2], "nullable": not bool(row[3])} for row in rows]
        else:
            rows = self._execute(
                "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                "WHERE table_name = %s ORDER BY ordinal_position",
                (table,),
            ).fetchall()
            columns = [{"name": row[0], "type": row[1], "nullable": row[2] == "YES"} for row in rows]
        return {"source_id": self.policy.source_id, "table": table, "columns": columns}

    def query(self, sql: str, parameters: dict[str, Any] | list[Any] | None = None) -> dict[str, Any]:
        statement = self._validate_read_query(sql)
        cursor = self._execute(statement, parameters)
        columns = [column[0] for column in cursor.description or []]
        self._enforce_columns(columns)
        fetched = cursor.fetchmany(self.policy.max_rows + 1)
        truncated = len(fetched) > self.policy.max_rows
        rows = [self._redact(dict(zip(columns, row))) for row in fetched[: self.policy.max_rows]]
        return {
            "source_id": self.policy.source_id,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
        }

    def explain(self, sql: str, parameters: dict[str, Any] | list[Any] | None = None) -> dict[str, Any]:
        statement = self._validate_read_query(sql)
        cursor = self._execute(f"EXPLAIN {statement}", parameters)
        columns = [column[0] for column in cursor.description or []]
        return {"source_id": self.policy.source_id, "plan": [dict(zip(columns, row)) for row in cursor.fetchmany(self.policy.max_rows)]}

    def _validate_read_query(self, sql: str) -> str:
        statement = sql.strip()
        if not statement:
            raise DataPolicyError("SQL query cannot be empty.")
        if ";" in statement.rstrip(";"):
            raise DataPolicyError("Only one statement is allowed.")
        statement = statement.rstrip(";").strip()
        if "--" in statement or "/*" in statement:
            raise DataPolicyError("SQL comments are not allowed.")
        if not re.match(r"^(SELECT|WITH|EXPLAIN)\b", statement, re.IGNORECASE):
            raise DataPolicyError("Only read-only SELECT, WITH, and EXPLAIN statements are allowed.")
        if _WRITE_KEYWORDS.search(statement):
            raise DataPolicyError("Only read-only SQL is allowed.")
        for raw_table in _TABLE_REFERENCE.findall(statement):
            self.policy.require_table(raw_table.strip('"`[]').split(".")[-1])
        return statement

    def _execute(self, statement: str, parameters: Any = None) -> Any:
        cursor = self.connection.cursor()
        if parameters is None:
            cursor.execute(statement)
        else:
            cursor.execute(statement, parameters)
        return cursor

    @staticmethod
    def _validate_identifier(identifier: str) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
            raise DataPolicyError("Invalid table identifier.")

    def _redact(self, row: dict[str, Any]) -> dict[str, Any]:
        sensitive = {column.lower() for column in self.policy.sensitive_columns}
        return {key: "[REDACTED]" if key.lower() in sensitive else value for key, value in row.items()}

    def _enforce_columns(self, columns: list[str]) -> None:
        if not self.policy.allowed_columns:
            return
        allowed = {column.lower() for values in self.policy.allowed_columns.values() for column in values}
        for column in columns:
            if column.lower() not in allowed:
                raise DataPolicyError(f"Column '{column}' is not allowed for source '{self.policy.source_id}'.")


class AnalyticsToolkit(SqlToolkit):
    """SQL toolkit for Trino, Athena, BigQuery, ClickHouse, Snowflake, and Databricks.

    A driver-specific DB-API connection is supplied by the application. The same
    read-only policy limits result size and source scope across warehouse engines.
    """

    def __init__(self, connection: Any, *, engine: str, policy: DataAccessPolicy) -> None:
        super().__init__(connection, policy=policy, dialect=engine)
        self.name = engine
        self.engine = engine
        self.register(self.estimate_cost, description="Return configured query budget metadata before a warehouse query.")

    def estimate_cost(self, sql: str) -> dict[str, Any]:
        self._validate_read_query(sql)
        return {
            "source_id": self.policy.source_id,
            "engine": self.engine,
            "max_bytes_scanned": self.policy.max_bytes_scanned,
            "cost_budget_per_query": self.policy.cost_budget_per_query,
            "requires_explain": self.policy.require_explain,
        }


class TrinoToolkit(AnalyticsToolkit):
    def __init__(self, connection: Any, *, policy: DataAccessPolicy) -> None:
        super().__init__(connection, engine="trino", policy=policy)


class AthenaToolkit(AnalyticsToolkit):
    def __init__(self, connection: Any, *, policy: DataAccessPolicy) -> None:
        super().__init__(connection, engine="athena", policy=policy)


class BigQueryToolkit(AnalyticsToolkit):
    def __init__(self, connection: Any, *, policy: DataAccessPolicy) -> None:
        super().__init__(connection, engine="bigquery", policy=policy)


class ClickHouseToolkit(AnalyticsToolkit):
    def __init__(self, connection: Any, *, policy: DataAccessPolicy) -> None:
        super().__init__(connection, engine="clickhouse", policy=policy)


class SnowflakeToolkit(AnalyticsToolkit):
    def __init__(self, connection: Any, *, policy: DataAccessPolicy) -> None:
        super().__init__(connection, engine="snowflake", policy=policy)


class DatabricksToolkit(AnalyticsToolkit):
    def __init__(self, connection: Any, *, policy: DataAccessPolicy) -> None:
        super().__init__(connection, engine="databricks", policy=policy)
