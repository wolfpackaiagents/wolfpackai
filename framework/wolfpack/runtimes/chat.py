"""Immutable, allowlisted Chat runtime factories.

The Mesh catalog is metadata, not executable code. This registry is deliberately
small and source-owned so a registration cannot execute arbitrary artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

from ..agent.agent import Agent
from ..team.team import Team, TeamMode
from ..tools.decorator import tool

CHAT_RUNTIME_KEYS = frozenset({("weather-operations", "1.0.0"), ("support-orchestrator", "1.0.0")})


@dataclass(frozen=True)
class ChatRuntimeEvent:
    type: str
    data: dict[str, Any]


class ChatRuntime:
    def __init__(self, key: str, model: Any):
        self.key = key
        self.model = model
        self.tool_names: set[str] = set()

    def stream(self, message: str) -> Iterator[ChatRuntimeEvent]:
        yield ChatRuntimeEvent("run", {"runtime": self.key})
        if self.key == "weather-operations":
            agent = Agent(name="weather-operations", model=self.model, tools=[])
            output = agent.run(message)
            yield ChatRuntimeEvent("final", {"content": output.content or ""})
            return

        @tool
        def search_support_knowledge(query: str) -> str:
            """Searches the fixed, read-only support knowledge source."""
            return "Knowledge article: Password resets are completed from the sign-in page."

        triage = Agent(name="support-triage", model=self.model, tools=[])
        knowledge = Agent(
            name="knowledge-specialist",
            model=self.model,
            tools=[search_support_knowledge],
            tool_allowlist=["search_support_knowledge"],
        )
        self.tool_names = {"search_support_knowledge"}
        triage_output = triage.run(message)
        yield ChatRuntimeEvent("team.member", {"member": "support-triage", "status": "completed"})
        yield ChatRuntimeEvent("team.member", {"member": "knowledge-specialist", "status": "started"})
        knowledge_output = knowledge.run(f"{message}\n\nTriage result: {triage_output.content or ''}")
        # The tool result is intentionally constrained to the fixed read-only source.
        if "search_support_knowledge" in str(knowledge_output.messages):
            yield ChatRuntimeEvent("tool", {"tool_name": "search_support_knowledge", "result": search_support_knowledge("password reset")})
        yield ChatRuntimeEvent("team.member", {"member": "knowledge-specialist", "status": "completed"})
        yield ChatRuntimeEvent("final", {"content": knowledge_output.content or ""})


def build_chat_runtime(key: str, version: str, model: Any) -> ChatRuntime | None:
    if (key, version) not in CHAT_RUNTIME_KEYS:
        return None
    return ChatRuntime(key, model)
