"""Use MySQL to give an Agent read-only access to a film catalog."""

import os

import pymysql

from wolfpack import Agent, DataAccessPolicy, SqlToolkit, get_model_from_env


connection = pymysql.connect(
    host=os.environ["MYSQL_HOST"],
    user=os.environ["MYSQL_USER"],
    password=os.environ["MYSQL_PASSWORD"],
    database=os.environ["MYSQL_DATABASE"],
)
movies = SqlToolkit(
    connection,
    policy=DataAccessPolicy(source_id="film-catalog", allowed_tables={"movies"}, max_rows=20),
    dialect="mysql",
)
agent = Agent(
    name="film-programmer",
    model=get_model_from_env(),
    tools=[movies],
    tool_allowlist=["list_tables", "describe_table", "query"],
)
print(agent.run("Recommend three action movies rated above 8.0 from the approved catalog.").content)
