"""Combine a governed live SQL tool with an explicitly ingested RAG snapshot."""

import os

import psycopg

from wolfpack import Agent, DataAccessPolicy, SqlToolkit, get_model_from_env, ingest_rows
from wolfpack.knowledge.knowledge import Knowledge
from wolfpack.vectordb.base import MemoryVectorDb
from wolfpack.vectordb.embeddings import OllamaEmbeddingModel, OpenAIEmbeddingModel


def embedding_model():
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAIEmbeddingModel(model="text-embedding-3-small", api_key=os.environ["OPENAI_API_KEY"])
    return OllamaEmbeddingModel(model="embeddinggemma:latest")


def main() -> None:
    policy = DataAccessPolicy(
        source_id="production-customers",
        allowed_tables={"customers"},
        allowed_columns={"customers": {"id", "name", "email"}},
        sensitive_columns={"email"},
        max_rows=100,
    )
    knowledge = Knowledge(vector_db=MemoryVectorDb(), embedding_model=embedding_model())

    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        customer_data = SqlToolkit(connection, policy=policy, dialect="postgres")
        snapshot = customer_data.query("SELECT id, name, email FROM customers ORDER BY id")
        ingest_rows(knowledge, snapshot["rows"], source_id=policy.source_id)

        agent = Agent(
            name="customer-researcher",
            model=get_model_from_env(),
            tools=[customer_data],
            knowledge=knowledge,
            tool_allowlist=["list_tables", "describe_table", "query", "search_knowledge"],
        )
        result = agent.run("Use the knowledge base to summarize the approved snapshot. Query live SQL only if needed.")

    print(f"Knowledge documents: {knowledge.count()}")
    print(result.content)
    print("Tools used:", [call["name"] for call in result.tool_calls])


if __name__ == "__main__":
    main()
