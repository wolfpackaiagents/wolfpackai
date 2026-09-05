"""Tests for the delegation-based Team pattern.

The leader model decides which specialist to invoke via the
delegate_task_to_member LLM tool.
"""

from wolfpack.team import Team, TeamMode


class Member:
    def __init__(self, name: str):
        self.name = name
        self.run_id = f"run_{name}"

    def run(self, message: str):
        return type("Output", (), {"content": f"{self.name} processed: {message}", "run_id": self.run_id, "failed": False})()


class InteractionTracker:
    def __init__(self):
        self.interactions = []
        self.traces = []

    def record_interaction(self, source, target, interaction_type, **kwargs):
        self.interactions.append((source, target, interaction_type, kwargs))

    def start_trace(self, name: str, run_id: str | None = None):
        tid = run_id or f"trace_{name}"
        trace = {"id": tid, "name": name}
        self.traces.append(trace)
        return trace

    def end_trace(self, trace, **kwargs):
        pass

    def start_span(self, kind: str, name: str, **kwargs):
        return {"id": f"span_{name}", "name": name, "kind": kind}

    def end_span(self, span, **kwargs):
        pass


def test_team_needs_at_least_one_member():
    try:
        Team("empty", []).run("hello")
        assert False, "should have raised"
    except ValueError as e:
        assert "needs at least one member" in str(e)


def test_team_delegates_to_member():
    a = Member("alpha")
    tracker = InteractionTracker()
    team = Team("coordinator", [a], telemetry=tracker)
    result = team._delegate("alpha", "test task", parent_trace={"id": "trace-root"})
    assert "alpha processed: test task" in result


def test_team_returns_error_for_unknown_member():
    a = Member("alpha")
    tracker = InteractionTracker()
    team = Team("coordinator", [a], telemetry=tracker)
    result = team._delegate("unknown_member", "test task")
    assert "Error" in result
    assert "unknown_member" in result


def test_callers_can_record_contextual_team_interactions():
    tracker = InteractionTracker()
    team = Team("lead", [], telemetry=tracker)

    team.record_interaction(
        "research",
        "knowledge-search",
        "tool",
        trace_id="trace-42",
        operation="tool.invoke",
        tool_name="search_support_knowledge",
        source_display_name="Research Specialist",
        target_display_name="Knowledge Search",
        metadata={"query_kind": "incident"},
    )

    assert tracker.interactions == [
        ("research", "knowledge-search", "tool", {
            "trace_id": "trace-42",
            "operation": "tool.invoke",
            "tool_name": "search_support_knowledge",
            "source_display_name": "Research Specialist",
            "target_display_name": "Knowledge Search",
            "metadata": {"team": "lead", "query_kind": "incident"},
        }),
    ]


def test_team_run_creates_leader_agent_and_trace():
    class FakeModel:
        provider = "test"
        model_id = "test-model"
        def invoke(self, messages, tools=None):
            from wolfpack.models.base import ModelResponse
            from wolfpack.models.message import Message
            return ModelResponse(message=Message(role="assistant", content="done"))
        def stream(self, messages, tools=None):
            from wolfpack.models.base import ModelStreamChunk, ModelResponse
            from wolfpack.models.message import Message
            yield ModelStreamChunk(response=ModelResponse(message=Message(role="assistant", content="done")))

    a = Member("alpha")
    tracker = InteractionTracker()
    team = Team("coordinator", [a], leader_model=FakeModel(), telemetry=tracker)
    result = team.run("investigate")
    assert isinstance(result.content, str) and len(result.content) > 0
    assert tracker.traces
    assert any(t["name"] == "coordinator_run" for t in tracker.traces)