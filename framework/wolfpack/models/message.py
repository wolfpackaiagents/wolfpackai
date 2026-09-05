"""Canonical message model between agents and models.

Roles: system, user, assistant, tool. Each message supports content (str or a list
of parts), tool_calls, tool_call_id and metadata for observability.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    id: Optional[str] = None
    name: str
    arguments: str  # serialized JSON

    def to_dict(self) -> Dict[str, Any]:
        # OpenAI-compatible shape for serialized provider payloads
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": self.arguments},
        }


class Message(BaseModel):
    role: str  # system | user | assistant | tool
    content: Optional[Union[str, List[Any]]] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    name: Optional[str] = None
    reasoning_content: Optional[str] = None
    created_at: Optional[str] = None

    def is_tool_call(self) -> bool:
        return bool(self.tool_calls)

    def get_text(self) -> str:
        if isinstance(self.content, str):
            return self.content
        if isinstance(self.content, list):
            out: List[str] = []
            for p in self.content:
                if isinstance(p, dict) and p.get("type") == "text":
                    out.append(str(p.get("text", "")))
            return "\n".join(out)
        return ""

    def to_dict(self) -> Dict[str, Any]:
        d = super().model_dump(exclude_none=True)
        if self.tool_calls:
            d["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        return d