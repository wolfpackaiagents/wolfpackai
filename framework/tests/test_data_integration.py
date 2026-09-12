"""Integration tests for governed SQL access against real database engines."""

import os
import sqlite3
from pathlib import Path

import pytest

from wolfpack.data import DataAccessPolicy, DataPolicyError, SqlToolkit


def _policy() -> DataAccessPolicy:
    return DataAccessPolicy(
        source_id="integration-customers",
        allowed_tables={"customers"},
        sensitive_columns={"email"},
        max_rows=10,
    )


def test_sqlite_file_database_enforces_data_policy(tmp_path: Path):
    database = sqlite3.connect(tmp_path / "customers.db")
    database.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
    database.execute("INSERT INTO customers (name, email) VALUES ('Ada', 'ada@example.com')")
    database.commit()
    toolkit = SqlToolkit(database, policy=_policy())

    assert toolkit.list_tables()["tables"] == ["customers"]
    assert toolkit.query("SELECT id, name, email FROM customers")["rows"] == [
        {"id": 1, "name": "Ada", "email": "[REDACTED]"}
    ]
    with pytest.raises(DataPolicyError):
        toolkit.query("UPDATE customers SET name = 'Grace'")


@pytest.mark.integration
def test_postgres_database_enforces_data_policy():
    postgres_url = os.environ.get("WOLFPACK_TEST_POSTGRES_URL")
    if not postgres_url:
        pytest.skip("WOLFPACK_TEST_POSTGRES_URL is not configured")

    psycopg = pytest.importorskip("psycopg")
    with psycopg.connect(postgres_url, autocommit=True) as setup_connection:
        with setup_connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS customers")
            cursor.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
            cursor.execute("INSERT INTO customers (id, name, email) VALUES (1, 'Ada', 'ada@example.com')")

    with psycopg.connect(postgres_url, autocommit=True) as connection:
        toolkit = SqlToolkit(connection, policy=_policy(), dialect="postgres")

        assert toolkit.list_tables()["tables"] == ["customers"]
        assert toolkit.query("SELECT id, name, email FROM customers")["rows"] == [
            {"id": 1, "name": "Ada", "email": "[REDACTED]"}
        ]
        with pytest.raises(DataPolicyError):
            toolkit.query("DELETE FROM customers")
