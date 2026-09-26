"""Events emitted during AgentForce planning and parallel execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class ForceEvent:
    """Base event for AgentForce streaming."""

    force_name: str
    event_type: str = "ForceEvent"
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "force_name": self.force_name,
            "timestamp": self.timestamp,
        }


@dataclass
class ForceStartedEvent(ForceEvent):
    """Emitted when AgentForce begins processing a batch of tasks."""

    event_type: str = "ForceStarted"
    total_tasks: int = 0
    mission: str = ""
    pools: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "total_tasks": self.total_tasks,
            "mission": self.mission,
            "pools": self.pools,
        })
        return d


@dataclass
class ForcePredictionEvent(ForceEvent):
    """Emitted when AIPrediction calculates initial execution forecasts."""

    event_type: str = "ForcePrediction"
    predicted_duration_ms: float = 0.0
    predicted_cost: float = 0.0
    predicted_tokens: int = 0
    predicted_success_rate: float = 1.0
    bottlenecks: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.95

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "predicted_duration_ms": self.predicted_duration_ms,
            "predicted_cost": self.predicted_cost,
            "predicted_tokens": self.predicted_tokens,
            "predicted_success_rate": self.predicted_success_rate,
            "bottlenecks": self.bottlenecks,
            "confidence": self.confidence,
        })
        return d


@dataclass
class ForceProgressEvent(ForceEvent):
    """Emitted on each completed task to update progress bars in real-time."""

    event_type: str = "ForceProgress"
    completed: int = 0
    total: int = 0
    percent: float = 0.0
    active_pools: Dict[str, int] = field(default_factory=dict)
    eta_seconds: float = 0.0
    latest_task_id: Optional[str] = None
    latest_pool: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "completed": self.completed,
            "total": self.total,
            "percent": round(self.percent, 1),
            "active_pools": self.active_pools,
            "eta_seconds": round(self.eta_seconds, 1),
            "latest_task_id": self.latest_task_id,
            "latest_pool": self.latest_pool,
        })
        return d


@dataclass
class ForceTaskCompletedEvent(ForceEvent):
    """Emitted when an individual task finishes execution."""

    event_type: str = "ForceTaskCompleted"
    task_id: str = ""
    pool: str = ""
    executor_name: str = ""
    status: str = "completed"
    duration_ms: float = 0.0
    output_preview: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_id": self.task_id,
            "pool": self.pool,
            "executor_name": self.executor_name,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 2),
            "output_preview": self.output_preview,
            "error": self.error,
        })
        return d


@dataclass
class ForceCompletedEvent(ForceEvent):
    """Emitted when the entire batch and synthesis are complete."""

    event_type: str = "ForceCompleted"
    completed: int = 0
    failed: int = 0
    total_duration_ms: float = 0.0
    synthesis_preview: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "completed": self.completed,
            "failed": self.failed,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "synthesis_preview": self.synthesis_preview,
            "metrics": self.metrics,
        })
        return d
