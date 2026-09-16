"""Live provider verification for Model Routing.

Run explicitly with: uv run pytest tests/test_model_routing_live.py -m integration -v
"""

from __future__ import annotations

import json
import os

import pytest

from wolfpack import Agent
from wolfpack.models.base import OpenAILike
from wolfpack.models.routing import ModelPolicy, ModelRoute, ModelRouter, ModelTarget
from wolfpack.models.utils import get_model


pytestmark = pytest.mark.integration


def _target(model, input_price: float, output_price: float) -> ModelTarget:
    return ModelTarget(
        model=model,
        input_price_per_million=input_price,
        output_price_per_million=output_price,
    )


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY") or not os.environ.get("ANTHROPIC_API_KEY"),
    reason="OPENAI_API_KEY and ANTHROPIC_API_KEY are required",
)
def test_live_policy_routes_reasoning_task_and_retryable_fallback():
    reasoning = get_model("anthropic:claude-haiku-4-5")
    task = get_model("openai:gpt-4o-mini")
    policy = ModelPolicy(
        name="live-routing-verification",
        version="1",
        reasoning=ModelRoute(primary=_target(reasoning, 1.0, 5.0)),
        task=ModelRoute(primary=_target(task, 0.15, 0.60)),
    )

    reasoning_response = ModelRouter(policy).invoke(
        [{"role": "user", "content": "Reply exactly with ROUTING_REASONING_OK."}],
    )
    assert reasoning_response.routing["selected"] == {"provider": "anthropic", "model": "claude-haiku-4-5"}
    assert reasoning_response.routing["purpose"] == "reasoning"
    assert reasoning_response.routing["fallback_index"] == 0

    agent = Agent(name="live-routing-task", model_policy=policy, task_selector="simple")
    agent.run("Reply exactly with ROUTING_TASK_OK.")
    assert isinstance(agent.model, ModelRouter)
    assert agent.model.last_routing["selected"] == {"provider": "openai", "model": "gpt-4o-mini"}
    assert agent.model.last_routing["purpose"] == "task"
    assert agent.model.last_routing["fallback_index"] == 0

    unavailable_primary = OpenAILike(
        id="unavailable-routing-probe",
        provider="openai",
        api_key="not-a-real-secret",
        base_url="http://127.0.0.1:9",
    )
    fallback_response = ModelRouter(
        ModelPolicy(
            name="live-fallback-verification",
            reasoning=ModelRoute(
                primary=_target(unavailable_primary, 0.15, 0.60),
                fallbacks=[_target(reasoning, 1.0, 5.0)],
            ),
        )
    ).invoke([{"role": "user", "content": "Reply exactly with ROUTING_FALLBACK_OK."}])

    routing = fallback_response.routing
    assert routing["selected"] == {"provider": "anthropic", "model": "claude-haiku-4-5"}
    assert routing["fallback_index"] == 1
    assert routing["attempts"][0]["outcome"] == "error"
    assert routing["attempts"][0]["error_type"] == "transient"
    assert "not-a-real-secret" not in json.dumps(routing)


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY")
    or not os.environ.get("OLLAMA_BASE_URL")
    or not os.environ.get("OLLAMA_MODEL"),
    reason="OPENAI_API_KEY, OLLAMA_BASE_URL and OLLAMA_MODEL are required",
)
def test_live_openai_primary_and_ollama_task_policy():
    ollama_model_id = os.environ["OLLAMA_MODEL"]
    primary = get_model("openai:gpt-4.1-mini")
    task = get_model(f"ollama:{ollama_model_id}")
    policy = ModelPolicy(
        name="openai-ollama-live-routing",
        version="1",
        reasoning=ModelRoute(primary=_target(primary, 0.40, 1.60)),
        task=ModelRoute(primary=_target(task, 0.0, 0.0)),
    )

    primary_response = ModelRouter(policy).invoke(
        [{"role": "user", "content": "Reply exactly with OPENAI_PRIMARY_OK."}],
    )
    assert primary_response.routing["selected"] == {"provider": "openai", "model": "gpt-4.1-mini"}
    assert primary_response.routing["purpose"] == "reasoning"
    assert primary_response.routing["fallback_index"] == 0

    agent = Agent(name="openai-ollama-task", model_policy=policy, task_selector="simple")
    task_response = agent.run("Reply exactly with OLLAMA_TASK_OK.")
    assert not task_response.failed
    assert isinstance(agent.model, ModelRouter)
    assert agent.model.last_routing["selected"] == {"provider": "ollama", "model": ollama_model_id}
    assert agent.model.last_routing["purpose"] == "task"
    assert agent.model.last_routing["fallback_index"] == 0
