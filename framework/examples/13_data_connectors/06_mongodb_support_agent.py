"""Use MongoDB support tickets as a bounded Agent tool."""

import os

from pymongo import MongoClient

from wolfpack import Agent, DataAccessPolicy, DocumentToolkit, get_model_from_env


collection = MongoClient(os.environ["MONGODB_URL"]).support.tickets
tickets = DocumentToolkit(
    collection="tickets",
    policy=DataAccessPolicy(source_id="support-tickets", allowed_collections={"tickets"}, max_rows=20),
    find=lambda name, filter, limit: list(collection.find(filter, {"_id": 0, "customer_email": 0}).limit(limit)),
)
agent = Agent(
    name="support-triage",
    model=get_model_from_env(),
    tools=[tickets],
    tool_allowlist=["find_documents"],
)
print(agent.run("List the open payment incidents reported in the last day without exposing customer email addresses.").content)
