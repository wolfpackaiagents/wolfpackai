"""Execution event taxonomy (agno / vercel agent-v1 style).

The Agent's `run()`/`arun()` can return an iterator of streaming events that lets you
observe each step, tool call, content and termination. Some events are also turned
into OTel spans by the telemetry connector.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class RunEventType:
    RUN_STARTED = "RunStarted"
    RUN_CONTENT = "RunContent"
    RUN_STEP = "RunStep"
    RUN_TOOL = "RunTool"
    RUN_ERROR = "RunError"
    RUN_COMPLETED = "RunCompleted"
    RUN_FAILED = "RunFailed"
    RUN_CANCELLED = "RunCancelled"
    RUN_HOOK = "RunHook"


def event_type_to_str(val: str) -> str:
    return val


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class BaseRunEvent:
    event_type: str
    run_id: Optional[str] = None
    agent_id: Optional[str] = None
    name: Optional[str] = None
    timestamp: str = field(default_factory=_now)
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.run_id is None:
            self.run_id = uuid.uuid4().hex

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["event_type"] = self.event_type
        return d


@dataclass
class RunStartedEvent(BaseRunEvent):
    event_type: str = RunEventType.RUN_STARTED
    run_input: Optional[Any] = None


@dataclass
class RunContentEvent(BaseRunEvent):
    event_type: str = RunEventType.RUN_CONTENT
    content: Optional[str] = None
    reasoning_content: Optional[str] = None
    response_id: Optional[str] = None


@dataclass
class RunStepEvent(BaseRunEvent):
    event_type: str = RunEventType.RUN_STEP
    messages: Optional[List[Any]] = None
    tool_calls: Optional[List[Any]] = None
    result: Optional[Any] = None


@dataclass
class RunToolEvent(BaseRunEvent):
    event_type: str = RunEventType.RUN_TOOL
    tool_name: Optional[str] = None
    tool_arguments: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None


@dataclass
class RunErrorEvent(BaseRunEvent):
    event_type: str = RunEventType.RUN_ERROR
    error: Optional[str] = None


@dataclass
class RunCompletedEvent(BaseRunEvent):
    event_type: str = RunEventType.RUN_COMPLETED
    output: Optional[Any] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunFailedEvent(BaseRunEvent):
    event_type: str = RunEventType.RUN_FAILED
    error: Optional[str] = None
    retries: int = 0