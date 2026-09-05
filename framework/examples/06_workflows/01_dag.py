"""Run a deterministic workflow with dependencies, routing and retry.

    uv run python examples/06_workflows/01_dag.py
"""

from wolfpack import Workflow


def main() -> None:
    attempts = 0

    def fetch(state):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("temporary source outage")
        return state["source"].upper()

    workflow = Workflow("daily-report")
    workflow.add_step("fetch", fetch, retries=1)
    workflow.add_step("format", lambda state: f"Report: {state['fetch']}", depends_on=["fetch"])
    workflow.add_step("notify", lambda state: "sent", depends_on=["format"], condition=lambda state: state["send"])

    result = workflow.run({"source": "sales completed", "send": True})
    print(result.outputs)


if __name__ == "__main__":
    main()
