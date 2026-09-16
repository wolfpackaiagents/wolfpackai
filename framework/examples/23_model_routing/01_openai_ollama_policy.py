"""Route reasoning to OpenAI and simple tasks to an Ollama model.

Required environment:
    OPENAI_API_KEY
    OLLAMA_BASE_URL
    OLLAMA_MODEL

Usage:
    uv run python examples/23_model_routing/01_openai_ollama_policy.py
"""

from __future__ import annotations

import os

from wolfpack import Agent, ModelPolicy, ModelRoute, ModelRouter, ModelTarget, get_model


def target(model, input_price_per_million: float, output_price_per_million: float) -> ModelTarget:
    return ModelTarget(
        model=model,
        input_price_per_million=input_price_per_million,
        output_price_per_million=output_price_per_million,
    )


def main() -> None:
    ollama_model = os.environ.get("OLLAMA_MODEL")
    if not ollama_model:
        raise SystemExit("Set OLLAMA_MODEL to a model available from OLLAMA_BASE_URL.")

    policy = ModelPolicy(
        name="openai-ollama",
        version="1",
        reasoning=ModelRoute(
            primary=target(get_model("openai:gpt-4.1-mini"), 0.40, 1.60),
        ),
        task=ModelRoute(
            primary=target(get_model(f"ollama:{ollama_model}"), 0.0, 0.0),
        ),
    )

    # Use the reasoning route directly when the request needs the primary model.
    reasoning = ModelRouter(policy).invoke([
        {"role": "user", "content": "Give one reason that request tracing helps debug agents."},
    ])
    print("REASONING ANSWER:", reasoning.message.get_text())
    print("REASONING ROUTE:", reasoning.routing["selected"])

    # A short, tool-free request uses the task route when task_selector is enabled.
    agent = Agent(name="routed-assistant", model_policy=policy, task_selector="simple")
    task = agent.run("Reply with the word ready.")
    print("TASK ANSWER:", task.content)
    print("TASK ROUTE:", agent.model.last_routing["selected"])
    print("TASK SAVINGS:", agent.model.last_routing["estimated_savings"])


if __name__ == "__main__":
    main()
