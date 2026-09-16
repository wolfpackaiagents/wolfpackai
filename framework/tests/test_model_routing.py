from __future__ import annotations

import pytest

from wolfpack.models.base import BaseModel, ModelResponse, ReportedCost
from wolfpack.models.message import Message
from wolfpack.models.routing import ModelPolicy, ModelRoute, ModelRouter, ModelTarget
from wolfpack import Agent
from wolfpack.observer.client import WolfpackObserver


class StubModel(BaseModel):
    def __init__(self, provider: str, model_id: str, response: ModelResponse | Exception):
        self.provider = provider
        self.model_id = model_id
        self.response = response
        self.calls = 0

    def invoke(self, messages, tools=None):
        self.calls += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class APIConnectionError(Exception):
    pass


def response(content: str, input_tokens: int = 10, output_tokens: int = 5, cost: float | None = None) -> ModelResponse:
    return ModelResponse(
        message=Message(role="assistant", content=content),
        usage={"input_tokens": input_tokens, "output_tokens": output_tokens},
        cost=ReportedCost(cost, "USD", "provider") if cost is not None else None,
    )


def target(model: BaseModel, input_price: float, output_price: float) -> ModelTarget:
    return ModelTarget(model=model, input_price_per_million=input_price, output_price_per_million=output_price)


def test_router_uses_reasoning_primary_and_records_equivalent_token_savings():
    reasoning = StubModel("anthropic", "claude-opus", response("reasoned", cost=0.30))
    policy = ModelPolicy(
        reasoning=ModelRoute(primary=target(reasoning, 15.0, 75.0)),
        baseline="reasoning",
    )

    routed = ModelRouter(policy).invoke([{"role": "user", "content": "Analyze this."}])

    assert routed.message.content == "reasoned"
    assert routed.routing["selected"]["provider"] == "anthropic"
    assert routed.routing["purpose"] == "reasoning"
    assert routed.routing["attempts"][0]["outcome"] == "success"
    assert routed.routing["actual_cost"]["amount"] == 0.30
    assert routed.routing["baseline_cost"]["amount"] == pytest.approx(0.000525)


def test_router_falls_back_after_retryable_error_and_records_failed_attempt():
    primary = StubModel("anthropic", "claude-opus", TimeoutError("timed out"))
    fallback = StubModel("openai", "gpt-mini", response("fallback", cost=0.02))
    policy = ModelPolicy(
        reasoning=ModelRoute(
            primary=target(primary, 15.0, 75.0),
            fallbacks=[target(fallback, 0.15, 0.60)],
        ),
    )

    routed = ModelRouter(policy).invoke([{"role": "user", "content": "Analyze this."}])

    assert routed.message.content == "fallback"
    assert primary.calls == 1
    assert fallback.calls == 1
    assert routed.routing["selected"]["model"] == "gpt-mini"
    assert routed.routing["fallback_index"] == 1
    assert [attempt["outcome"] for attempt in routed.routing["attempts"]] == ["error", "success"]
    assert routed.routing["attempts"][0]["error_type"] == "timeout"


def test_router_does_not_fallback_after_non_retryable_error():
    primary = StubModel("anthropic", "claude-opus", ValueError("invalid request"))
    fallback = StubModel("openai", "gpt-mini", response("fallback"))
    router = ModelRouter(
        ModelPolicy(
            reasoning=ModelRoute(primary=target(primary, 15.0, 75.0), fallbacks=[target(fallback, 0.15, 0.60)]),
        )
    )

    with pytest.raises(ValueError, match="invalid request"):
        router.invoke([{"role": "user", "content": "Analyze this."}])

    assert fallback.calls == 0


def test_router_falls_back_after_provider_connection_error():
    primary = StubModel("openai", "gpt-mini", APIConnectionError("connection failed"))
    fallback = StubModel("anthropic", "claude-haiku", response("fallback"))
    routed = ModelRouter(
        ModelPolicy(reasoning=ModelRoute(primary=target(primary, 0.15, 0.60), fallbacks=[target(fallback, 1.0, 5.0)]))
    ).invoke([{"role": "user", "content": "Analyze this."}])

    assert routed.routing["fallback_index"] == 1
    assert routed.routing["attempts"][0]["error_type"] == "transient"


def test_router_uses_task_route_when_requested():
    reasoning = StubModel("anthropic", "claude-opus", response("reasoned"))
    task = StubModel("ollama", "gemma-4b", response("task"))
    router = ModelRouter(
        ModelPolicy(
            reasoning=ModelRoute(primary=target(reasoning, 15.0, 75.0)),
            task=ModelRoute(primary=target(task, 0.0, 0.0)),
        )
    )

    routed = router.invoke([{"role": "user", "content": "Summarize this."}], purpose="task")

    assert routed.message.content == "task"
    assert routed.routing["purpose"] == "task"
    assert reasoning.calls == 0


def test_agent_uses_task_route_for_a_simple_tool_free_request():
    reasoning = StubModel("anthropic", "claude-opus", response("reasoned"))
    task = StubModel("ollama", "gemma-4b", response("task"))
    agent = Agent(
        name="router-agent",
        model_policy=ModelPolicy(
            reasoning=ModelRoute(primary=target(reasoning, 15.0, 75.0)),
            task=ModelRoute(primary=target(task, 0.0, 0.0)),
        ),
        task_selector="simple",
    )

    result = agent.run("Summarize this.")

    assert result.content == "task"
    assert task.calls == 1
    assert reasoning.calls == 0


def test_agent_attaches_routing_metadata_to_generation_telemetry():
    model = StubModel("anthropic", "claude-opus", response("reasoned", cost=0.03))
    observer = WolfpackObserver("http://amp.test")
    agent = Agent(
        name="router-agent",
        model_policy=ModelPolicy(reasoning=ModelRoute(primary=target(model, 15.0, 75.0))),
        telemetry=observer,
    )

    agent.run("Analyze this request in depth.")

    generation = next(event["body"] for event in observer._buffer if event["type"] == "observation-end" and event["body"]["type"] == "GENERATION")
    assert generation["metadata"]["routing"]["selected"] == {"provider": "anthropic", "model": "claude-opus"}
