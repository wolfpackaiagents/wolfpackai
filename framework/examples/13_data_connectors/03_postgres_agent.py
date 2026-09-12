"""Give a real Agent bounded, read-only access to PostgreSQL."""

import os

import psycopg

from wolfpack import Agent, DataAccessPolicy, SqlToolkit, get_model_from_env


def main() -> None:
    policy = DataAccessPolicy(
        source_id="production-customers",
        allowed_tables={"customers"},
        allowed_columns={"customers": {"id", "name", "email"}},
        sensitive_columns={"email"},
        max_rows=100,
    )

    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        customer_data = SqlToolkit(connection, policy=policy, dialect="postgres")
        agent = Agent(
            name="customer-analyst",
            model=get_model_from_env(),
            role="Customer data analyst",
            goal="Answer only from the approved customer source.",
            tools=[customer_data],
            tool_allowlist=["list_tables", "describe_table", "query"],
        )
        result = agent.run("How many customers are in the approved source? Do not request email addresses.")

    print(result.content)
    print("Tools used:", [call["name"] for call in result.tool_calls])


if __name__ == "__main__":
    main()
