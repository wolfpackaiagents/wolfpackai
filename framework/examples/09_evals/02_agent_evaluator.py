"""Evaluate a real Wolfpack agent with a deterministic quality check.

    uv run python examples/09_evals/02_agent_evaluator.py
"""

from wolfpack import Agent, get_model_from_env
from wolfpack.evals import CallableEvaluator, EvalCase, EvalRunner


def main() -> None:
    try:
        model = get_model_from_env()
    except Exception:
        raise SystemExit(
            "No API key found (OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, "
            "or OLLAMA_BASE_URL). Set one and re-run."
        )
    agent = Agent(
        name="Capital expert",
        model=model,
        role="A geography expert",
        goal="Answer with only the capital city of the requested country.",
        backstory="A wolfpack agent trained to identify capital cities precisely.",
        system="Reply with only the capital city.",
    )
    evaluator = CallableEvaluator("exact_match", lambda case, output: output.strip().lower() == case.expected.lower())
    runner = EvalRunner(lambda prompt: agent.run(prompt).content or "", [evaluator])
    report = runner.run([EvalCase(input="What is the capital of France?", expected="Paris")])
    print(report.results[0].output)
    print(report.averages)


if __name__ == "__main__":
    main()
