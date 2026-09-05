"""Tests for team with specialist Agents and knowledge base."""

from pathlib import Path

from wolfpack.agent.agent import Agent
from wolfpack.knowledge.knowledge import Knowledge
from wolfpack.knowledge.readers import MarkdownReader
from wolfpack.team import Team, TeamResult
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


class FakeModel:
    provider = "test"
    model_id = "test-model"

    def invoke(self, messages, tools=None):
        from wolfpack.models.base import ModelResponse
        from wolfpack.models.message import Message
        return ModelResponse(message=Message(role="assistant", content="processed"))

    def stream(self, messages, tools=None):
        from wolfpack.models.base import ModelStreamChunk, ModelResponse
        from wolfpack.models.message import Message
        yield ModelStreamChunk(response=ModelResponse(message=Message(role="assistant", content="processed")))


def _fake_tool_fn(search_query: str) -> str:
    return f"found: {search_query}"


def test_markdown_reader_reads_file():
    path = Path(__file__).parent.parent / "examples" / "20_team_with_knowledge" / "support_knowledge.md"
    reader = MarkdownReader(chunk_size=500)
    chunks = reader.read_file(str(path))
    assert len(chunks) > 0
    assert any("Password Reset" in c.content for c in chunks)


def test_markdown_reader_reads_string():
    reader = MarkdownReader()
    chunks = reader.read_string("# Title\n\n## Section 1\nContent here\n\n## Section 2\nMore content")
    assert len(chunks) >= 2
    headings = [c.metadata.get("heading") for c in chunks if c.metadata.get("heading")]
    assert "Section 1" in headings


def test_knowledge_accepts_markdown_chunks():
    vdb = MemoryVectorDb()
    emb = SimpleEmbedding()
    knowledge = Knowledge(vector_db=vdb, embedding_model=emb)

    reader = MarkdownReader(chunk_size=500)
    chunks = reader.read_string("## Password Reset\nReset instructions here.\n## Billing\nBilling info here.")
    for chunk in chunks:
        knowledge.add_text(chunk.content, metadata={"source": "test", "heading": chunk.metadata.get("heading")})

    assert knowledge.count() >= 2
    results = knowledge.search("password", limit=2)
    assert len(results) > 0


def test_team_with_member_agents():
    from wolfpack.tools.function import Function

    fn = Function(name="test_tool", description="A test tool", entrypoint=_fake_tool_fn)
    member = Agent(name="test-agent", role="Test specialist", description="A test agent", tools=[fn], model=FakeModel())
    team = Team("test-team", [member], leader_model=FakeModel())
    result = team.run("test message")
    assert isinstance(result, TeamResult)
    assert isinstance(result.content, str)


def test_team_member_descriptions_include_tools():
    from wolfpack.tools.function import Function

    fn = Function(name="test_tool", description="A test tool", entrypoint=_fake_tool_fn)
    member = Agent(name="test-agent", role="Test specialist", description="A test agent", tools=[fn], model=FakeModel())
    team = Team("test-team", [member], leader_model=FakeModel())
    desc = team._build_member_descriptions()
    assert "test-agent" in desc
    assert "test_tool" in desc


def test_team_delegates_to_member_agent():
    from wolfpack.tools.function import Function

    fn = Function(name="test_tool", description="A test tool", entrypoint=_fake_tool_fn)
    member = Agent(name="test-agent", role="Test specialist", description="A test agent", tools=[fn], model=FakeModel())
    team = Team("test-team", [member], leader_model=FakeModel())
    result = team._delegate("test-agent", "search for something")
    assert "processed" in result


def test_team_returns_error_for_unknown_member():
    team = Team("test-team", [], leader_model=FakeModel())
    try:
        team.run("test")
        assert False, "should have raised"
    except ValueError as e:
        assert "needs at least one member" in str(e)