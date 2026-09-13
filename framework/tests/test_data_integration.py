"""Integration tests for governed SQL access against real database engines."""

import os
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

import pytest

from wolfpack.data import ClickHouseToolkit, DataAccessPolicy, DataPolicyError, DocumentToolkit, SqlToolkit


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


@pytest.mark.integration
def test_mysql_database_enforces_data_policy():
    mysql_url = os.environ.get("WOLFPACK_TEST_MYSQL_URL")
    if not mysql_url:
        pytest.skip("WOLFPACK_TEST_MYSQL_URL is not configured")

    pymysql = pytest.importorskip("pymysql")
    parsed_url = urlparse(mysql_url)
    connection = pymysql.connect(
        host=parsed_url.hostname,
        port=parsed_url.port or 3306,
        user=parsed_url.username,
        password=parsed_url.password,
        database=parsed_url.path.lstrip("/"),
        autocommit=True,
    )
    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS customers")
        cursor.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name VARCHAR(255), email VARCHAR(255))")
        cursor.execute("INSERT INTO customers (id, name, email) VALUES (1, 'Ada', 'ada@example.com')")

    toolkit = SqlToolkit(connection, policy=_policy(), dialect="mysql")
    assert toolkit.query("SELECT id, name, email FROM customers")["rows"] == [
        {"id": 1, "name": "Ada", "email": "[REDACTED]"}
    ]
    with pytest.raises(DataPolicyError):
        toolkit.query("DELETE FROM customers")
    connection.close()


@pytest.mark.integration
def test_mongodb_collection_enforces_data_policy():
    mongodb_url = os.environ.get("WOLFPACK_TEST_MONGODB_URL")
    if not mongodb_url:
        pytest.skip("WOLFPACK_TEST_MONGODB_URL is not configured")

    pymongo = pytest.importorskip("pymongo")
    client = pymongo.MongoClient(mongodb_url)
    collection = client.wolfpack_data_test.customers
    collection.drop()
    collection.insert_one({"id": 1, "name": "Ada", "email": "ada@example.com"})
    toolkit = DocumentToolkit(
        collection="customers",
        policy=DataAccessPolicy(source_id="customers", allowed_collections={"customers"}, max_rows=10),
        find=lambda name, filter, limit: list(collection.find(filter, {"_id": 0}).limit(limit)),
    )

    assert toolkit.find_documents({"name": "Ada"})["documents"] == [{"id": 1, "name": "Ada", "email": "ada@example.com"}]
    client.close()


@pytest.mark.integration
def test_clickhouse_database_enforces_data_policy():
    clickhouse_host = os.environ.get("WOLFPACK_TEST_CLICKHOUSE_HOST")
    if not clickhouse_host:
        pytest.skip("WOLFPACK_TEST_CLICKHOUSE_HOST is not configured")

    clickhouse_connect = pytest.importorskip("clickhouse_connect")
    client = clickhouse_connect.get_client(
        host=clickhouse_host,
        port=int(os.environ.get("WOLFPACK_TEST_CLICKHOUSE_PORT", "8123")),
        username=os.environ.get("WOLFPACK_TEST_CLICKHOUSE_USER", "default"),
        password=os.environ.get("WOLFPACK_TEST_CLICKHOUSE_PASSWORD", ""),
    )
    client.command("DROP TABLE IF EXISTS customers")
    client.command("CREATE TABLE customers (id UInt64, name String, email String) ENGINE = Memory")
    client.command("INSERT INTO customers VALUES (1, 'Ada', 'ada@example.com')")
    toolkit = ClickHouseToolkit(client, policy=_policy())

    assert toolkit.list_tables()["tables"] == ["customers"]
    assert [column["name"] for column in toolkit.describe_table("customers")["columns"]] == ["id", "name", "email"]
    assert toolkit.query("SELECT id, name, email FROM customers")["rows"] == [
        {"id": 1, "name": "Ada", "email": "[REDACTED]"}
    ]
    with pytest.raises(DataPolicyError):
        toolkit.query("DELETE FROM customers")
    client.close()
