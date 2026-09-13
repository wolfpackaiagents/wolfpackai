"""Search an approved action-movie catalog in a local SQLite database."""

import sqlite3

from wolfpack import DataAccessPolicy, SqlToolkit


connection = sqlite3.connect(":memory:")
connection.execute("CREATE TABLE movies (title TEXT, genre TEXT, release_year INTEGER, rating REAL)")
connection.execute("INSERT INTO movies VALUES ('Mad Max: Fury Road', 'Action', 2015, 8.1)")
connection.commit()

policy = DataAccessPolicy(
    source_id="film-catalog",
    allowed_tables={"movies"},
    max_rows=50,
)
data = SqlToolkit(connection, policy=policy, dialect="sqlite")

print(data.query("SELECT title, release_year, rating FROM movies WHERE genre = 'Action' ORDER BY rating DESC"))
