"""Two wolfpack agents coordinated by a leader model via delegation.

The leader decides which specialist to call and when.

    uv run python examples/07_teams/01_coordinate.py
"""

from wolfpack import Agent, Team, get_model_from_env


def main() -> None:
    try:
        model = get_model_from_env()
    except Exception:
        raise SystemExit(
            "No API key found (OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, "
            "or OLLAMA_BASE_URL). Set one and re-run."
        )
    researcher = Agent(
        name="Researcher",
        model=model,
        role="Research specialist",
        goal="Find and state one verified fact about the requested topic.",
        backstory="A wolfpack agent that researches topics and provides concise facts.",
        description="State one verified fact about octopuses.",
        system="State one verified fact about octopuses.",
    )
    editor = Agent(
        name="Editor",
        model=model,
        role="Editor",
        goal="Polish research findings into a single clear sentence.",
        backstory="A wolfpack agent that edits and condenses content into concise sentences.",
        description="Turn the supplied research into one concise sentence.",
        system="Turn the supplied research into one concise sentence.",
    )
    team = Team("ocean-team", [researcher, editor], leader_model=model)
    result = team.run("Give a concise fact about octopuses.")
    print(result.content)


if __name__ == "__main__":
    main()