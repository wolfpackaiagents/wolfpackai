"""Agent tools for managing AMP scheduled tasks."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..tools.toolkit import Toolkit
from .amp import AmpScheduleClient
from .contracts import ScheduleTaskRequest


class ScheduleToolkit(Toolkit):
    """Expose AMP schedule operations to an Agent with safe HITL defaults."""

    def __init__(self, client: AmpScheduleClient):
        super().__init__(name="amp_schedule")
        self.client = client
        self.register(self.schedule_task, requires_confirmation=True)
        self.register(self.list_tasks)
        self.register(self.pause_task, requires_confirmation=True)
        self.register(self.resume_task, requires_confirmation=True)
        self.register(self.cancel_task, requires_confirmation=True)

    def schedule_task(
        self,
        name: str,
        cron: str,
        task: str,
        payload: Optional[Dict[str, Any]] = None,
        timezone: str = "UTC",
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates a scheduled task after human approval.

        Args:
            name: a concise name for the schedule.
            cron: the cron expression that controls execution.
            task: the registered task name to execute.
            payload: JSON input passed to the task.
            timezone: IANA timezone used to evaluate the cron expression.
            description: optional explanation of the schedule's purpose.
        """
        return self.client.schedule_task(
            ScheduleTaskRequest(name=name, cron=cron, task=task, payload=payload or {}, timezone=timezone, description=description)
        ).model_dump()

    def list_tasks(self, status: Optional[str] = None) -> list[Dict[str, Any]]:
        """Lists scheduled tasks without changing them.

        Args:
            status: optional schedule status filter.
        """
        return [task.model_dump() for task in self.client.list_tasks(status=status)]

    def pause_task(self, schedule_id: str) -> Dict[str, Any]:
        """Pauses a scheduled task after human approval.

        Args:
            schedule_id: the AMP schedule identifier.
        """
        return self.client.pause_task(schedule_id).model_dump()

    def resume_task(self, schedule_id: str) -> Dict[str, Any]:
        """Resumes a scheduled task after human approval.

        Args:
            schedule_id: the AMP schedule identifier.
        """
        return self.client.resume_task(schedule_id).model_dump()

    def cancel_task(self, schedule_id: str) -> Dict[str, Any]:
        """Cancels a scheduled task permanently after human approval.

        Args:
            schedule_id: the AMP schedule identifier.
        """
        return self.client.cancel_task(schedule_id).model_dump()
