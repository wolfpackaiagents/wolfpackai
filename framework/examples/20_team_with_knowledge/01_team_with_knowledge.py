"""Team with specialized Agents using real tools and knowledge base.

Each member is a full Agent with its own role, description, tools,
and knowledge. The leader decides which specialist to delegate to.

Run:
    uv run python examples/20_team_with_knowledge/01_team_with_knowledge.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wolfpack import Agent, Team, get_model_from_env, tool
from wolfpack.knowledge.knowledge import Knowledge
from wolfpack.knowledge.readers import MarkdownReader
from wolfpack.vectordb.base import MemoryVectorDb
from wolfpack.vectordb.embeddings import EmbeddingModel


class SimpleEmbedding(EmbeddingModel):
    def embed(self, texts: list[str]) -> list[list[float]]:
        result = []
        for text in texts:
            freq = [0.0] * 128
            for ch in text.lower():
                if ord(ch) < 128:
                    freq[ord(ch)] += 1.0
            n = len(text) or 1
            result.append([f / n for f in freq])
        return result


@tool
def classify_ticket(message: str) -> str:
    """Classifies a support ticket into a category.
    Args:
        message: the support request text
    Returns:
        category: 'password', 'billing', 'api', 'account', or 'general'
    """
    msg = message.lower()
    if any(w in msg for w in ["senha", "password", "reset", "log in", "login"]):
        return "password"
    if any(w in msg for w in ["billing", "fatura", "pagamento", "refund", "reembolso"]):
        return "billing"
    if any(w in msg for w in ["api", "token", "key", "rate limit"]):
        return "api"
    if any(w in msg for w in ["conta", "account", "locked", "bloqueado", "unlock"]):
        return "account"
    return "general"


def main() -> None:
    knowledge_path = Path(__file__).parent / "support_knowledge.md"
    reader = MarkdownReader(chunk_size=500)
    chunks = reader.read_file(str(knowledge_path))

    vector_db = MemoryVectorDb()
    embedding_model = SimpleEmbedding()
    knowledge = Knowledge(vector_db=vector_db, embedding_model=embedding_model)
    for chunk in chunks:
        knowledge.add_text(chunk.content, metadata={"source": "support_knowledge", "heading": chunk.metadata.get("heading")})

    print(f"Knowledge base loaded: {knowledge.count()} chunks")

    try:
        model = get_model_from_env()
    except Exception:
        raise SystemExit(
            "No API key found (OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, "
            "or OLLAMA_BASE_URL). Set one and re-run."
        )
    print(f"Using model: {model.provider}/{model.model_id}")

    triage = Agent(
        name="support-triage",
        model=model,
        role="Classify and prioritize support tickets",
        goal="Determine the correct category and priority for each support request.",
        backstory="A wolfpack agent specialised in triaging support tickets into categories like password, billing, or API.",
        description="Specialist in ticket classification. Determines the category of a support request.",
        tools=[classify_ticket],
    )

    knowledge_agent = Agent(
        name="knowledge-specialist",
        model=model,
        role="Search support knowledge base for solutions",
        goal="Retrieve relevant documentation and known solutions from the knowledge base.",
        backstory="A wolfpack agent that searches the knowledge base to ground answers in documented solutions.",
        description="Specialist in retrieving documentation and known solutions from the knowledge base.",
        knowledge=knowledge,
    )

    team = Team("support-orchestrator", [triage, knowledge_agent], leader_model=model)

    print("\nRunning team with message: 'Não consigo redefinir minha senha'")
    result = team.run("Não consigo redefinir minha senha no sistema")
    print(f"\n=== Result ===\n{result.content}\n")


if __name__ == "__main__":
    main()