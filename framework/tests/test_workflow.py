import pytest

from wolfpack.workflow import Workflow, WorkflowError


def test_workflow_runs_steps_in_dependency_order():
    workflow = Workflow("report")
    workflow.add_step("load", lambda state: state["value"] + 1)
    workflow.add_step("format", lambda state: f"value={state['load']}", depends_on=["load"])

    result = workflow.run({"value": 2})

    assert result.outputs == {"load": 3, "format": "value=3"}


def test_workflow_retries_failed_step():
    attempts = []

    def unstable(state):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("temporary")
        return "ok"

    result = Workflow("retry").add_step("unstable", unstable, retries=1).run()

    assert result.outputs["unstable"] == "ok"
    assert len(attempts) == 2


def test_workflow_skips_conditional_step():
    result = Workflow("conditional").add_step(
        "optional", lambda state: "ran", condition=lambda state: state["enabled"]
    ).run({"enabled": False})

    assert result.outputs == {}
    assert result.skipped == ["optional"]


def test_workflow_rejects_missing_dependency():
    workflow = Workflow("invalid").add_step("next", lambda state: None, depends_on=["missing"])

    with pytest.raises(WorkflowError, match="missing dependencies"):
        workflow.run()
