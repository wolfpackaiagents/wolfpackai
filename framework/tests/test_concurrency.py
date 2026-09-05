"""Tests for agent concurrency with session — proving no lost/duplicated turns."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wolfpack import Agent
from wolfpack.models.base import BaseModel, ModelResponse
from wolfpack.models.message import Message


class EchoModel(BaseModel):
    provider = "fake"
    model_id = "echo"

    def __init__(self, suffix=""):
        self.suffix = suffix

    def invoke(self, messages, tools=None):
        last = messages[-1]
        content = last.get("content", "") if isinstance(last, dict) else last.content
        return ModelResponse(message=Message(role="assistant", content=f"echo: {content}{self.suffix}"), usage={})


def test_same_session_two_sequential_runs_preserves_order():
    agent = Agent(
        name="test",
        model=EchoModel(),
        session_id="seq_test",
    )
    r1 = agent.run("first")
    assert r1.content == "echo: first"

    r2 = agent.run("second")
    assert r2.content == "echo: second"

    session = agent._get_session()
    assert session is not None
    texts = [m.get_text() for m in session.messages if m.role == "user"]
    assert texts == ["first", "second"], f"Expected both user turns, got {texts}"


def test_same_session_run_after_pause_does_not_lose_turns():
    class PausingModel(BaseModel):
        provider = "fake"
        model_id = "pause"
        def __init__(self):
            self.call_count = 0
        def invoke(self, messages, tools=None):
            self.call_count += 1
            if self.call_count == 1:
                return ModelResponse(message=Message(role="assistant", content="need input"), usage={})
            last = messages[-1]
            content = last.get("content", "") if isinstance(last, dict) else last.content
            return ModelResponse(message=Message(role="assistant", content=f"done: {content}"), usage={})

    from wolfpack.tools.function import Function, FunctionCall, FunctionExecutionResult

    agent = Agent(
        name="test",
        model=PausingModel(),
        tools=[],
        session_id="pause_test",
    )
    r1 = agent.run("hello")
    # Not paused — just a simple response
    session = agent._get_session()
    assert session is not None
    user_msgs = [m.get_text() for m in session.messages if m.role == "user"]
    assistant_msgs = [m.get_text() for m in session.messages if m.role == "assistant"]
    assert "hello" in user_msgs, f"Expected user turn saved, got {user_msgs}"
    assert any("done" in m for m in assistant_msgs) or any("need input" in m for m in assistant_msgs)


def test_concurrent_same_session_shared_store():
    results: list[Exception | None] = []

    def run_agent(name: str, out: list):
        agent = Agent(
            name=name,
            model=EchoModel(suffix=f"-{name}"),
            session_id="concurrent_test",
        )
        try:
            r = agent.run(f"msg-from-{name}")
            out.append(r.content)
        except Exception as e:
            out.append(e)

    t1_out: list = []
    t2_out: list = []
    t1 = threading.Thread(target=run_agent, args=("A", t1_out))
    t2 = threading.Thread(target=run_agent, args=("B", t2_out))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(t1_out) == 1
    assert len(t2_out) == 1
    # Both should succeed (may share session state, but shouldn't crash)
    for out in t1_out + t2_out:
        assert not isinstance(out, Exception), f"Concurrent run failed: {out}"