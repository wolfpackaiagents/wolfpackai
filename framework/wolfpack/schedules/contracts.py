"""Typed contracts for the AMP scheduled tasks API."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class ScheduleTaskRequest(BaseModel):
    """A task definition to be executed by AMP on a cron schedule."""

    name: str = Field(min_length=1, max_length=128)
    cron: str = Field(min_length=1, max_length=256)
    task: str = Field(min_length=1, max_length=256)
    payload: Dict[str, Any] = Field(default_factory=dict)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    description: Optional[str] = Field(default=None, max_length=1024)

    def to_amp_payload(self, registration_id: str) -> Dict[str, Any]:
        """Translate the framework task label to AMP's schedule payload."""
        payload = self.model_dump(exclude={"task", "description"}, exclude_none=True)
        payload["registration_id"] = registration_id
        payload["schedule_type"] = "cron"
        payload["payload"] = {**self.payload, "_wolfpack_task": self.task}
        return payload


class ScheduleTask(BaseModel):
    """A scheduled task returned by AMP."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    cron: str | None = None
    task: str | None = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    timezone: str = "UTC"
    status: str = "active"
    description: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    next_run_at: Optional[str] = None
    last_run_at: Optional[str] = None
