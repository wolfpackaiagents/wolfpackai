"""Persist an Agent conversation locally across turns.

    uv run python examples/06_workflows/02_session.py
"""

from wolfpack import Agent, SQLiteSessionStore, get_model_from_env


def main() -> None:
    try:
        model = get_model_from_env()
    except Exception:
        raise SystemExit(
            "No API key found (OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, "
            "or OLLAMA_BASE_URL). Set one and re-run."
        )
    agent = Agent(
        name="Session assistant",
        model=model,
        role="A helpful assistant that remembers context across turns",
        goal="Remember user preferences and recall them when asked.",
        backstory="A wolfpack agent using session persistence to keep conversation state across runs.",
        session_id="session-example",
        session_store=SQLiteSessionStore(".wolfpack-example-sessions.db"),
    )
    agent.run("Remember that my favorite color is orange. Reply only with confirmation.")
    result = agent.run("What is my favorite color? Reply only with the color.")
    print(result.content)


if __name__ == "__main__":
    main()
