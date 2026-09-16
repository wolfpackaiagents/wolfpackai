"""Tests for Skill and SkillKnowledge."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
import tempfile

import pytest

from wolfpack.agent.skill import Skill, SkillKnowledge
from wolfpack.agent.agent import Agent
from wolfpack.models.base import BaseModel, ModelResponse
from wolfpack.models.message import Message, ToolCall
from wolfpack.observer.client import WolfpackObserver


class FakeModel:
    provider = "test"
    model_id = "test-model"

    def invoke(self, messages, tools=None):
        from wolfpack.models.message import Message
        return type(
            "Resp",
            (),
            {
                "message": Message(role="assistant", content="ok"),
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )()

    def stream(self, messages, tools=None):
        yield type("Chunk", (), {"content": "chunk", "response": None})()


class ActivationModel(BaseModel):
    provider = "test"
    model_id = "activation-model"

    def __init__(self):
        self.payloads = []

    def invoke(self, messages, tools=None):
        self.payloads.append(messages)
        if len(self.payloads) == 1:
            return ModelResponse(
                message=Message(
                    role="assistant",
                    tool_calls=[ToolCall(id="activate-1", name="activate_skill", arguments='{"name": "risco"}')],
                )
            )
        return ModelResponse(message=Message(role="assistant", content="Analise concluida."))


def test_skill_inline():
    s = Skill(name="analista", content="Voce e um analista financeiro.")
    assert s.name == "analista"
    assert s.content == "Voce e um analista financeiro."
    assert s.context is None


def test_skill_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# Skill de exemplo\nConteudo da skill.")
        path = f.name
    try:
        s = Skill(name="exemplo", path=path)
        assert s.content == "# Skill de exemplo\nConteudo da skill."
    finally:
        Path(path).unlink()


def test_skill_file_not_found():
    with pytest.raises(FileNotFoundError):
        Skill(name="x", path="/nonexistent/skill.md")


def test_skill_no_content_or_path():
    with pytest.raises(ValueError, match="Either content or path"):
        Skill(name="x")


def test_skill_empty_name():
    with pytest.raises(ValueError, match="non-empty"):
        Skill(name="", content="x")


def test_skill_with_context():
    s = Skill(name="risco", content="analise de risco", context="Use quando pedir analise de risco")
    assert s.context == "Use quando pedir analise de risco"


def test_skill_knowledge_requires_knowledge():
    with pytest.raises(ValueError, match="requires a Knowledge"):
        SkillKnowledge(name="x", knowledge=None, context="ctx")


def test_skill_knowledge_empty_context():
    with pytest.raises(ValueError, match="must be a non-empty string"):
        SkillKnowledge(name="x", knowledge=MagicMock(), context="")


def test_agent_system_prompt_with_always_skill():
    agent = Agent(
        name="test",
        model=FakeModel(),
        skills=[Skill(name="analista", content="Voce e um analista.")],
    )
    prompt = agent.system_prompt
    assert "Active Skills" in prompt
    assert "analista" in prompt
    assert "Voce e um analista." in prompt


def test_agent_system_prompt_context_skill_not_appended():
    agent = Agent(
        name="test",
        model=FakeModel(),
        skills=[Skill(name="risco", content="analise de risco", context="Use when risk analysis")],
    )
    prompt = agent.system_prompt
    assert "Available Skills" in prompt
    assert "risco" in prompt
    assert "analise de risco" not in prompt
    assert "activate_skill" in prompt


def test_agent_system_prompt_with_instructions_and_skills():
    agent = Agent(
        name="test",
        model=FakeModel(),
        instructions=["Be concise."],
        skills=[Skill(name="analista", content="Voce e um analista.")],
    )
    prompt = agent.system_prompt
    assert "Be concise." in prompt
    assert "Active Skills" in prompt


def test_agent_system_prompt_with_custom_system_and_skills():
    agent = Agent(
        name="test",
        model=FakeModel(),
        system="You are a helpful assistant.",
        skills=[Skill(name="analista", content="Voce e um analista.")],
    )
    prompt = agent.system_prompt
    assert "You are a helpful assistant." in prompt
    assert "Active Skills" in prompt


def test_agent_skill_knowledge_registers_tool():
    knowledge = MagicMock()
    knowledge.search.return_value = ["resultado 1"]
    agent = Agent(
        name="test",
        model=FakeModel(),
        skills=[SkillKnowledge(name="regulatorio", knowledge=knowledge, context="normas ANATEL")],
    )
    assert "search_knowledge_regulatorio" in agent._tool_map
    prompt = agent.system_prompt
    assert "search_knowledge_regulatorio" in prompt
    assert "Available Skills" in prompt
    assert "regulatorio" in prompt
    function = agent._tool_map["search_knowledge_regulatorio"]
    assert function.description == "normas ANATEL"


def test_contextual_skill_is_injected_after_activation():
    model = ActivationModel()
    agent = Agent(
        name="test",
        model=model,
        skills=[Skill(name="risco", content="Use matriz de risco.", context="Quando analisar risco")],
    )

    result = agent.run("Analise o risco do projeto.")

    assert result.content == "Analise concluida."
    assert result.tool_calls == [{"name": "activate_skill", "arguments": {"name": "risco"}}]
    assert model.payloads[1][-2]["role"] == "tool"
    assert model.payloads[1][-1] == {"role": "system", "content": "Activated skill [risco]:\nUse matriz de risco."}


def test_skills_are_trace_metadata():
    observer = WolfpackObserver("http://amp.test")
    Agent(
        name="test",
        model=FakeModel(),
        telemetry=observer,
        skills=[Skill(name="analista", content="Voce e um analista.")],
    ).run("hello")

    trace = next(event["body"] for event in observer._buffer if event["type"] == "observation-end" and event["body"]["type"] == "TRACE")
    assert trace["metadata"]["skills"] == ["analista"]


def test_agent_multiple_skills_mixed():
    agent = Agent(
        name="test",
        model=FakeModel(),
        skills=[
            Skill(name="sempre", content="Sempre ativa."),
            Skill(name="contextual", content="Contextual.", context="Quando for contextual"),
            SkillKnowledge(name="kbase", knowledge=MagicMock(), context="Use a base de conhecimento"),
        ],
    )
    prompt = agent.system_prompt
    assert "Active Skills" in prompt
    assert "Sempre ativa." in prompt
    assert "Available Skills" in prompt
    assert "contextual" in prompt
    assert "kbase" in prompt


def test_agent_empty_skills_no_error():
    agent = Agent(name="test", model=FakeModel(), skills=[])
    assert agent.system_prompt is not None
    assert "Skills" not in agent.system_prompt


def test_agent_skills_do_not_break_run():
    agent = Agent(
        name="test",
        model=FakeModel(),
        skills=[Skill(name="analista", content="Voce e um analista.")],
    )
    result = agent.run("hello")
    assert result.content is not None
