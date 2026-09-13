"""Query approved corporate debt records from PostgreSQL."""

import os

import psycopg

from wolfpack import DataAccessPolicy, SqlToolkit


database_url = os.environ["DATABASE_URL"]
policy = DataAccessPolicy(
    source_id="corporate-debts",
    allowed_tables={"company_debts"},
    sensitive_columns={"tax_id", "contact_email"},
    max_rows=100,
)

with psycopg.connect(database_url) as connection:
    debts = SqlToolkit(connection, policy=policy, dialect="postgres")
    print(debts.query("SELECT company_name, outstanding_amount, due_date FROM company_debts WHERE status = 'overdue' ORDER BY outstanding_amount DESC"))
