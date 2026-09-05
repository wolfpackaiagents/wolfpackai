"""Multi-agent orchestration with delegation via tool-based leader model.

The leader receives member descriptions (role, tools, knowledge) and decides
which specialist Agent to delegate to. Each member runs as a full Agent with
its own model, tools, and knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..agent.agent import Agent
from ..tools.decorator import tool


class TeamMode(str, Enum):
    coordinate = "coordinate"
    route = "route"
    broadcast = "broadcast"
    tasks = "tasks"


@dataclass
class TeamResult:
    content: str
    member_outputs: Dict[str, Any] = field(default_factory=dict)


class Team:
    """A leader-driven agent team. The leader delegates to member Agents
    via the `delegate_task_to_member()` tool. Each member runs as a full
    Agent with its own model, tools, and knowledge."""

    def __init__(
        self,
        name: str,
        members: list,
        leader_model=None,
        mode: TeamMode | str = TeamMode.coordinate,
        telemetry=None,
        max_delegations: int = 10,
    ):
        self.name = name
        self.members = {m.name: m for m in members}
        self.member_list = members
        self.leader_model = leader_model
        self.mode = TeamMode(mode)
        self.telemetry = telemetry
        self.max_delegations = max_delegations

    def _build_member_descriptions(self) -> str:
        lines = []
        for m in self.member_list:
            desc = getattr(m, "description", None) or getattr(m, "role", "") or "specialist"
            tool_names = list(getattr(m, "_tool_map", {}).keys())
            tool_str = f", tools: {', '.join(tool_names)}" if tool_names else ""
            lines.append(f"- {m.name}: {desc}{tool_str}")
        return "\n".join(lines)

    def _delegate(self, member_name: str, task: str, parent_trace=None) -> str:
        member = self.members.get(member_name)
        if not member:
            return f"Error: member '{member_name}' not found. Available: {list(self.members.keys())}"
        member.telemetry = self.telemetry
        if self.telemetry:
            span = self.telemetry.start_span("TOOL", f"delegate_{member_name}", parent=parent_trace)
            output = member.run(task)
            content = output.content or ""
            self.telemetry.end_span(span, input={"task": task}, output=content)
        else:
            output = member.run(task)
            content = output.content or ""
        self._record_interaction(self.name, member_name, "delegation", member, parent_trace)
        return content

    def _record_interaction(self, source: str, target: str, interaction_type: str, member=None, parent_trace=None) -> None:
        if not self.telemetry:
            return
        trace_id = parent_trace.get("id") if parent_trace else getattr(member, "run_id", None)
        self.telemetry.record_interaction(
            source, target, interaction_type,
            trace_id=trace_id,
            operation=f"team.{interaction_type}",
            source_display_name=self.name if source == self.name else source,
            target_display_name=getattr(member, "display_name", getattr(member, "name", target)),
            metadata={"team": self.name},
        )

    def run(self, message: str) -> TeamResult:
        if not self.member_list:
            raise ValueError("A team needs at least one member.")

        member_descriptions = self._build_member_descriptions()

        if self.mode == TeamMode.broadcast:
            return self._run_broadcast(message)
        if self.mode == TeamMode.tasks:
            return self._run_tasks(message)
        if self.mode == TeamMode.route:
            return self._run_route(message)

        return self._run_coordinate(message, member_descriptions)

    def _run_broadcast(self, message: str) -> TeamResult:
        results = {}
        for member in self.member_list:
            result = self._delegate(member.name, message)
            results[member.name] = result
        combined = "\n\n".join(f"**{name}**: {out}" for name, out in results.items())
        return TeamResult(content=combined or "No member produced output.", member_outputs=results)

    def _run_tasks(self, message: str) -> TeamResult:
        results = {}
        for member in self.member_list:
            task_desc = f"{message}\n\nFocus on your area: {getattr(member, 'description', '') or getattr(member, 'role', 'general')}"
            result = self._delegate(member.name, task_desc)
            results[member.name] = result
        combined = "\n\n".join(f"**{name}**: {out}" for name, out in results.items())
        return TeamResult(content=combined or "No member produced output.", member_outputs=results)

    def _run_route(self, message: str) -> TeamResult:
        import re
        best_member = self.member_list[0]
        best_score = 0
        msg_lower = message.lower()
        for member in self.member_list:
            desc = (getattr(member, "description", "") or getattr(member, "role", "") or "").lower()
            tools = " ".join(getattr(member, "_tool_map", {}).keys()).lower()
            score = sum(1 for word in re.findall(r'\w+', msg_lower) if word in desc or word in tools)
            if score > best_score:
                best_score, best_member = score, member
        result = self._delegate(best_member.name, message)
        return TeamResult(content=result, member_outputs={best_member.name: result})

    def _run_coordinate(self, message: str, member_descriptions: str) -> TeamResult:
        leader_trace = self.telemetry.start_trace(f"{self.name}_run") if self.telemetry else None

        @tool(name="delegate_task_to_member", description=f"Delegates a task to a team member and returns their response. Available members:\n{member_descriptions}")
        def delegate_task_to_member(member_name: str, task_description: str) -> str:
            return self._delegate(member_name, task_description, parent_trace=leader_trace)

        leader_agent = Agent(
            name=self.name,
            model=self.leader_model,
            tools=[delegate_task_to_member],
            tool_allowlist=["delegate_task_to_member"],
            telemetry=self.telemetry,
            session_id=message[:64],
            max_iterations=self.max_delegations,
            role="Team leader coordinating a team of specialists.",
            description=f"Team leader. Delegate tasks to specialists. Available members:\n{member_descriptions}",
            system=f"You coordinate a team of specialized AI agents. You must delegate every user request to the appropriate team member.\n\nAvailable team members:\n{member_descriptions}\n\nRules:\n1. NEVER answer the user directly\n2. ALWAYS use delegate_task_to_member tool for every request\n3. Choose the best member based on their role and tools\n4. After receiving the member's response, you may synthesize it for the user\n5. If a request needs multiple specialists, delegate one at a time",
        )
        output = leader_agent.run(message)
        if self.telemetry and leader_trace:
            self.telemetry.end_trace(leader_trace, input={"message": message}, output=output.content)
        return TeamResult(content=output.content or "")

    def record_interaction(self, source: str, target: str, interaction_type: str = "delegation", *, trace_id: str | None = None, operation: str | None = None, tool_name: str | None = None, source_display_name: str | None = None, target_display_name: str | None = None, metadata: Dict[str, Any] | None = None) -> None:
        record = getattr(self.telemetry, "record_interaction", None)
        if callable(record):
            record(source, target, interaction_type, trace_id=trace_id, operation=operation, tool_name=tool_name, source_display_name=source_display_name, target_display_name=target_display_name, metadata={"team": self.name, **(metadata or {})})