"""Synchronous HTTP client for AMP scheduled tasks."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from .contracts import ScheduleTask, ScheduleTaskRequest


class AmpScheduleClient:
    """Manages scheduled tasks through AMP's public schedules API."""

    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: float = 10, registration_id: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.registration_id = registration_id

    def schedule_task(self, task: ScheduleTaskRequest) -> ScheduleTask:
        """Create a scheduled task."""
        if not self.registration_id:
            raise ValueError("registration_id is required to create an AMP schedule.")
        return self._schedule_task(self._request("POST", "/schedules", task.to_amp_payload(self.registration_id)))

    def list_tasks(self, status: Optional[str] = None) -> List[ScheduleTask]:
        """List scheduled tasks, optionally filtered by status."""
        path = "/schedules"
        if status:
            path += f"?{urllib.parse.urlencode({'status': status})}"
        response = self._request("GET", path)
        return [self._schedule_task(item) for item in response]

    def pause_task(self, schedule_id: str) -> ScheduleTask:
        """Pause an active scheduled task."""
        return ScheduleTask.model_validate(self._request("POST", f"/schedules/{schedule_id}/pause"))

    def resume_task(self, schedule_id: str) -> ScheduleTask:
        """Resume a paused scheduled task."""
        return ScheduleTask.model_validate(self._request("POST", f"/schedules/{schedule_id}/resume"))

    def cancel_task(self, schedule_id: str) -> ScheduleTask:
        """Cancel a scheduled task permanently."""
        return self._schedule_task(self._request("DELETE", f"/schedules/{schedule_id}"))

    @staticmethod
    def _schedule_task(payload: Dict[str, Any]) -> ScheduleTask:
        payload["task"] = (payload.get("payload") or {}).get("_wolfpack_task")
        return ScheduleTask.model_validate(payload)

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            f"{self.base_url}/api/public/schedules{path.removeprefix('/schedules')}",
            data=data,
            headers={"Content-Type": "application/json", "X-API-Key": self.api_key or ""},
            method=method,
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = response.read()
        return json.loads(body) if body else None
