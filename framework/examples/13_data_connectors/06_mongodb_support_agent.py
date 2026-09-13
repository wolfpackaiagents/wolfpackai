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
source_documents = tickets.find_documents({"status": "open", "category": "payment"})
print("APPROVED COLLECTION DATA:", source_documents["documents"])
agent = Agent(
    name="support-triage",
    model=get_model_from_env(),
    system="For payment incidents, call find_documents with exactly {'status': 'open', 'category': 'payment'} before answering.",
    tools=[tickets],
    tool_allowlist=["find_documents"],
)
result = agent.run("List the open payment incidents in the approved collection without exposing customer email addresses.")
print("AGENT RESULT:", result.content)
print("Tools used:", [call["name"] for call in result.tool_calls])
