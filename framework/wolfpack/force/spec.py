"""Specifications and definitions for AgentForce executors, pools, and tasks."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExecutorSpec:
    """Specification of an executor Agent within a dedicated pool."""

    name: str
    agent: Any  # Agent instance
    pool: str
    max_concurrency: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    policy: Optional[Any] = None  # DataAccessPolicy
    knowledge: Optional[Any] = None  # Knowledge or OKFBundle
    toolkits: Optional[List[Any]] = None  # List of Toolkits

    def __post_init__(self) -> None:
        if self.max_concurrency < 1:
            self.max_concurrency = 1


@dataclass
class PoolConfig:
    """Runtime configuration and executor collection for a named pool."""

    name: str
    executors: List[ExecutorSpec] = field(default_factory=list)
    max_concurrency: int = 5

    def add_executor(self, executor: ExecutorSpec) -> None:
        self.executors.append(executor)


@dataclass
class TaskItem:
    """Individual unit of work to be scheduled and executed."""

    id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:12]}")
    input: Any = None
    description: str = ""
    pool: str = "default"
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0


@dataclass
class TaskResult:
    """Result of an executed TaskItem."""

    task_id: str
    pool: str
    executor_name: str
    status: str  # "completed", "failed", "paused"
    output: Any = None
    error: Optional[str] = None
    description: str = ""
    duration_ms: float = 0.0
    trace_id: Optional[str] = None
    tokens_used: int = 0
    estimated_cost: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
