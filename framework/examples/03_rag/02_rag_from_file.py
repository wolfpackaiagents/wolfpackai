"""02_rag_from_file.py - Load a markdown file into the KB and answer from it.

This example shows the file-based side of RAG. It writes a small temporary
markdown file at runtime (a few `##` sections), loads it with
`kb.add_from_path(md_path)`, searches it directly, and then has an Agent answer a
question using the automatically generated `search_knowledge` tool. The retrieved
context is printed so you can see exactly what the answer was grounded on.

The embedding provider is picked from the environment (OpenAI when available,
otherwise Ollama). The chat model comes from `get_model_from_env()`.
"""

import os
import sys
import tempfile
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
    print("02_RAG_FROM_FILE - RAG from a markdown file")
    print("=" * 60)

    # 1) Create a small temporary markdown file with several ## sections.
    markdown = """# Acme Corp Product Manual

## About the company

Acme Corp is a fictional logistics company founded in 1987 in Lisbon.
It specializes in same-day parcel delivery across Southern Europe.

## Pricing

Acme's standard delivery costs 4.50 euros per parcel. Priority delivery
costs 9.90 euros and guarantees arrival before noon the next business day.

## Contact

Clients reach the Acme support team by emailing support@acme.example or
calling +351 555 0100 between 9:00 and 18:00 on weekdays.
"""
    tmp = tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8")
    tmp.write(markdown)
    tmp.close()
    md_path = tmp.name
    print(f"\nWrote temporary markdown: {md_path}")

    # 2) Load the file into the knowledge base (markdown is split by ## sections).
    kb = Knowledge(vector_db=MemoryVectorDb(), embedding_model=build_embedding_model())
    kb.add_from_path(md_path)
    print(f"Documents stored    : {kb.count()}")

    # 3) Search the file-backed KB directly.
    query = "How much does priority delivery cost?"
    print(f"\n--- kb.search() for: {query!r} ---")
    retrieved = kb.search(query, limit=3)
    for r in retrieved:
        print(f"  [score={r.score:.4f}] meta={r.document.metadata} :: {r.document.content[:70]}...")

    # 4) Have an agent answer using the RAG tool built from the file KB.
    try:
        model = get_model_from_env()
    except Exception:
        raise SystemExit(
            "No API key found (OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, "
            "or OLLAMA_BASE_URL). Set one and re-run."
        )
    agent = Agent(
        name="Manual Support Agent",
        model=model,
        role="A support agent grounded in the product manual",
        goal="Answer customer questions strictly from the product manual stored in the knowledge base.",
        backstory="You only know the content of the provided manual. Quote it when answering.",
        tools=[create_knowledge_search_tool(kb)],
    )

    question = "What is the price of priority delivery and when does it arrive?"
    print(f"\n--- Agent answering ---")
    print(f"Question: {question}")
    result = agent.run(question)

    print("\n----- FINAL ANSWER -----")
    if result.failed:
        print(f"Run failed: {result.error}")
    else:
        print(result.content)

    print("\n----- RETRIEVED CONTEXT (evidence) -----")
    for r in kb.search(query, limit=3):
        print(f"  [score={r.score:.4f}] {r.document.content[:90]}...")

    # Clean up the temporary file.
    Path(md_path).unlink(missing_ok=True)
    print(f"\nRemoved temporary file: {md_path}")
    print("Done.")


if __name__ == "__main__":
    main()