"""End-to-end: a real-model wolfpack agent sends traces to AMP.

`WOLFPACK_AMP_URL` (default http://localhost:8200) points at the Wolfpack Control
Plane ingestion endpoint. `WolfpackObserver` implements the Tracker contract and
buffers events; `tracker.flush()` pushes them to `POST /api/public/ingestion`. Each
run is recorded as a trace with step observations containing generation and tool
children, including their inputs and outputs (with PII redacted by default).
If the AMP backend is down the observer swallows the connection error, so the
script keeps working and events are silently buffered.

Run from the `framework` dir:
    uv run python examples/05_observability/02_amp_observer.py
"""

import os

from wolfpack import Agent, MeshIdentity, get_model_from_env, tool
from wolfpack.observer.client import WolfpackObserver


@tool
def get_weather(city: str) -> str:
    """Gets the weather for a city.

    Args:
        city: the city name.
    """
    return f"Weather in {city}: 22°C, partly cloudy."


def main() -> None:
    amp_url = os.environ.get("WOLFPACK_AMP_URL", "http://localhost:8200")
    amp_key = os.environ.get("WOLFPACK_AMP_API_KEY", "pk-wp-dev:dev-secret")
    print(f"→ sending observations to AMP at {amp_url}")

    tracker = WolfpackObserver(
        base_url=amp_url,
        api_key=amp_key,
        deployment=MeshIdentity(
            os.environ.get("WOLFPACK_ENVIRONMENT_ID", "development"),
            os.environ.get("WOLFPACK_ENVIRONMENT_SLUG", "development"),
            os.environ.get("WOLFPACK_REGISTRATION_ID", "weather-agent"),
            "weather-agent",
            "1.0.0",
            trigger_type="interactive",
        ),
    )

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
        backstory="A wolfpack agent with a weather tool, observed by the AMP control plane.",
        tools=[get_weather],
        telemetry=tracker,
    )
    output = agent.run("What is the weather in Lisbon?")
    print("status:", "ok" if not output.failed else output.error)
    print("answer:", output.content)
    print("tokens:", output.usage)

    tracker.flush()
    print("run_id:", output.run_id)
    print("→ end-to-end trace sent. Open the Control Plane UI to inspect it.")
    print(
        "  (If the AMP backend is not running, the observer buffered the events; "
        "start it with the control-plane ./run.sh and re-run.)"
    )


if __name__ == "__main__":
    main()
