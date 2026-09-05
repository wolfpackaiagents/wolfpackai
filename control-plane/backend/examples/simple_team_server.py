"""Simplified team agent server — no telemetry, just execute the team and return the result.

Run:
    uv run python examples/simple_team_server.py
"""

from __future__ import annotations

import os
import time

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from wolfpack.team import Team
from wolfpack.models.utils import get_model_from_env

app = FastAPI(title="Simple Team Agent")


class SimpleTask(BaseModel):
    message: str


class Specialist:
    def __init__(self, name: str):
        self.name = name
        self.run_id = f"run_{name}"
        self.display_name = name.replace("-", " ").title()
        self.description = f"{self.display_name}: specialist"

    def run(self, task: str):
        content = f"{self.display_name}: processed request: {task[:80]}"
        return type("Output", (), {"content": content, "run_id": self.run_id, "failed": False})()


@app.post("/v1/team-run")
def team_run(task: SimpleTask):
    """Receives a message, executes the support-orchestrator Team, returns the result."""
    print(f"\n=== Received: {task.message[:60]}... ===")

    try:
        model = get_model_from_env()
        print(f"  Model: {model.provider}/{model.model_id}")
    except ValueError:
        return {"error": "No LLM provider configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY."}

    triage = Specialist("support-triage")
    knowledge = Specialist("knowledge-specialist")
    team = Team("support-orchestrator", [triage, knowledge], leader_model=model)

    print("  Running team (leader delegates via tool)...")
    start = time.time()
    result = team.run(task.message)
    duration = time.time() - start
    print(f"  Done in {duration:.2f}s")

    return {
        "status": "completed",
        "output": result.content,
        "duration_s": round(duration, 2),
    }


if __name__ == "__main__":
    port = int(os.environ.get("TEAM_AGENT_PORT", "9012"))
    print(f"Starting simple team agent on port {port}")
    uvicorn.run(app, host="127.0.0.1", port=port)