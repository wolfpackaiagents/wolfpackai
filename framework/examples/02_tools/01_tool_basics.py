"""01 - Tool basics: a single agent with several @tool callables.

Shows the simplest way to give an Agent tools: plain functions decorated with
`@tool`. The decorator builds a `Function` and infers the JSON schema from the
type hints plus the Google-style docstring (`Args:` section). Docstrings are
model-facing, so they are written in English.

The agent runs the full tool-calling loop: it decides which tools to call,
executes them, and composes the final answer. We inspect the returned `RunOutput`
for the final text, the list of executed tool calls, and total token usage.

Run:
    uv run python examples/02_tools/01_tool_basics.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wolfpack import Agent, get_model_from_env, tool


@tool
def get_weather(city: str) -> str:
    """Returns the current weather for a city.

    Args:
        city: the city name, e.g. Madrid or London.
    """
    conditions = {"madrid": "22 C, partly cloudy", "london": "14 C, light rain"}
    key = city.strip().lower()
    if key in conditions:
        return f"{city}: {conditions[key]}"
    return f"{city}: unknown, assume 20 C and clear sky."


@tool
def calculator(expression: str) -> str:
    """Evaluates a basic arithmetic expression.

    Args:
        expression: a simple arithmetic expression with +, -, * and /,
            e.g. "14 * 7".
    """
    try:
        return eval(expression, {"__builtins__": {}}, {})  # noqa: S307
    except Exception as exc:  # noqa: BLE001
        return f"Could not evaluate '{expression}': {exc}"


@tool
def get_time_now() -> str:
    """Returns the current UTC date and time."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def main() -> None:
    try:
        model = get_model_from_env()
    except Exception:
        raise SystemExit(
            "No API key found (OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, "
            "or OLLAMA_BASE_URL). Set one and re-run."
        )

    agent = Agent(
        name="Generalist",
        model=model,
        role="A helpful assistant with several tools",
        goal="Answer questions accurately, using tools whenever they help.",
        backstory="A wolfpack agent with a basic toolkit, ready to solve everyday problems.",
        tools=[get_weather, calculator, get_time_now],
    )

    question = "What's the weather in Madrid and what is 14 * 7?"
    print(f"Model: {model.model_id}\nAgent: {agent.id}\n")
    print(f"Prompt: {question}\n")

    output = agent.run(question)

    print("=== FINAL ANSWER ===")
    print(output.content)
    print()
    print("=== TOOL CALLS EXECUTED ===")
    if output.tool_calls:
        for call in output.tool_calls:
            print(f"  {call['name']}({call['arguments']})")
    else:
        print("  (none)")
    print()
    print("=== USAGE ===")
    print(output.usage)
    print()
    if output.failed:
        print("Run FAILED:", output.error)


if __name__ == "__main__":
    main()