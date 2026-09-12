import sqlite3

import pytest

from wolfpack.data import DataAccessPolicy, DataPolicyError, SqlToolkit


def _database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
    connection.execute("INSERT INTO customers (name, email) VALUES ('Ada', 'ada@example.com')")
    connection.commit()
    return connection


def _toolkit(**policy_overrides) -> SqlToolkit:
    max_rows = policy_overrides.pop("max_rows", 10)
    policy = DataAccessPolicy(
        source_id="customers",
        allowed_tables={"customers"},
        sensitive_columns={"email"},
        max_rows=max_rows,
        **policy_overrides,
    )
    return SqlToolkit(_database(), policy=policy)


def test_sql_toolkit_lists_and_describes_only_allowed_tables():
    toolkit = _toolkit()

    assert toolkit.list_tables()["tables"] == ["customers"]
    assert [column["name"] for column in toolkit.describe_table("customers")["columns"]] == ["id", "name", "email"]


def test_sql_toolkit_rejects_writes_and_multiple_statements():
    toolkit = _toolkit()

    with pytest.raises(DataPolicyError, match="read-only"):
        toolkit.query("DELETE FROM customers")

    with pytest.raises(DataPolicyError, match="one statement"):
        toolkit.query("SELECT id FROM customers; DELETE FROM customers")


def test_sql_toolkit_enforces_table_scope_and_redacts_sensitive_columns():
    toolkit = _toolkit()

    with pytest.raises(DataPolicyError, match="not allowed"):
        toolkit.query("SELECT * FROM sqlite_master")

    assert toolkit.query("SELECT id, name, email FROM customers")["rows"] == [{"id": 1, "name": "Ada", "email": "[REDACTED]"}]


def test_sql_toolkit_enforces_column_scope():
    toolkit = _toolkit(allowed_columns={"customers": {"id", "name"}})

    with pytest.raises(DataPolicyError, match="Column 'email' is not allowed"):
        toolkit.query("SELECT id, email FROM customers")


def test_sql_toolkit_applies_row_limit_when_query_has_no_limit():
    toolkit = _toolkit(max_rows=1)
    toolkit.connection.execute("INSERT INTO customers (name, email) VALUES ('Grace', 'grace@example.com')")
    toolkit.connection.commit()

    result = toolkit.query("SELECT id, name FROM customers ORDER BY id")

    assert result["row_count"] == 1
    assert result["truncated"] is True


def test_document_graph_and_key_value_toolkits_apply_source_scope():
    from wolfpack.data import DocumentToolkit, GraphToolkit, KeyValueToolkit

    documents = DocumentToolkit(
        collection="customers",
        policy=DataAccessPolicy(source_id="customers", allowed_collections={"customers"}),
        find=lambda collection, filter, limit: [{"id": 1, "name": "Ada"}],
    )
    graph = GraphToolkit(
        policy=DataAccessPolicy(source_id="graph", allowed_graph_labels={"Customer"}),
        labels=lambda: ["Customer"],
        read=lambda query, parameters, limit: [{"name": "Ada"}],
    )
    cache = KeyValueToolkit(
        policy=DataAccessPolicy(source_id="cache", allowed_key_prefixes={"customer:"}),
        get_value=lambda key: "Ada",
    )

    assert documents.find_documents({"name": "Ada"})["documents"] == [{"id": 1, "name": "Ada"}]
    assert graph.read_cypher("MATCH (c:Customer) RETURN c.name")["rows"] == [{"name": "Ada"}]
    assert cache.get("customer:1")["value"] == "Ada"

    with pytest.raises(DataPolicyError):
        cache.get("session:1")


def test_warehouse_toolkits_share_the_governed_sql_contract():
    from wolfpack.data import AthenaToolkit, BigQueryToolkit, ClickHouseToolkit, DatabricksToolkit, SnowflakeToolkit, TrinoToolkit

    policy = DataAccessPolicy(source_id="warehouse", allowed_tables={"customers"})
    for toolkit_type in (TrinoToolkit, AthenaToolkit, BigQueryToolkit, ClickHouseToolkit, SnowflakeToolkit, DatabricksToolkit):
        toolkit = toolkit_type(_database(), policy=policy)
        assert toolkit.estimate_cost("SELECT id FROM customers")["engine"]
        with pytest.raises(DataPolicyError):
            toolkit.query("UPDATE customers SET name = 'Grace'")
