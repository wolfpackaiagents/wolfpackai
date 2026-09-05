"""Deterministic reminder scheduling and external-action approval flow.

Run with: uv run python examples/17_personal_agent/02_reminder_and_approval.py
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wolfpack.personal import ActionPolicy, ExternalActionManager, ReminderService
from wolfpack.schedules import ScheduleTask


class FakeScheduleClient:
    """Local stand-in for AmpScheduleClient; it makes no HTTP requests."""

    def schedule_task(self, request):
        return ScheduleTask(id="reminder-1", status="active", **request.model_dump())


def main() -> None:
    reminder = ReminderService(FakeScheduleClient()).create(
        "Stretch", "0 10 * * 1-5", "Take a short stretch break", timezone="America/Sao_Paulo"
    )
    print(f"{reminder.schedule_id}: {reminder.message}")

    actions = ExternalActionManager(ActionPolicy(allowed_actions=frozenset({"email.send"})))
    draft = actions.draft("email.send", "alex@example.test", {"subject": "Weekly plan"})
    print(draft.status)
    actions.approve(draft.id, note="Reviewed by Alex")
    completed = actions.execute(draft.id, lambda action: {"delivered": False, "target": action.target})
    print(f"{completed.status}: {completed.result['delivered']}")


if __name__ == "__main__":
    main()
