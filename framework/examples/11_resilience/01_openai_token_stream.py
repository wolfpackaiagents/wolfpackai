"""Stream OpenAI response chunks without repeating the final answer.

Set OPENAI_API_KEY and optionally WOLFPACK_MODEL before running:

    uv run python examples/11_resilience/01_openai_token_stream.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wolfpack import Agent, RunEventType, get_model


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY to run this OpenAI streaming example.")

    try:
        model = get_model(f"openai:{os.environ.get('WOLFPACK_MODEL', 'gpt-4o-mini')}")
    except Exception:
        raise SystemExit(
            f"Could not create model openai:{os.environ.get('WOLFPACK_MODEL', 'gpt-4o-mini')}. "
            "Verify that OPENAI_API_KEY is valid."
        )

    agent = Agent(
        name="OpenAI Streaming",
        model=model,
        role="A concise assistant",
        goal="Demonstrate streaming token output from the OpenAI provider.",
        backstory="A wolfpack agent configured to stream responses token by token from OpenAI.",
        system="Answer concisely.",
    )

    print("Response: ", end="", flush=True)
    for event in agent.run("Explain why streaming improves chat UX in one sentence.", stream=True):
        if event.event_type == RunEventType.RUN_CONTENT and event.content:
            print(event.content, end="", flush=True)
        elif event.event_type == RunEventType.RUN_FAILED:
            raise RuntimeError(event.error or "Streaming run failed.")
    print()


if __name__ == "__main__":
    main()
