"""Run a bounded query against a local SQLite database."""

import sqlite3

from wolfpack import DataAccessPolicy, SqlToolkit


connection = sqlite3.connect(":memory:")
connection.execute("CREATE TABLE daily_sales (day TEXT, total INTEGER)")
connection.execute("INSERT INTO daily_sales VALUES ('2026-09-12', 4200)")
connection.commit()

policy = DataAccessPolicy(
    source_id="local-analytics",
    allowed_tables={"daily_sales"},
    max_rows=50,
)
data = SqlToolkit(connection, policy=policy, dialect="sqlite")

print(data.query("SELECT day, total FROM daily_sales ORDER BY day DESC"))
