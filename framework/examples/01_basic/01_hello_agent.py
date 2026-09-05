"""01_hello_agent.py - Minimal hello-world agent built with wolfpack.

This example shows the smallest possible end-to-end program: build a model from
the environment, wrap it in an Agent with no tools, ask a simple question, and
print both the final answer and the token usage.

The model provider is picked automatically by `get_model_from_env()`, which reads
your environment keys. It prefers OPENAI_API_KEY, then ANTHROPIC_API_KEY, then
GOOGLE_API_KEY, then OLLAMA_BASE_URL (see wolfpack/models/utils.py).

Usage:
    uv run python examples/01_basic/01_hello_agent.py
    uv run python examples/01_basic/01_hello_agent.py "Who founded Wolfram Research?"
"""

import sys
from pathlib import Path

# Make wolfpack importable when this script lives inside the `examples/` folder.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wolfpack import Agent, get_model_from_env


def main() -> None:
    # Optional custom prompt passed as a CLI argument (defaults to a greeting).
    prompt = " ".join(sys.argv[1:]) or "Say hello in a friendly one-liner and name the AI framework you run on."

    # 1) Build a model from the available environment key (auto-selected provider).
    try:
        model = get_model_from_env()
    except Exception:
        raise SystemExit(
            "No API key found (OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, "
            "or OLLAMA_BASE_URL). Set one and re-run."
        )

    # 2) Wrap it in an Agent. Without `tools`, the agent replies directly.
    agent = Agent(
        name="Hello Agent",
        model=model,
        role="A friendly assistant",
        goal="Answer the user's message clearly and concisely.",
        backstory="A brand-new wolfpack agent, eager to prove it can hold a conversation.",
    )

    print("=" * 60)
    print("WOLFPACK HELLO AGENT")
    print("=" * 60)
    print(f"Model provider      : {getattr(model, 'provider', 'n/a')}")
    print(f"Model id           : {getattr(model, 'id', model)}")
    print(f"Agent name         : {agent.name}")
    print(f"Agent id           : {agent.id}")
    print("-" * 60)
    print(f"Prompt             : {prompt}")
    print("-" * 60)

    # 3) Run the agent (synchronous) and inspect the RunOutput.
    result = agent.run(prompt)

    print("\n----- FINAL ANSWER -----")
    if result.failed:
        print(f"Oops, the run failed: {result.error}")
    else:
        print(result.content)

    print("\n----- TOKEN USAGE -----")
    print(result.usage or "no usage reported")

    print("\n----- MESSAGE COUNT -----")
    print(f"{len(result.messages)} messages exchanged.\n")


if __name__ == "__main__":
    main()