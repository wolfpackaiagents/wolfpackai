"""The result of an agent execution.

`RunOutput` carries the final message, all conversation messages (including tool
calls), total token usage, the list of references (e.g. RAG documents) and — for
human-in-the-loop runs — the run status and pending requirements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..models.message import Message
from ..run.requirement import RunRequirement, RunStatus


@dataclass
class RunOutput:
    run_id: str
    content: Optional[str] = None
    messages: List[Message] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    usage: Dict[str, Any] = field(default_factory=dict)
    references: List[Any] = field(default_factory=list)
    failed: bool = False
    error: Optional[str] = None
    status: str = RunStatus.COMPLETED.value
    requirements: List[RunRequirement] = field(default_factory=list)
    is_paused: bool = False
    paused_at_message_index: Optional[int] = None

    @property
    def active_requirements(self) -> List[RunRequirement]:
        return [r for r in self.requirements if r.is_pending()]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "content": self.content,
            "messages": [m.to_dict() for m in self.messages],
            "tool_calls": self.tool_calls,
            "usage": self.usage,
            "references": [getattr(r, "to_dict", lambda: r)() for r in self.references],
            "failed": self.failed,
            "error": self.error,
            "status": self.status,
            "requirements": [r.to_dict() for r in self.requirements],
            "is_paused": self.is_paused,
            "paused_at_message_index": self.paused_at_message_index,
        }