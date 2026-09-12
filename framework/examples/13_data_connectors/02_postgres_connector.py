"""Connect a PostgreSQL data source with a server-side access policy."""

import os

import psycopg

from wolfpack import DataAccessPolicy, SqlToolkit


database_url = os.environ["DATABASE_URL"]
policy = DataAccessPolicy(
    source_id="production-customers",
    allowed_tables={"customers"},
    sensitive_columns={"email", "phone"},
    max_rows=100,
)

with psycopg.connect(database_url) as connection:
    customers = SqlToolkit(connection, policy=policy, dialect="postgres")
    print(customers.query("SELECT id, name, email FROM customers ORDER BY id"))
