"""AgentForce: Mass parallel multi-agent execution with pools and progress streaming.

Demonstrates:
- Coordinator Agent analyzing the mission
- Specialized Executor Pools running in parallel via ThreadPoolExecutor
- Live progress bar events (ForceProgressEvent) with ETA calculation
- AIPrediction forecasting duration, cost, and bottlenecks
- Final synthesis of batch results

Run with:
    uv run python examples/24_force/01_basic_force.py
"""

from __future__ import annotations

import time
from typing import Any, List
from wolfpack import Agent
from wolfpack.force import AgentForce
from wolfpack.models.base import BaseModel, ModelResponse
from wolfpack.models.message import Message


class DeterministicSimulator(BaseModel):
    """Simulates realistic agent work with slight processing latency."""

    def __init__(self, prefix: str, latency_s: float = 0.05) -> None:
        self.provider = "simulator"
        self.model_id = "deterministic-v1"
        self.prefix = prefix
        self.latency_s = latency_s

    def invoke(self, messages: List[Any], tools: Any = None) -> ModelResponse:
        time.sleep(self.latency_s)
        user_msg = next((m.get("content") for m in reversed(messages) if m.get("role") == "user"), "")
        return ModelResponse(
            message=Message(role="assistant", content=f"{self.prefix} {user_msg}"),
            usage={"input_tokens": 40, "output_tokens": 25},
        )


def main() -> None:
    print("=== Wolfpack AI: AgentForce Mass Execution ===\n")

    # 1. Create Coordinator Agent
    coordinator = Agent(
        name="OperationsManager",
        model=DeterministicSimulator("[Operations Synthesis]", latency_s=0.02),
        system="Consolidate and coordinate multi-pool execution batches.",
    )

    # 2. Create Specialized Pool Executors
    triage_worker = Agent(
        name="TriageWorker-1",
        model=DeterministicSimulator("[Triage Validated]", latency_s=0.04),
    )
    billing_worker = Agent(
        name="BillingWorker-1",
        model=DeterministicSimulator("[Billing Processed]", latency_s=0.06),
    )

    # 3. Assemble AgentForce
    force = AgentForce(coordinator=coordinator, max_workers=6, name="CustomerOpsForce")

    # Pool 1: Triage (high concurrency)
    force.add_executor(name="triage-a", agent=triage_worker, pool="triage", max_concurrency=4)

    # Pool 2: Billing (restricted concurrency)
    force.add_executor(name="billing-a", agent=billing_worker, pool="billing", max_concurrency=2)

    # 4. Batch of incoming tickets to execute in mass
    tickets = [
        {"id": "tkt_101", "prompt": "Customer cannot access invoice PDF", "pool": "billing"},
        {"id": "tkt_102", "prompt": "Verify account email address", "pool": "triage"},
        {"id": "tkt_103", "prompt": "Refund request for double charge", "pool": "billing"},
        {"id": "tkt_104", "prompt": "Spam report on user comment", "pool": "triage"},
        {"id": "tkt_105", "prompt": "Subscription downgrade request", "pool": "billing"},
        {"id": "tkt_106", "prompt": "Password reset inquiry", "pool": "triage"},
    ]

    print(f"Dispatched {len(tickets)} tasks across pools: triage, billing.\n")
    print("--- Live Progress Stream ---")

    final_result = None
    for event in force.run(
        mission="Process urgent customer support queue",
        data=tickets,
        stream=True,
    ):
        if hasattr(event, "event_type"):
            if event.event_type == "ForceStarted":
                print(f"[START] Force '{event.force_name}' started with {event.total_tasks} tasks.")
            elif event.event_type == "ForcePrediction":
                print(
                    f"[AIPrediction] Estimated Duration: {event.predicted_duration_ms:.0f}ms | "
                    f"Est Cost: ${event.predicted_cost:.4f} | Confidence: {event.confidence * 100:.0f}%"
                )
            elif event.event_type == "ForceProgress":
                bar = "█" * int(event.percent / 10) + "░" * (10 - int(event.percent / 10))
                print(
                    f"  [{bar}] {event.percent:5.1f}% ({event.completed}/{event.total}) "
                    f"ETA: {event.eta_seconds:.1f}s | Active: {event.active_pools}"
                )
        else:
            final_result = event

    print("\n--- Final Aggregated Result ---")
    if final_result:
        print(f"Status: {final_result.status.upper()}")
        print(f"Completed: {final_result.completed_tasks}/{final_result.total_tasks} in {final_result.duration_ms:.1f}ms")
        for pool_name, summary in final_result.pool_summaries.items():
            print(f"  • Pool '{pool_name}': {summary.completed_tasks} tasks (avg {summary.avg_task_duration_ms:.1f}ms)")
        print(f"\nExecutive Synthesis:\n{final_result.synthesis}")


if __name__ == "__main__":
    main()
