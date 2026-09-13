"""Use Elasticsearch support documents as a bounded Agent tool."""

import os

from elasticsearch import Elasticsearch

from wolfpack import Agent, DataAccessPolicy, ElasticsearchToolkit, get_model_from_env


tickets = ElasticsearchToolkit(
    Elasticsearch(os.environ["ELASTICSEARCH_URL"]),
    index="support-tickets",
    policy=DataAccessPolicy(
        source_id="support-tickets",
        allowed_collections={"support-tickets"},
        sensitive_columns={"customer_email"},
        max_rows=20,
    ),
)
print("APPROVED INDEX DATA:", tickets.find_documents({"status": "open"}))
agent = Agent(
    name="support-triage",
    model=get_model_from_env(),
    system="For open incidents, call find_documents with exactly {'status': 'open'} before answering.",
    tools=[tickets],
    tool_allowlist=["find_documents"],
)
result = agent.run("List the open support incidents without exposing customer email addresses.")
print("AGENT RESULT:", result.content)
print("Tools used:", [call["name"] for call in result.tool_calls])
