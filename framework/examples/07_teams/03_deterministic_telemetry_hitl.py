"""Deterministic Agent telemetry with a human approval and AMP observation events.

This example has no model-provider dependency. It demonstrates tool execution,
HITL approval, and event observation through the WolfpackObserver.

    WOLFPACK_AMP_URL=http://127.0.0.1:8200 WOLFPACK_AMP_API_KEY=pk-wp-dev:dev-secret \
      uv run python examples/07_teams/03_deterministic_telemetry_hitl.py
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from wolfpack import Agent, MeshIdentity, tool
from wolfpack.models.base import BaseModel, ModelResponse
from wolfpack.models.message import Message, ToolCall
from wolfpack.observer.client import WolfpackObserver
from wolfpack.run.approval_store import AmpApprovalStore


@tool
def lookup_incident(incident_id: str) -> str:
    """Returns the affected service for a known incident."""
    assert incident_id == "INC-42"
    return "Affected service: payments-api"


@tool(requires_confirmation=True)
def deploy_rollback(service: str, version: str) -> str:
    """Rolls a service back after an operator approves the deployment."""
    assert (service, version) == ("payments-api", "2026.08.24.1")
    return "payments-api rolled back to 2026.08.24.1"


class ResearchModel(BaseModel):
    provider = "deterministic"
    model_id = "incident-research-v1"

    def invoke(self, messages, tools=None) -> ModelResponse:
        if any(message.get("role") == "tool" for message in messages):
            return ModelResponse(Message(role="assistant", content="payments-api is affected."), usage={})
        return ModelResponse(
            Message(
                role="assistant",
                content=None,
                tool_calls=[ToolCall(id="lookup-1", name="lookup_incident", arguments='{"incident_id": "INC-42"}')],
            ),
            usage={},
        )


class RemediationModel(BaseModel):
    provider = "deterministic"
    model_id = "incident-remediation-v1"

    def invoke(self, messages, tools=None) -> ModelResponse:
        if any("approved by human" in str(message.get("content", "")) for message in messages):
            return ModelResponse(Message(role="assistant", content="Rollback completed after approval."), usage={})
        return ModelResponse(
            Message(
                role="assistant",
                content=None,
                tool_calls=[
                    ToolCall(
                        id="rollback-1",
                        name="deploy_rollback",
                        arguments='{"service": "payments-api", "version": "2026.08.24.1"}',
                    )
                ],
            ),
            usage={},
        )


@dataclass
class DemoResult:
    observer: WolfpackObserver
    remediation: object
    research_run_id: str
    remediation_run_id: str


def run_demo() -> DemoResult:
    """Runs the complete, deterministic telemetry flow and leaves events buffered."""
    observer = WolfpackObserver(
        base_url=os.environ.get("WOLFPACK_AMP_URL", "http://127.0.0.1:1"),
        api_key=os.environ.get("WOLFPACK_AMP_API_KEY", "pk-wp-dev:dev-secret"),
        max_batch=100,
        redact_pii=False,
        deployment=MeshIdentity(
            os.environ.get("WOLFPACK_ENVIRONMENT_ID", "development"),
            os.environ.get("WOLFPACK_ENVIRONMENT_SLUG", "development"),
            os.environ.get("WOLFPACK_REGISTRATION_ID", "support-orchestrator"),
            "support-orchestrator",
            "1.0.0",
        ),
    )
    observer.heartbeat(instance_id=os.environ.get("WOLFPACK_INSTANCE_ID", "deterministic-hitl-local"), metadata={"example": "deterministic-hitl"})
    approvals = AmpApprovalStore(observer=observer)
    research = Agent(
        "incident-research",
        ResearchModel(),
        role="Incident research specialist",
        goal="Investigate incidents by looking up relevant data using tools.",
        backstory="A deterministic wolfpack agent that researches incidents to identify affected services.",
        tools=[lookup_incident],
        telemetry=observer,
    )
    remediation = Agent(
        "incident-remediation",
        RemediationModel(),
        role="Incident remediation specialist",
        goal="Deploy rollbacks after receiving human approval.",
        backstory="A deterministic wolfpack agent that remediates incidents, always requiring operator approval before rolling back.",
        tools=[deploy_rollback],
        telemetry=observer,
        approval_store=approvals,
    )
    research.run_id = "run_incident_research"
    remediation.run_id = "run_incident_remediation"

    # Research phase
    research_result = research.run("Investigate INC-42")
    observer.record_interaction(
        "incident-research", "incident-remediation", "handoff",
        trace_id=research.run_id,
        operation="team.handoff",
        source_display_name="Incident Research",
        target_display_name="Incident Remediation",
    )

    # Remediation phase — requires approval
    result = remediation.run("Roll back the affected service.")
    requirement = result.requirements[0]
    approvals.resolve(result.run_id, requirement.approval_id, "approve")
    completed = remediation.continue_run(result.run_id)

    return DemoResult(observer, completed, research.run_id, remediation.run_id)


def main() -> None:
    result = run_demo()
    print(result.remediation.content)
    print(f"research trace: {result.research_run_id}")
    print(f"remediation trace: {result.remediation_run_id}")
    result.observer.flush()


if __name__ == "__main__":
    main()