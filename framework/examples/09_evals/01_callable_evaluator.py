"""Evaluate a deterministic target with a callable evaluator.

    uv run python examples/09_evals/01_callable_evaluator.py
"""

from wolfpack.evals import CallableEvaluator, EvalCase, EvalRunner


def main() -> None:
    exact_match = CallableEvaluator("exact_match", lambda case, output: output == case.expected)
    runner = EvalRunner(lambda text: text.upper(), [exact_match])
    report = runner.run(
        [
            EvalCase(input="wolf", expected="WOLF"),
            EvalCase(input="pack", expected="PACK"),
        ]
    )

    for result in report.results:
        print(f"{result.case.input}: {result.output} ({result.scores[0].value})")
    print("averages:", report.averages)


if __name__ == "__main__":
    main()
