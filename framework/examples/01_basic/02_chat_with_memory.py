"""02_chat_with_memory.py - Multi-turn conversation with SessionMemory.

This example demonstrates how to keep context across several `agent.run()` calls
using the `SessionMemory` store. Each user message is added to the session,
the agent replies, and the assistant reply is also appended, so the next turn can
see the full conversation history.

`run(..., messages=...)` lets you pass the accumulated history as a list of message
dicts, which the agent turns back into `Message` objects internally.

Usage:
    uv run python examples/01_basic/02_chat_with_memory.py
"""

import sys
from pathlib import Path

# Make wolfpack importable when this script lives inside the `examples/` folder.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wolfpack import Agent, get_model_from_env
from wolfpack.memory.memory import SessionMemory


def main() -> None:
    # 1) Set up the conversational memory (a short-term in-memory session store).
    session = SessionMemory(session_id="example-chat")

    # 2) Build the agent once; it keeps acting on the evolving conversation.
    try:
        model = get_model_from_env()
    except Exception:
        raise SystemExit(
            "No API key found (OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, "
            "or OLLAMA_BASE_URL). Set one and re-run."
        )
    agent = Agent(
        name="Chat Buddy",
        model=model,
        role="A patient conversation partner",
        goal="Help the user explore a topic step by step.",
        backstory="A wolfpack agent designed to hold a natural multi-turn chat.",
    )

    print("=" * 60)
    print("WOLFPACK CHAT WITH SESSION MEMORY")
    print("=" * 60)
    print(f"Session id : {session.session_id}")
    print("-" * 60)

    # 3) Send a small scripted conversation of 2-3 turns. Each turn re-uses the
    #    accumulated session history so the agent remembers what was said.
    turns = [
        "My name is Alex and I'm learning about AI agents. Remember my name.",
        "What is my name, and what did we talk about so far?",
        "Great. Suggest one fun project I could build to practice agents.",
    ]

    for turn, text in enumerate(turns, start=1):
        # Append the incoming user turn to the session.
        session.add_user_message(text)

        # Feed the FULL history (dicts) into the agent for this turn.
        result = agent.run(messages=session.get_messages())

        print(f"\n[[ TURN {turn} ]]")
        print(f"USER   : {text}")

        if result.failed:
            print(f"ASSISTANT (error): {result.error}")
            continue

        # Remember the assistant reply for the next turn, then print it.
        session.add_assistant_message(result.content)
        print(f"ASSISTANT: {result.content}")

    # 4) Print a clean transcript of the final session state.
    print("\n" + "=" * 60)
    print("FINAL CONVERSATION TRANSCRIPT")
    print("=" * 60)
    for m in session.get_messages():
        role = m.get("role", "?")
        content = m.get("content", "")
        print(f"[{role}] {content}")
    print("=" * 60)


if __name__ == "__main__":
    main()