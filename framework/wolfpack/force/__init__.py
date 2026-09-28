"""AgentForce module for mass parallel multi-agent execution."""

from __future__ import annotations

from .acquisition import DataSource, normalize_to_tasks
from .dispatcher import ForceDispatcher
from .events import (
    ForceCompletedEvent,
    ForceEvent,
    ForcePredictionEvent,
    ForceProgressEvent,
    ForceStartedEvent,
    ForceTaskCompletedEvent,
)
from .force import AgentForce
from .prediction import AIPredictionEngine
from .result import AgentForceResult, PoolSummary
from .spec import ExecutorSpec, PoolConfig, TaskItem, TaskResult

__all__ = [
    "AgentForce",
    "ExecutorSpec",
    "PoolConfig",
    "TaskItem",
    "TaskResult",
    "DataSource",
    "normalize_to_tasks",
    "ForceDispatcher",
    "AIPredictionEngine",
    "AgentForceResult",
    "PoolSummary",
    "ForceEvent",
    "ForceStartedEvent",
    "ForcePredictionEvent",
    "ForceProgressEvent",
    "ForceTaskCompletedEvent",
    "ForceCompletedEvent",
]
