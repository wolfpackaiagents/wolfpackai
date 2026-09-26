"""Result structures returned by AgentForce executions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from .spec import TaskResult


@dataclass
class PoolSummary:
    """Consolidated metrics for a specific executor pool."""

    pool: str
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_duration_ms: float = 0.0
    avg_task_duration_ms: float = 0.0
    total_tokens: int = 0
    total_cost: float = 0.0
    active_workers: int = 0

    def compute_averages(self) -> None:
        if self.completed_tasks > 0:
            self.avg_task_duration_ms = self.total_duration_ms / self.completed_tasks


@dataclass
class AgentForceResult:
    """The complete result of an AgentForce batch execution."""

    mission: str
    status: str = "completed"  # "completed", "failed", "partial"
    synthesis: str = ""
    tasks: List[TaskResult] = field(default_factory=list)
    pool_summaries: Dict[str, PoolSummary] = field(default_factory=dict)
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    duration_ms: float = 0.0
    prediction: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> Dict[str, Any]:
        return {
            "mission": self.mission,
            "status": self.status,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "duration_ms": round(self.duration_ms, 2),
            "pool_breakdown": {
                p: {
                    "completed": s.completed_tasks,
                    "failed": s.failed_tasks,
                    "avg_ms": round(s.avg_task_duration_ms, 1),
                }
                for p, s in self.pool_summaries.items()
            },
        }
