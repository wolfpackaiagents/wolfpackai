"""Emit deterministic Mesh team interactions without an LLM provider.

    WOLFPACK_AMP_URL=http://127.0.0.1:8000 WOLFPACK_AMP_API_KEY=pk-wp-dev:dev-secret \
      uv run python examples/07_teams/02_mesh_telemetry.py
"""

import os

from wolfpack import MeshIdentity
from wolfpack.observer.client import WolfpackObserver


def run_demo(observer: WolfpackObserver, message: str) -> str:
    """Simulate two deterministic specialists and record their Mesh handoffs."""
    trace = observer.start_trace("triage_run")
    research = f"research: {message}"
    observer.record_interaction(
        "triage", "research", "delegation", trace_id=trace["id"], operation="team.delegate",
        source_display_name="Triage", target_display_name="Research", metadata={"team": "triage"},
    )
    writer = "writer: Incident summary prepared."
    observer.record_interaction(
        "triage", "writer", "delegation", trace_id=trace["id"], operation="team.delegate",
        source_display_name="Triage", target_display_name="Writer", metadata={"team": "triage"},
    )
    result = f"{research}\n{writer}"
    observer.end_trace(trace, input={"message": message}, output=result)
    return result


def main() -> None:
    observer = WolfpackObserver(
        os.environ.get("WOLFPACK_AMP_URL", "http://127.0.0.1:8000"),
        api_key=os.environ.get("WOLFPACK_AMP_API_KEY"),
        deployment=MeshIdentity(
            os.environ.get("WOLFPACK_ENVIRONMENT_ID", "development"),
            os.environ.get("WOLFPACK_ENVIRONMENT_SLUG", "development"),
            os.environ.get("WOLFPACK_REGISTRATION_ID", "mesh-triage"),
            "mesh-triage",
            "1.0.0",
            trigger_type="interactive",
        ),
    )
    print(run_demo(observer, "Summarize the incident."))
    observer.flush()


if __name__ == "__main__":
    main()
