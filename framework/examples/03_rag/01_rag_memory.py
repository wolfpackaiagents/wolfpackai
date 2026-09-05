"""01_rag_memory.py - In-memory RAG with real embeddings and an answering agent.

This example builds a knowledge base entirely in memory (no external files, no
infrastructure) from a list of facts. It then shows three things:

    1. Embedding the facts into an in-memory vector DB with real embeddings.
    2. Querying the KB directly with `kb.search()` and printing scores/metadata.
    3. Wrapping the same KB into a tool (`create_knowledge_search_tool`) on a real
       Agent, then asking a question that can ONLY be answered from the KB.

The embedding provider is picked from the environment: OpenAI when OPENAI_API_KEY
is set, otherwise Ollama (OLLAMA_BASE_URL). The chat model is chosen automatically
by `get_model_from_env()`.

Use real embeddings + a real chat model. No external store is required.
"""

import os
import sys
from pathlib import Path

# Make wolfpack importable when this script lives inside the `examples/` folder.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wolfpack import Agent, create_knowledge_search_tool, get_model_from_env
from wolfpack.knowledge.knowledge import Knowledge
from wolfpack.vectordb.base import MemoryVectorDb
from wolfpack.vectordb.embeddings import OpenAIEmbeddingModel, OllamaEmbeddingModel


def build_embedding_model():
    """Pick an embedding provider from the environment (OpenAI preferred)."""
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAIEmbeddingModel(model="text-embedding-3-small", api_key=os.environ["OPENAI_API_KEY"])
    return OllamaEmbeddingModel(model="embeddinggemma:latest")


def main() -> None:
    print("=" * 60)
    print("01_RAG_MEMORY - RAG from an in-memory fact list")
    print("=" * 60)

    # 1) Build the knowledge base from facts (no files on disk, no chunking).
    facts = [
        "The wolfpack framework is a Python library for building AI agents.",
        "Every wolfpack agent run emits OpenTelemetry spans using the gen_ai semantic convention.",
        "A wolfpack Knowledge combines a VectorDb with an EmbeddingModel to do retrieval.",
        "MemoryVectorDb is an in-memory vector store with no external dependencies, ideal for demos.",
        "The Agent tool-calling loop retries until the model replies without tool calls or max_iterations is reached.",
    ]
    embedding_model = build_embedding_model()
    kb = Knowledge(vector_db=MemoryVectorDb(), embedding_model=embedding_model)
    for i, fact in enumerate(facts):
        # chunk=False preserves each fact as a single retrievable document.
        kb.add_text(fact, metadata={"fact_id": i, "source": "inline"})
    print(f"\nEmbedding model     : {kb.embedding_model.__class__.__name__}")
    print(f"Knowledge documents : {kb.count()}")

    # 2) Inspect what is stored (metadata is kept per document).
    print("\n--- metadata on stored documents ---")
    stored = kb.vector_db._docs
    for d in stored:
        print(f"  id={d.id[:8]} meta={d.metadata} :: {d.content[:52]}...")

    # 3) Query directly with kb.search() and print similarity scores.
    query = "Which wolfpack component stores embedded documents so they can be retrieved later?"
    print(f"\n--- kb.search() for: {query!r} ---")
    results = kb.search(query, limit=3)
    for r in results:
        print(f"  [score={r.score:.4f}] meta={r.document.metadata} :: {r.document.content[:70]}...")

    # 4) Turn the KB into a tool and give it to a real Agent.
    try:
        model = get_model_from_env()
    except Exception:
        raise SystemExit(
            "No API key found (OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, "
            "or OLLAMA_BASE_URL). Set one and re-run."
        )
    agent = Agent(
        name="RAG Memory Assistant",
        model=model,
        role="A retrieval-augmented assistant",
        goal="Answer questions strictly from the facts stored in the knowledge base.",
        backstory="You only know what was stored in memory, never external knowledge.",
        tools=[create_knowledge_search_tool(kb)],
    )

    question = (
        "According to the knowledge base, what OpenTelemetry convention is emitted "
        "when a wolfpack agent runs? Give the exact term."
    )

    print(f"\n--- Agent answering (only retrievable via KB) ---")
    print(f"Question: {question}")
    result = agent.run(question)

    print("\n----- FINAL ANSWER -----")
    if result.failed:
        print(f"Run failed: {result.error}")
    else:
        print(result.content)

    print("\n----- TOOL CALLS (citations) -----")
    if result.tool_calls:
        for tc in result.tool_calls:
            print(f"  tool={tc['name']} args={tc['arguments']}")
    else:
        print("  (no tool call was recorded)")
    print("\n----- RETRIEVED CONTEXT FOR VERIFICATION -----")
    for r in kb.search(query, limit=3):
        print(f"  [score={r.score:.4f}] {r.document.content[:90]}...")

    print("\nDone.")


if __name__ == "__main__":
    main()