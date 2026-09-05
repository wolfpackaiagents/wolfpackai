"""Inspect the HITL protection applied to schedule management tools.

Run:
    uv run python examples/16_scheduled_tasks/02_agent_hitl.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from wolfpack import AmpScheduleClient, ScheduleToolkit


def main() -> None:
    schedules = ScheduleToolkit(AmpScheduleClient("http://localhost:8200"))
    print("Registered tools:", list(schedules.functions))
    for name, function in schedules.functions.items():
        print(f"{name}: requires_confirmation={function.requires_confirmation}")

    call = schedules.functions["cancel_task"].get_function_call("call_1", {"schedule_id": "sch_example"})
    result = call.execute()
    print(f"cancel_task result: {result.status}")


if __name__ == "__main__":
    main()
