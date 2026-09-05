"""Streaming observability events.

`run(..., stream=True)` returns an iterator of `BaseRunEvent`s (content deltas,
tool calls, steps, completion). This example prints each raw event_type and then
summarizes which spans/steps the run produced.

Run from the `framework` dir:
    uv run python examples/05_observability/03_stream_events.py
"""

from collections import Counter

from wolfpack import Agent, get_model_from_env, tool


@tool
def get_weather(city: str) -> str:
    """Gets the weather for a city.

    Args:
        city: the city name.
    """
    return f"Weather in {city}: 22°C, partly cloudy."


def main() -> None:
    try:
        model = get_model_from_env()
    except Exception:
        raise SystemExit(
            "No API key found (OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, "
            "or OLLAMA_BASE_URL). Set one and re-run."
        )
    agent = Agent(
        name="weather-agent",
        model=model,
        role="Weather assistant",
        goal="Answer weather questions using the get_weather tool.",
        backstory="A wolfpack agent that demonstrates the streaming event API.",
        tools=[get_weather],
    )

    print("--- raw event feed (streaming) ---")
    counts: Counter = Counter()
    for ev in agent.run("What is the weather in Lisbon?", stream=True):
        counts[ev.event_type] += 1
        print(f"[{ev.event_type}]")

    print("\n--- event taxonomy summary ---")
    for kind, n in counts.most_common():
        print(f"{kind}: {n}")

    total_spans = counts.get("RunTool", 0) + counts.get("RunContent", 0) + counts.get("RunStep", 0)
    print(f"\nrun produced {total_spans} observable spans/steps "
          f"({counts.get('RunTool', 0)} tool calls, "
          f"{counts.get('RunContent', 0)} content deltas, "
          f"{counts.get('RunStep', 0)} steps) and {counts.get('RunCompleted', 0)} completion.")


if __name__ == "__main__":
    main()