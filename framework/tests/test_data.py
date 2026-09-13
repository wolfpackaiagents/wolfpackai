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


def test_native_redis_neo4j_and_elasticsearch_toolkits_apply_governed_reads():
    from wolfpack.data import ElasticsearchToolkit, Neo4jToolkit, RedisToolkit

    class RedisClient:
        def get(self, key):
            return b"12"

    class Neo4jDriver:
        def session(self):
            class Session:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    pass

                def run(self, query, parameters):
                    return [{"supplier": "Atlas Parts"}]

            return Session()

    class ElasticsearchClient:
        def search(self, *, index, query, size):
            return {"hits": {"hits": [{"_source": {"ticket_id": "PAY-1042", "customer_email": "ana@example.com"}}]}}

    inventory = RedisToolkit(RedisClient(), policy=DataAccessPolicy(source_id="inventory", allowed_key_prefixes={"inventory:"}))
    suppliers = Neo4jToolkit(Neo4jDriver(), policy=DataAccessPolicy(source_id="suppliers", allowed_graph_labels={"Supplier"}))
    tickets = ElasticsearchToolkit(
        ElasticsearchClient(),
        index="support-tickets",
        policy=DataAccessPolicy(source_id="tickets", allowed_collections={"support-tickets"}, sensitive_columns={"customer_email"}),
    )

    assert inventory.get("inventory:sku-42")["value"] == "12"
    assert suppliers.read_cypher("MATCH (s:Supplier) RETURN s.name AS supplier")["rows"] == [{"supplier": "Atlas Parts"}]
    assert tickets.find_documents({"status": "open"})["documents"] == [{"ticket_id": "PAY-1042", "customer_email": "[REDACTED]"}]


def test_warehouse_toolkits_share_the_governed_sql_contract():
    from wolfpack.data import AthenaToolkit, BigQueryToolkit, ClickHouseToolkit, DatabricksToolkit, SnowflakeToolkit, TrinoToolkit

    policy = DataAccessPolicy(source_id="warehouse", allowed_tables={"customers"})
    for toolkit_type in (TrinoToolkit, AthenaToolkit, BigQueryToolkit, ClickHouseToolkit, SnowflakeToolkit, DatabricksToolkit):
        toolkit = toolkit_type(_database(), policy=policy)
        assert toolkit.estimate_cost("SELECT id FROM customers")["engine"]
        with pytest.raises(DataPolicyError):
            toolkit.query("UPDATE customers SET name = 'Grace'")


def test_clickhouse_toolkit_accepts_clickhouse_connect_clients():
    from wolfpack.data import ClickHouseToolkit

    class QueryResult:
        column_names = ("id", "email")
        result_rows = ((1, "ada@example.com"),)

    class ClickHouseClient:
        def query(self, statement, parameters=None):
            assert statement == "SELECT id, email FROM customers"
            assert parameters is None
            return QueryResult()

    toolkit = ClickHouseToolkit(
        ClickHouseClient(),
        policy=DataAccessPolicy(source_id="warehouse", allowed_tables={"customers"}, sensitive_columns={"email"}),
    )

    assert toolkit.query("SELECT id, email FROM customers")["rows"] == [{"id": 1, "email": "[REDACTED]"}]


def test_agent_keeps_live_sql_tools_separate_from_knowledge_search():
    from wolfpack import Agent

    class SnapshotKnowledge:
        def search(self, query: str, limit: int = 5):
            return []

    agent = Agent(name="customer-researcher", model=object(), tools=[_toolkit()], knowledge=SnapshotKnowledge())

    assert {"list_tables", "describe_table", "query", "search_knowledge"} <= set(agent._tool_map)
