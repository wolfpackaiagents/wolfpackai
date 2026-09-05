"""03 - Multi-provider: pick the model, stream the tool-calling loop.

Rewrites the previous `multi_provider_tools.py`. The provider/model is chosen from
the first CLI argument (default `openai:gpt-4o-mini`). Any of these work:

    openai:gpt-4o-mini              -> needs OPENAI_API_KEY
    anthropic:claude-haiku-4-5      -> needs ANTHROPIC_API_KEY
    ollama:qwen2.5                  -> needs OLLAMA_BASE_URL (and the model loaded)

The same weather + calculator tools are shared by every provider. Streaming
(`run(..., stream=True)`) emits events, including `RunTool` events carrying the
tool name and its result.

Run:
    uv run python examples/02_tools/03_multi_provider.py
    uv run python examples/02_tools/03_multi_provider.py anthropic:claude-haiku-4-5
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wolfpack import Agent, get_model, tool


@tool
def get_weather(city: str) -> str:
    """Returns the current weather for a city.

    Args:
        city: the city name, e.g. Madrid.
    """
    return f"{city}: 22 C, partly cloudy."


@tool
def calculator(expression: str) -> str:
    """Evaluates a basic arithmetic expression.

    Args:
        expression: an arithmetic expression, e.g. (2 + 3) * 4.
    """
    try:
        return eval(expression, {"__builtins__": {}}, {})  # noqa: S307
    except Exception as exc:  # noqa: BLE001
        return f"Could not evaluate '{expression}': {exc}"


def main() -> None:
    model_spec = sys.argv[1] if len(sys.argv) > 1 else "openai:gpt-4o-mini"
    prompt = " ".join(sys.argv[2:]) or "What's the weather in Madrid and what is (2 + 3) * 4?"

    try:
        model = get_model(model_spec)
    except Exception:
        raise SystemExit(
            f"Could not create model '{model_spec}'. "
            "Make sure the corresponding API key is set (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.) "
            "or that the provider spec is correct."
        )
    provider = getattr(model, "provider", model_spec.split(":", 1)[0])

    agent = Agent(
        name="MultiProvider",
        model=model,
        role="A helpful assistant with tools",
        goal="Answer using the weather and calculator tools when relevant.",
        tools=[get_weather, calculator],
    )

    print(f"Provider/model requested : {model_spec}")
    print(f"Resolved provider/model   : {provider} / {model.model_id}")
    print(f"Agent                     : {agent.id}")
    print(f"Prompt                    : {prompt}\n")

    for ev in agent.run(prompt, stream=True):
        if ev.event_type == "RunTool":
            print(f"  [tool] {ev.tool_name}({ev.tool_arguments}) -> {ev.result}")
        elif ev.event_type == "RunContent" and ev.content:
            print(f"  [content] {ev.content}")
        elif ev.event_type == "RunStep":
            calls = ev.tool_calls or []
            if calls:
                names = ", ".join(c.get("name", "") for c in calls)
                print(f"  [step] model asked for tools: {names}")
        elif ev.event_type == "RunCompleted":
            metrics = ev.metrics or {}
            print("  [completed] usage:", metrics.get("usage"))
        elif ev.event_type == "RunFailed":
            print("  [failed]", ev.error)


if __name__ == "__main__":
    main()