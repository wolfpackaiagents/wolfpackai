"""Give a collections Agent bounded, read-only access to PostgreSQL debt data."""

import os

import psycopg

from wolfpack import Agent, DataAccessPolicy, SqlToolkit, get_model_from_env


def main() -> None:
    policy = DataAccessPolicy(
        source_id="corporate-debts",
        allowed_tables={"company_debts"},
        allowed_columns={"company_debts": {"company_name", "outstanding_amount", "due_date", "status", "tax_id"}},
        sensitive_columns={"tax_id"},
        max_rows=100,
    )

    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        debt_data = SqlToolkit(connection, policy=policy, dialect="postgres")
        source_rows = debt_data.query(
            "SELECT company_name, outstanding_amount, due_date, status FROM company_debts "
            "WHERE status = 'overdue' ORDER BY outstanding_amount DESC"
        )
        print("APPROVED TABLE DATA:", source_rows["rows"])
        agent = Agent(
            name="collections-analyst",
            model=get_model_from_env(),
            role="Corporate collections analyst",
            goal="Prioritize overdue corporate debt using only the approved source.",
            tools=[debt_data],
            tool_allowlist=["list_tables", "describe_table", "query"],
        )
        result = agent.run("Which three companies have the largest overdue balances? Do not request tax IDs.")

    print("AGENT RESULT:", result.content)
    print("Tools used:", [call["name"] for call in result.tool_calls])


if __name__ == "__main__":
    main()
