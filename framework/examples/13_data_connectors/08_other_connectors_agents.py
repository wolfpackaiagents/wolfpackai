"""Agent factories for connectors that require external infrastructure to verify."""

from wolfpack import (
    Agent,
    AthenaToolkit,
    BigQueryToolkit,
    DataAccessPolicy,
    DatabricksToolkit,
    DocumentToolkit,
    GraphToolkit,
    KeyValueToolkit,
    SnowflakeToolkit,
    TrinoToolkit,
    get_model_from_env,
)


def supply_chain_agent(neo4j_driver):
    """Trace delayed shipments through Neo4j supplier relationships."""
    graph = GraphToolkit(
        policy=DataAccessPolicy(source_id="supply-chain", allowed_graph_labels={"Supplier", "Shipment"}, max_rows=25),
        labels=lambda: ["Supplier", "Shipment"],
        read=lambda query, parameters, limit: [dict(record) for record in neo4j_driver.session().run(query, parameters or {})][:limit],
    )
    return Agent("supply-chain-analyst", get_model_from_env(), tools=[graph], tool_allowlist=["list_labels", "read_cypher"])


def inventory_agent(redis_client):
    """Look up warehouse inventory by an approved Redis key prefix."""
    inventory = KeyValueToolkit(
        policy=DataAccessPolicy(source_id="warehouse-inventory", allowed_key_prefixes={"inventory:"}),
        get_value=redis_client.get,
    )
    return Agent("inventory-assistant", get_model_from_env(), tools=[inventory], tool_allowlist=["get"])


def account_agent(dynamodb_table):
    """Retrieve bounded account records from DynamoDB."""
    accounts = DocumentToolkit(
        collection="accounts",
        policy=DataAccessPolicy(source_id="customer-accounts", allowed_collections={"accounts"}, max_rows=20),
        find=lambda name, filter, limit: dynamodb_table.scan(Limit=limit, FilterExpression=filter).get("Items", []),
    )
    return Agent("account-analyst", get_model_from_env(), tools=[accounts], tool_allowlist=["find_documents"])


def field_service_agent(firestore_collection):
    """Retrieve open field-service work orders from Firestore."""
    work_orders = DocumentToolkit(
        collection="work_orders",
        policy=DataAccessPolicy(source_id="field-service", allowed_collections={"work_orders"}, max_rows=20),
        find=lambda name, filter, limit: [snapshot.to_dict() for snapshot in firestore_collection.limit(limit).stream()],
    )
    return Agent("field-service-dispatcher", get_model_from_env(), tools=[work_orders], tool_allowlist=["find_documents"])


def warehouse_agents(trino_connection, athena_connection, bigquery_connection, snowflake_connection, databricks_connection):
    """Create agents for delivery, advertising, invoicing, retail, and fraud analysis."""
    sources = [
        ("delivery-lake", TrinoToolkit(trino_connection, policy=DataAccessPolicy(source_id="delivery-lake", allowed_tables={"shipment_events"}))),
        ("ad-performance", AthenaToolkit(athena_connection, policy=DataAccessPolicy(source_id="ad-performance", allowed_tables={"campaign_events"}))),
        ("invoices", BigQueryToolkit(bigquery_connection, policy=DataAccessPolicy(source_id="invoices", allowed_tables={"invoice_fact"}))),
        ("retail-sales", SnowflakeToolkit(snowflake_connection, policy=DataAccessPolicy(source_id="retail-sales", allowed_tables={"daily_store_sales"}))),
        ("fraud-signals", DatabricksToolkit(databricks_connection, policy=DataAccessPolicy(source_id="fraud-signals", allowed_tables={"transactions"}))),
    ]
    return [Agent(f"{name}-analyst", get_model_from_env(), tools=[toolkit], tool_allowlist=["query", "estimate_cost"]) for name, toolkit in sources]
