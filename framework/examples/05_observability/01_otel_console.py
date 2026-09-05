"""OTel console example.

Shows the framework's native OpenTelemetry path. `create_tracker()` returns an
`OTelTracker` whose spans are printed to the console via `ConsoleSpanExporter`
(when `WOLFPACK_TRACER=otel` is set). Opentelemetry is optional: if the SDK is not
installed, `create_tracker()` falls back to a `NoopTracker` and we print a note.

Run from the `framework` dir:
    uv run python examples/05_observability/01_otel_console.py
"""

import os

from wolfpack import Agent, get_model_from_env, tool


@tool
def get_weather(city: str) -> str:
    """Gets the weather for a city.

    Args:
        city: the city name.
    """
    return f"Weather in {city}: 22°C, partly cloudy."


def main() -> None:
    os.environ.setdefault("WOLFPACK_TRACER", "otel")

    try:
        from wolfpack.telemetry.otel import create_tracker

        tracker = create_tracker()
    except Exception as exc:  # pragma: no cover - guard for a missing SDK
        tracker = None
        print(f"[otel] OTEL import failed ({exc}); using noop tracing.")

    if tracker is None or not tracker:
        # NoopTracker.__bool__ is False; a real OTelTracker is truthy.
        print(
            "[otel] OpenTelemetry SDK not installed -> NoopTracker active. "
            "The example still runs; spans are enabled when you `uv add opentelemetry-*`."
        )
        from wolfpack.telemetry.otel import NoopTracker

        tracker = tracker or NoopTracker()
    else:
        print("[otel] OTel console exporter active: spans will print below.\n")

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
        backstory="A wolfpack agent with a weather tool, instrumented with OpenTelemetry tracing.",
        tools=[get_weather],
        telemetry=tracker,
    )
    output = agent.run("What is the weather in Lisbon?")
    print("\n--- run result ---")
    print("status:", "ok" if not output.failed else output.error)
    print("answer:", output.content)
    print("usage:", output.usage)


if __name__ == "__main__":
    main()