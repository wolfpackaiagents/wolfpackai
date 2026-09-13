"""Use ClickHouse aggregates as a read-only Agent tool."""

import os

import clickhouse_connect

from wolfpack import Agent, ClickHouseToolkit, DataAccessPolicy, get_model_from_env


client = clickhouse_connect.get_client(
    host=os.environ["CLICKHOUSE_HOST"],
    username=os.environ["CLICKHOUSE_USER"],
    password=os.environ["CLICKHOUSE_PASSWORD"],
    database=os.environ["CLICKHOUSE_DATABASE"],
)
revenue = ClickHouseToolkit(
    client,
    policy=DataAccessPolicy(source_id="daily-revenue", allowed_tables={"daily_revenue"}, max_rows=31),
)
agent = Agent(
    name="revenue-analyst",
    model=get_model_from_env(),
    tools=[revenue],
    tool_allowlist=["list_tables", "describe_table", "query", "estimate_cost"],
)
print(agent.run("Which sales region had the highest revenue in the last 30 days?").content)
