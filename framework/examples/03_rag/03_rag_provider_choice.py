"""03_rag_provider_choice.py - Swap embedding providers against the same content.

This example shows how to swap embedding providers for the same knowledge base:
the exact same content and query are embedded (and searched) with OpenAI embeddings
and with Ollama embeddings, and the resulting scores are printed side by side.

The selection is robust and environment-driven:
  - If OPENAI_API_KEY is set   -> OpenAI  (text-embedding-3-small, 1536 dims).
  - Otherwise                   -> Ollama  (embeddinggemma:latest, 768 dims).

Both KBs share the same documents, so you can compare how each provider ranks them
against the same query. No chat model is needed here, only embeddings + search.
"""

import os
import sys
from pathlib import Path

# Make wolfpack importable when this script lives inside the `examples/` folder.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wolfpack.knowledge.knowledge import Knowledge
from wolfpack.vectordb.base import MemoryVectorDb
from wolfpack.vectordb.embeddings import OllamaEmbeddingModel, OpenAIEmbeddingModel


def build_default():
    """Return the embedding model chosen from the environment.

    OpenAI wins when a key exists; otherwise we fall back to Ollama.
    """
    if os.environ.get("OPENAI_API_KEY"):
        print("Provider pick : OpenAI (OPENAI_API_KEY set)")
        return OpenAIEmbeddingModel(model="text-embedding-3-small", api_key=os.environ["OPENAI_API_KEY"])
    print("Provider pick : Ollama (no OPENAI_API_KEY, using OLLAMA_BASE_URL)")
    return OllamaEmbeddingModel(model="embeddinggemma:latest")


def main() -> None:
    print("=" * 60)
    print("03_RAG_PROVIDER_CHOICE - Swap embedding providers")
    print("=" * 60)

    # 1) Decide the default provider from the environment.
    build_default()

    # 2) The same document set and query for both providers.
    content = (
        "The wolfpack framework is a Python library for building AI agents. "
        "MemoryVectorDb is an in-memory vector store with no external dependencies, "
        "ideal for demos and tests. Every wolfpack agent run emits OpenTelemetry spans "
        "using the gen_ai semantic convention."
    )
    query = "Which wolfpack component is an in-memory vector store?"

    print("\n--- Embedding the same content with each provider ---")
    try:
        openai_kb = Knowledge(
            vector_db=MemoryVectorDb(),
            embedding_model=OpenAIEmbeddingModel(model="text-embedding-3-small", api_key=os.environ.get("OPENAI_API_KEY")),
        )
        openai_kb.add_text(content, chunk=False)
        print("  OpenAI embedded OK")
    except Exception as e:
        openai_kb = None
        print(f"  OpenAI failed to embed: {type(e).__name__}: {e}")

    try:
        ollama_kb = Knowledge(vector_db=MemoryVectorDb(), embedding_model=OllamaEmbeddingModel(model="embeddinggemma:latest"))
        ollama_kb.add_text(content, chunk=False)
        print("  Ollama  embedded OK")
    except Exception as e:
        ollama_kb = None
        print(f"  Ollama  failed to embed: {type(e).__name__}: {e}")

    # 3) Run the same query and print scores side by side.
    print(f"\n--- kb.search() for: {query!r} (side by side) ---")
    for label, kb in (("OpenAI", openai_kb), ("Ollama", ollama_kb)):
        if kb is None:
            print(f"  {label:7} : (unavailable)")
            continue
        res = kb.search(query, limit=1)
        if res:
            dims = len(kb.embedding_model.embed([query])[0])
            print(f"  {label:7} [dims={dims}] top score={res[0].score:.4f} :: {res[0].document.content[:80]}...")
        else:
            print(f"  {label:7} : no results")

    print("\nDone.")


if __name__ == "__main__":
    main()