import importlib.util
import sys
from pathlib import Path


def _load_example():
    path = Path(__file__).parents[1] / "examples/07_teams/02_mesh_telemetry.py"
    spec = importlib.util.spec_from_file_location("mesh_telemetry_example", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeObserver:
    def __init__(self):
        self.interactions = []
        self.ended = None

    def start_trace(self, name):
        assert name == "triage_run"
        return {"id": "trace_1"}

    def record_interaction(self, source, target, interaction_type, **kwargs):
        self.interactions.append((source, target, interaction_type, kwargs))

    def end_trace(self, trace, **kwargs):
        self.ended = (trace, kwargs)


def test_mesh_telemetry_example_emits_deterministic_team_interactions():
    example = _load_example()
    observer = FakeObserver()

    result = example.run_demo(observer, "Summarize the incident.")

    assert result == "research: Summarize the incident.\nwriter: Incident summary prepared."
    assert [(source, target, interaction_type) for source, target, interaction_type, _ in observer.interactions] == [
        ("triage", "research", "delegation"),
        ("triage", "writer", "delegation"),
    ]
    assert observer.ended == ({"id": "trace_1"}, {"input": {"message": "Summarize the incident."}, "output": result})
