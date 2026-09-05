"""Create and inspect AMP scheduled tasks.

Run with an AMP instance that implements the schedules API:
    WOLFPACK_AMP_URL=http://localhost:8200 WOLFPACK_AMP_API_KEY=pk-wp-dev uv run python examples/16_scheduled_tasks/01_schedule_client.py
"""

import os
import sys
import json
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from wolfpack import AmpScheduleClient, ScheduleTaskRequest


def registration_id(base_url: str, api_key: str) -> str:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/public/mesh/catalog",
        headers={"X-API-Key": api_key},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        catalog = json.loads(response.read())
    for environment in catalog["environments"]:
        if environment["slug"] == "development":
            for registration in environment["registrations"]:
                if registration["definition_key"] == "weather-operations":
                    return registration["id"]
    raise RuntimeError("weather-operations not found. Run `uv run amp seed-demo` in control-plane/backend.")


def main() -> None:
    base_url = os.environ.get("WOLFPACK_AMP_URL", "http://localhost:8000")
    api_key = os.environ.get("WOLFPACK_AMP_API_KEY", "pk-wp-dev:dev-secret")
    client = AmpScheduleClient(base_url, api_key, registration_id=registration_id(base_url, api_key))
    task = next((item for item in client.list_tasks() if item.name == "weekday-operations-report"), None)
    if task is None:
        task = client.schedule_task(
            ScheduleTaskRequest(
                name="weekday-operations-report",
                cron="0 9 * * 1-5",
                task="reports.operations_daily",
                payload={"channel": "operations"},
                timezone="America/Sao_Paulo",
                description="Send the daily operations report on business days.",
            )
        )
        print(f"Created {task.id}: {task.name} ({task.status})")
    else:
        print(f"Existing {task.id}: {task.name} ({task.status})")
    for scheduled in client.list_tasks():
        print(f"{scheduled.id}: {scheduled.cron} -> {scheduled.task or 'runtime payload'} [{scheduled.status}]")


if __name__ == "__main__":
    main()
