"""Reminder creation backed by the optional AMP schedule client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from wolfpack.schedules import ScheduleTaskRequest


@dataclass(frozen=True)
class PersonalReminder:
    name: str
    cron: str
    message: str
    task: str
    timezone: str
    schedule_id: Optional[str]
    status: str


class ReminderService:
    """Creates personal reminder schedules when a schedule client is configured."""

    def __init__(self, schedule_client: Optional[Any] = None):
        self.schedule_client = schedule_client

    def create(
        self, name: str, cron: str, message: str, *, task: str = "personal.reminder",
        timezone: str = "UTC", payload: Optional[Dict[str, Any]] = None,
    ) -> PersonalReminder:
        if not self.schedule_client:
            raise RuntimeError("A schedule client is required to create a reminder.")
        body = {**(payload or {}), "message": message}
        scheduled = self.schedule_client.schedule_task(
            ScheduleTaskRequest(name=name, cron=cron, task=task, payload=body, timezone=timezone)
        )
        return PersonalReminder(name, cron, message, task, timezone, scheduled.id, scheduled.status)
