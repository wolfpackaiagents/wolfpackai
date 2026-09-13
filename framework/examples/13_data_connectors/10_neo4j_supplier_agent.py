"""Use Neo4j supplier relationships as a bounded Agent tool."""

import os

from neo4j import GraphDatabase

from wolfpack import Agent, DataAccessPolicy, Neo4jToolkit, get_model_from_env


driver = GraphDatabase.driver(os.environ["NEO4J_URL"], auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]))
suppliers = Neo4jToolkit(
    driver,
    policy=DataAccessPolicy(source_id="supply-chain", allowed_graph_labels={"Supplier"}, max_rows=20),
)
print("APPROVED GRAPH DATA:", suppliers.read_cypher("MATCH (s:Supplier) RETURN s.name AS supplier"))
agent = Agent(
    name="supply-chain-analyst",
    model=get_model_from_env(),
    tools=[suppliers],
    tool_allowlist=["list_labels", "read_cypher"],
)
result = agent.run("Which suppliers are available in the approved supply-chain graph?")
print("AGENT RESULT:", result.content)
print("Tools used:", [call["name"] for call in result.tool_calls])
driver.close()
