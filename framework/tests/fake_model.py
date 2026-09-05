"""FakeModel: deterministic model for tests (no external calls).

Simulates the tool-calling loop: responds with tool_calls on the first call(s)
and with the final response when passed the tool result. Lets you test the Agent
end-to-end without a network.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from wolfpack.models.base import BaseModel, ModelResponse, ModelStreamChunk
from wolfpack.models.message import Message, ToolCall


class FakeModel(BaseModel):
    def __init__(self, tool_name="get_weather", final_response="La respuesta final."):
        self.provider = "fake"
        self.model_id = "fake-model"
        self.tool_name = tool_name
        self.final_response = final_response
        self.calls = 0

    def invoke(self, messages, tools=None) -> ModelResponse:
        self.calls += 1
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        if not tool_msgs:
            # first turn: call the tool
            return ModelResponse(
                message=Message(
                    role="assistant",
                    content=None,
                    tool_calls=[ToolCall(id="call_1", name=self.tool_name, arguments='{"city": "Madrid"}')],
                ),
                usage={"input_tokens": 5, "output_tokens": 3},
            )
        # tool result already present: return the final response
        return ModelResponse(
            message=Message(role="assistant", content=self.final_response),
            usage={"input_tokens": 10, "output_tokens": 5},
        )


class SequentialFakeModel(BaseModel):
    """Invokes a list of instrumented responses and returns the last one from then
    on (for multi-step scenarios)."""

    def __init__(self, responses: List[ModelResponse]):
        self.responses = responses
        self.calls = 0
        self.provider = "fake"
        self.model_id = "fake-sequential"

    def invoke(self, messages, tools=None) -> ModelResponse:
        idx = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        return self.responses[idx]


class StreamingFakeModel(FakeModel):
    """Fake provider that yields a tool call followed by text chunks."""

    def stream(self, messages, tools=None):
        tool_msgs = [message for message in messages if message.get("role") == "tool"]
        if not tool_msgs:
            response = self.invoke(messages, tools)
            yield ModelStreamChunk(response=response)
            return

        self.calls += 1
        yield ModelStreamChunk(content="La respuesta ")
        yield ModelStreamChunk(content="final.")
        yield ModelStreamChunk(
            response=ModelResponse(
                message=Message(role="assistant", content="La respuesta final."),
                usage={"input_tokens": 10, "output_tokens": 5},
            )
        )
