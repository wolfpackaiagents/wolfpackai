"""03_stream_events.py - Observe the run event stream with `run(..., stream=True)`.

Instead of waiting for a single `RunOutput`, streaming lets you iterate over events
as the run progresses. Each event exposes an `event_type` string (see
wolfpack/agent/events.py) and type-specific payload fields:

    RunStarted    -> run_input
    RunContent    -> content
    RunTool       -> tool_name, tool_arguments, result, error, duration_ms
    RunStep       -> tool_calls / messages
    RunCompleted  -> metrics (holds the aggregate usage)

This example prints each event, shows the interesting payloads, and finally
collects the finished `RunOutput` to prove both styles work together.

Usage:
    uv run python examples/01_basic/03_stream_events.py
"""

import sys
from pathlib import Path

# Make wolfpack importable when this script lives inside the `examples/` folder.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wolfpack import Agent, get_model_from_env


def main() -> None:
    try:
        model = get_model_from_env()
    except Exception:
        raise SystemExit(
            "No API key found (OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, "
            "or OLLAMA_BASE_URL). Set one and re-run."
        )
    agent = Agent(
        name="Stream Explorer",
        model=model,
        role="A concise explainer",
        goal="Answer the question in a couple of sentences.",
        backstory="A wolfpack agent used to observe its own execution stream.",
    )

    prompt = "In one or two sentences, what is an LLM (large language model)?"

    print("=" * 60)
    print("WOLFPACK STREAMING EVENTS")
    print("=" * 60)
    print(f"Agent id : {agent.id}")
    print(f"Prompt   : {prompt}")
    print("-" * 60)

    final_output = None
    usage = {}

    # Iterate the run's event stream in real time.
    for ev in agent.run(prompt, stream=True):
        print(f"\n>>> event_type = {ev.event_type}")

        if ev.event_type == "RunStarted":
            print(f"    run_input: {ev.run_input}")

        elif ev.event_type == "RunContent":
            if ev.content:
                print(f"    content: {ev.content!r}")

        elif ev.event_type == "RunTool":
            print(f"    tool_name : {ev.tool_name}")
            print(f"    arguments : {ev.tool_arguments}")
            print(f"    result    : {ev.result}")
            if ev.error:
                print(f"    error     : {ev.error}")
            if ev.duration_ms is not None:
                print(f"    duration  : {ev.duration_ms:.1f} ms")

        elif ev.event_type == "RunStep":
            calls = ev.tool_calls or []
            print(f"    tool_calls count: {len(calls)}")

        elif ev.event_type == "RunCompleted":
            # The final event carries the aggregate metrics (usage) and the raw output.
            usage = ev.metrics.get("usage", {})
            print(f"    metrics['usage']: {usage}")

        elif ev.event_type == "RunFailed":
            print(f"    error: {ev.error}")

    # The stream already gave us everything, but re-wrap a RunOutput-equivalent
    # for clarity: the last content + usage. (A synchronous agent.run() would
    # return a RunOutput with the same fields.)
    print("\n" + "=" * 60)
    print("COLLECTED RESULT")
    print("=" * 60)
    print("usage      :", usage)

    # Demonstrate the direct (non-streaming) RunOutput shape for comparison.
    print("\n----- direct run() for comparison -----")
    direct = agent.run(prompt)
    print("failed     :", direct.failed)
    print("error      :", direct.error)
    print("content    :", direct.content)
    print("usage      :", direct.usage)
    print("tool_calls :", direct.tool_calls or "none")
    print("=" * 60)


if __name__ == "__main__":
    main()