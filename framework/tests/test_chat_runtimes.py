from wolfpack.runtimes.chat import CHAT_RUNTIME_KEYS, build_chat_runtime
from wolfpack.models.base import BaseModel, ModelResponse, ModelStreamChunk
from wolfpack.models.message import Message, ToolCall


class ToolThenTextModel(BaseModel):
    provider = "test"
    model_id = "test-model"

    def __init__(self, tool_name=None):
        self.tool_name = tool_name

    def invoke(self, messages, tools=None):
        return next(self.stream(messages, tools)).response

    def stream(self, messages, tools=None):
        if self.tool_name and not any(message["role"] == "tool" for message in messages):
            yield ModelStreamChunk(response=ModelResponse(message=Message(role="assistant", tool_calls=[ToolCall(id="tool-1", name=self.tool_name, arguments='{"query": "password reset"}')]), usage={}))
            return
        yield ModelStreamChunk(response=ModelResponse(message=Message(role="assistant", content="resolved"), usage={}))


def test_chat_runtime_registry_is_fixed_and_rejects_unknown_entries():
    assert CHAT_RUNTIME_KEYS == frozenset({("weather-operations", "1.0.0"), ("support-orchestrator", "1.0.0")})
    assert build_chat_runtime("unknown", "1.0.0", ToolThenTextModel()) is None
    assert build_chat_runtime("weather-operations", "2.0.0", ToolThenTextModel()) is None


def test_support_runtime_has_fixed_coordinate_members_and_read_only_knowledge_tool():
    runtime = build_chat_runtime("support-orchestrator", "1.0.0", ToolThenTextModel("search_support_knowledge"))

    events = list(runtime.stream("I cannot reset my password"))

    assert [event.type for event in events] == ["run", "team.member", "team.member", "tool", "team.member", "final"]
    assert [event.data["member"] for event in events if event.type == "team.member"] == ["support-triage", "knowledge-specialist", "knowledge-specialist"]
    tool = next(event for event in events if event.type == "tool")
    assert tool.data["tool_name"] == "search_support_knowledge"
    assert tool.data["result"] == "Knowledge article: Password resets are completed from the sign-in page."
    assert runtime.tool_names == {"search_support_knowledge"}
