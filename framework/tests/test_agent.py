from types import SimpleNamespace

import pytest

from wolfpack import Agent, tool, Toolkit
from wolfpack.memory import SQLiteSessionStore
from wolfpack.models.base import BaseModel, ModelResponse, OpenAILike, ReportedCost
from wolfpack.models.message import Message
from wolfpack.observer.client import WolfpackObserver
from wolfpack.tools.function import Function, FunctionCall
from wolfpack.tools.json_schema import get_json_schema
from wolfpack.tools.factory import create_knowledge_search_tool

from fake_model import FakeModel, StreamingFakeModel


@tool
def get_weather(city: str) -> str:
    """Gets the weather for a city.

    Args:
        city: the city name.
    """
    return f"En {city} hace sol, 24 grados."


@tool(requires_confirmation=True)
def destructive_op(target: str) -> str:
    """Operation that requires confirmation.

    Args:
        target: the target.
    """
    return "hecho"


@tool
def unavailable_weather(city: str) -> str:
    raise RuntimeError("weather service unavailable")


class MathTools(Toolkit):
    def __init__(self):
        super().__init__(name="math")
        self.register(self.sum)

    def sum(self, a: int, b: int) -> int:
        """Adds two integers.

        Args:
            a: first integer.
            b: second integer.
        """
        return a + b


def test_tool_decorator_creates_function():
    assert hasattr(get_weather, "function")
    assert isinstance(get_weather.function, Function)


def test_schema_inference():
    def probe(city: str = "x") -> str:
        return city

    schema = get_json_schema(probe, "probe")
    assert schema["parameters"]["properties"]["city"]["type"] == "string"


def test_function_call_executes():
    fn = get_weather.function
    fc = fn.get_function_call("call_1", {"city": "Lima"})
    res = fc.execute()
    assert res.status == "success"
    assert "Lima" in res.result


def test_requires_confirmation_blocks_execution():
    fc = destructive_op.function.get_function_call("c1", {"target": "x"})
    res = fc.execute()
    assert res.status == "tool_confirmation"


def test_toolkit_registers_tools():
    tk = MathTools()
    assert "sum" in tk.functions
    res = tk.functions["sum"].get_function_call("c1", {"a": 2, "b": 3}).execute()
    assert res.result == 5


def test_agent_runs_tool_loop():
    agent = Agent(
        name="Clima",
        model=FakeModel(tool_name="get_weather"),
        tools=[get_weather],
    )
    output = agent.run("¿Cómo está el clima en Madrid?")
    assert output.failed is False
    assert "La respuesta final." == output.content
    assert len(output.messages) == 2  # assistant(tool call) + assistant(final)
    assert output.tool_calls == [{"name": "get_weather", "arguments": {"city": "Madrid"}}]
    assert output.usage["input_tokens"] == 15


def test_agent_observations_include_hierarchy_payloads_and_redact_pii():
    observer = WolfpackObserver("http://amp.test")
    agent = Agent(
        name="Clima",
        model=FakeModel(tool_name="get_weather"),
        tools=[get_weather],
        telemetry=observer,
    )

    agent.run("Contact ana@example.com and tell me the weather in Madrid.")

    observations = [event["body"] for event in observer._buffer if event["type"] == "observation-end"]
    trace = next(observation for observation in observations if observation["type"] == "TRACE")
    steps = [observation for observation in observations if observation["type"] == "SPAN"]
    generation = next(observation for observation in observations if observation["type"] == "GENERATION")
    tool_observation = next(observation for observation in observations if observation["type"] == "TOOL")

    assert all(step["parent_observation_id"] == trace["id"] for step in steps)
    assert generation["parent_observation_id"] == steps[0]["id"]
    assert tool_observation["parent_observation_id"] == steps[0]["id"]
    assert generation["input"][1]["content"] == "Contact [PII_REDACTED] and tell me the weather in Madrid."
    assert trace["input"] == [{"role": "user", "content": "Contact [PII_REDACTED] and tell me the weather in Madrid."}]
    assert generation["output"]["tool_calls"][0]["function"]["name"] == "get_weather"
    assert tool_observation["input"] == {"city": "Madrid"}
    assert "Madrid" in tool_observation["output"]
    assert all("input" in step and "output" in step for step in steps)
    assert "cost" not in generation


def test_agent_observation_includes_only_provider_reported_generation_cost():
    class CostModel(BaseModel):
        provider = "gateway"
        model_id = "cost-model"

        def invoke(self, messages, tools=None):
            return ModelResponse(
                message=Message(role="assistant", content="done"),
                cost=ReportedCost(amount=0.0025, currency="USD", source="gateway"),
            )

    observer = WolfpackObserver("http://amp.test")
    Agent(name="Cost", model=CostModel(), telemetry=observer).run("hello")

    generation = next(event["body"] for event in observer._buffer if event["type"] == "observation-end" and event["body"]["type"] == "GENERATION")
    trace = next(event["body"] for event in observer._buffer if event["type"] == "observation-end" and event["body"]["type"] == "TRACE")
    assert generation["cost"] == 0.0025
    assert generation["cost_currency"] == "USD"
    assert generation["cost_source"] == "gateway"
    assert "cost" not in trace


def test_openai_like_cost_requires_explicit_currency():
    model = object.__new__(OpenAILike)
    model.provider = "gateway"

    response_with_currency = SimpleNamespace(usage=SimpleNamespace(cost=0.001, currency="USD"))
    response_without_currency = SimpleNamespace(usage=SimpleNamespace(cost=0.001))
    from wolfpack.models.base import _reported_cost

    assert _reported_cost(response_with_currency, model.provider).to_dict() == {"amount": 0.001, "currency": "USD", "source": "gateway"}
    assert _reported_cost(response_without_currency, model.provider) is None


def test_streaming_agent_observation_includes_terminal_generation_cost():
    class CostStreamingModel(BaseModel):
        provider = "gateway"
        model_id = "cost-model"

        def invoke(self, messages, tools=None):
            raise AssertionError("stream should be used")

        def stream(self, messages, tools=None):
            yield ModelStreamChunk(content="done")
            yield ModelStreamChunk(
                response=ModelResponse(
                    message=Message(role="assistant", content="done"),
                    cost=ReportedCost(amount=0.001, currency="USD", source="gateway"),
                )
            )

    from wolfpack.models.base import ModelStreamChunk

    observer = WolfpackObserver("http://amp.test")
    list(Agent(name="Cost", model=CostStreamingModel(), telemetry=observer).run("hello", stream=True))

    generation = next(event["body"] for event in observer._buffer if event["type"] == "observation-end" and event["body"]["type"] == "GENERATION")
    assert generation["cost"] == 0.001
    assert generation["cost_currency"] == "USD"
    assert generation["cost_source"] == "gateway"


def test_structured_retry_forwards_terminal_reported_cost_to_observer():
    from pydantic import BaseModel as PydanticBaseModel

    class Output(PydanticBaseModel):
        answer: str

    class RetryingCostModel(BaseModel):
        provider = "gateway"
        model_id = "cost-model"

        def __init__(self):
            self.calls = 0

        def invoke(self, messages, tools=None):
            self.calls += 1
            if self.calls == 1:
                return ModelResponse(message=Message(role="assistant", content="not json"))
            return ModelResponse(
                message=Message(role="assistant", content='{"answer": "done"}'),
                cost=ReportedCost(amount=0.003, currency="USD", source="gateway"),
            )

    observer = WolfpackObserver("http://amp.test")
    output = Agent(name="Cost", model=RetryingCostModel(), output_schema=Output, telemetry=observer).run("hello")

    generations = [
        event["body"]
        for event in observer._buffer
        if event["type"] == "observation-end" and event["body"]["type"] == "GENERATION"
    ]
    assert output.content == '{"answer": "done"}'
    assert len(generations) == 2
    assert "cost" not in generations[0]
    assert generations[1]["cost"] == 0.003
    assert generations[1]["cost_currency"] == "USD"
    assert generations[1]["cost_source"] == "gateway"


def test_agent_observation_records_tool_errors_with_arguments():
    observer = WolfpackObserver("http://amp.test")
    agent = Agent(
        name="Clima",
        model=FakeModel(tool_name="unavailable_weather"),
        tools=[unavailable_weather],
        telemetry=observer,
    )

    agent.run("How is the weather in Madrid?")

    tool_observation = next(event["body"] for event in observer._buffer if event["type"] == "observation-end" and event["body"]["type"] == "TOOL")
    assert tool_observation["input"] == {"city": "Madrid"}
    assert tool_observation["error"] == "weather service unavailable"


def test_agent_stream_events():
    agent = Agent(
        name="Clima",
        model=FakeModel(tool_name="get_weather"),
        tools=[get_weather],
    )
    events = list(agent.run("hola", stream=True))
    from wolfpack.agent.events import RunEventType

    types = [e.event_type for e in events]
    assert RunEventType.RUN_STARTED in types
    assert RunEventType.RUN_COMPLETED in types


def test_agent_streams_provider_chunks_once_and_preserves_tool_loop():
    agent = Agent(
        name="Clima",
        model=StreamingFakeModel(tool_name="get_weather"),
        tools=[get_weather],
    )

    events = list(agent.run("hola", stream=True))
    content = [event.content for event in events if event.event_type == "RunContent"]

    assert content == ["La respuesta ", "final."]
    assert sum(event.event_type == "RunTool" for event in events) == 1
    completed = next(event for event in events if event.event_type == "RunCompleted")
    assert completed.output["content"] == "La respuesta final."


def test_streaming_agent_emits_observations_with_step_children():
    observer = WolfpackObserver("http://amp.test")
    agent = Agent(
        name="Clima",
        model=StreamingFakeModel(tool_name="get_weather"),
        tools=[get_weather],
        telemetry=observer,
    )

    list(agent.run("hola", stream=True))

    observations = [event["body"] for event in observer._buffer]
    trace = next(observation for observation in observations if observation["type"] == "TRACE")
    step = next(observation for observation in observations if observation["type"] == "SPAN")
    generation = next(observation for observation in observations if observation["type"] == "GENERATION")
    tool_observation = next(observation for observation in observations if observation["type"] == "TOOL")

    assert step["parent_observation_id"] == trace["id"]
    assert generation["parent_observation_id"] == step["id"]
    assert tool_observation["parent_observation_id"] == step["id"]


def test_openai_like_stream_assembles_text_usage_and_fragmented_tool_calls():
    model = object.__new__(OpenAILike)
    model.model_id = "gpt-test"
    model.temperature = None
    model.max_tokens = None
    chunks = [
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="hello ", reasoning_content=None, tool_calls=[]))],
            usage=None,
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="world", reasoning_content=None, tool_calls=[]))],
            usage=None,
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content=None, reasoning_content=None, tool_calls=[
                SimpleNamespace(index=0, id="call_1", function=SimpleNamespace(name="weather", arguments='{"city":'))
            ]))],
            usage=None,
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content=None, reasoning_content=None, tool_calls=[
                SimpleNamespace(index=0, id=None, function=SimpleNamespace(name=None, arguments='"Madrid"}'))
            ]))],
            usage=None,
        ),
        SimpleNamespace(choices=[], usage=SimpleNamespace(prompt_tokens=7, completion_tokens=4)),
    ]
    model._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: iter(chunks))))

    events = list(model.stream([{"role": "user", "content": "hi"}], tools=None))

    assert [event.content for event in events[:-1]] == ["hello ", "world"]
    response = events[-1].response
    assert response.message.content == "hello world"
    assert response.message.tool_calls[0].arguments == '{"city":"Madrid"}'
    assert response.usage == {"input_tokens": 7, "output_tokens": 4}


def test_knowledge_search_tool_factory():
    from wolfpack.knowledge.knowledge import Knowledge
    from wolfpack.vectordb.base import MemoryVectorDb

    class FakeEmb:
        def embed(self, texts):
            # deterministic embedding: 3 dims
            return [[1.0 if c else 0.0, 1.0, 0.5] for c in texts]

    kb = Knowledge(vector_db=MemoryVectorDb(), embedding_model=FakeEmb())
    kb.add_text("El clima en Madrid es cálido y soleado.", chunk=False)
    fn = create_knowledge_search_tool(kb, name="search_knowledge")
    fc = fn.get_function_call("c1", {"query": "clima Madrid"})
    res = fc.execute()
    assert res.status == "success"
    assert "Madrid" in res.result


@pytest.mark.asyncio
async def test_async():
    import asyncio
    assert True


def test_agent_failed_when_model_raises():
    class Boom(BaseModel):
        provider = "fake"
        model_id = "boom"

        def invoke(self, messages, tools=None):
            raise RuntimeError("boom")

    agent = Agent(name="x", model=Boom())
    out = agent.run("hola")
    assert out.failed is True
    assert "boom" in out.error


def test_sqlite_session_store_persists_messages_and_metadata(tmp_path):
    db_path = str(tmp_path / "sessions.db")
    store = SQLiteSessionStore(db_path)
    session = store.create_session("customer-7")
    session.add_user_message("My preferred language is Portuguese.")
    session.metadata["user_id"] = "7"
    store.save(session)

    restored = SQLiteSessionStore(db_path).get("customer-7")
    assert restored is not None
    assert restored.get_messages() == [{"role": "user", "content": "My preferred language is Portuguese."}]
    assert restored.metadata == {"user_id": "7"}


def test_agent_uses_persistent_session_history(tmp_path):
    class RecordingModel(BaseModel):
        provider = "fake"
        model_id = "recording"

        def __init__(self):
            self.requests = []

        def invoke(self, messages, tools=None):
            self.requests.append(messages)
            return type("Response", (), {"message": Message(role="assistant", content="ack"), "usage": {}})()

    store = SQLiteSessionStore(str(tmp_path / "sessions.db"))
    model = RecordingModel()
    agent = Agent(name="Memory", model=model, session_id="s1", session_store=store)
    agent.run("first message")
    agent.run("second message")

    second_request = model.requests[1]
    assert any(m.get("content") == "first message" for m in second_request)
    assert any(m.get("content") == "ack" for m in second_request)
