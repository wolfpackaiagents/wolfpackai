import importlib.util
import sys
from pathlib import Path


def _load_example():
    path = Path(__file__).parents[1] / "examples/07_teams/03_deterministic_telemetry_hitl.py"
    spec = importlib.util.spec_from_file_location("deterministic_team_telemetry_hitl", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_deterministic_team_example_emits_correlated_mesh_tool_and_approval_telemetry():
    example = _load_example()

    result = example.run_demo()
    events = result.observer._buffer
    bodies = [event["body"] for event in events]

    interactions = [event["body"] for event in events if event["type"] == "mesh-interaction"]
    assert len(interactions) == 1
    assert interactions[0]["metadata"]["mesh_interaction"]["interaction_type"] == "handoff"
    assert interactions[0]["trace_id"] == result.research_run_id

    tool_events = [event["body"] for event in events if event["type"] == "observation-end" and event["body"].get("type") == "TOOL"]
    lookup = next(body for body in tool_events if body["name"] == "lookup_incident")
    rollback = next(body for body in tool_events if body["name"] == "deploy_rollback")
    assert lookup["input"] == {"incident_id": "INC-42"}
    assert lookup["output"] == "Affected service: payments-api"
    assert rollback["input"] == {"service": "payments-api", "version": "2026.08.24.1"}
    assert rollback["output"] == "awaiting approval"
    assert rollback["trace_id"] == result.remediation_run_id

    approvals = [body for body in bodies if body.get("name") == "approval.deploy_rollback"]
    assert [body["metadata"]["status"] for body in approvals] == ["pending", "approved"]
    assert {body["trace_id"] for body in approvals} == {result.remediation_run_id}
    assert result.remediation.content == "Rollback completed after approval."