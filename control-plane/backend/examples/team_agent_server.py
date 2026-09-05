"""FastAPI agent that executes the support-orchestrator Team and calls back to AMP.

Run:
    uv run python examples/team_agent_server.py

Then create a run in AMP and this server will pick it up.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from wolfpack.agent.agent import Agent
from wolfpack.mesh import MeshIdentity
from wolfpack.models.utils import get_model_from_env
from wolfpack.observer.client import WolfpackObserver
from wolfpack.team import Team

app = FastAPI(title="Wolfpack Team Agent Runtime")

AMP_URL = os.environ.get("WOLFPACK_AMP_URL", "http://127.0.0.1:8000")
AMP_API_KEY = os.environ.get("WOLFPACK_AMP_API_KEY", "pk-wp-dev:dev-secret")
INSTANCE_ID = os.environ.get("WOLFPACK_INSTANCE_ID", "team-agent-1")


class TaskRequest(BaseModel):
    run_id: str
    conversation_id: str
    message: str
    registration_id: str
    session_id: str
    environment_id: str
    environment_slug: str
    definition_key: str
    definition_version: str


class Specialist:
    """A team member that processes a delegated task."""

    def __init__(self, name: str, telemetry: WolfpackObserver, trace: dict[str, Any]):
        self.name = name
        self.telemetry = telemetry
        self.run_id = trace["id"]
        self.display_name = name.replace("-", " ").title()
        self.description = f"{self.display_name}: specialized support agent"

    def run(self, task: str):
        span = self.telemetry.start_span("TOOL", f"execute_{self.name}", parent=self.telemetry._last_trace_id() and {"id": self.telemetry._last_trace_id()})
        content = f"{self.display_name}: processed task: {task[:60]}..."
        if span:
            self.telemetry.end_span(span, input={"task": task}, output=content)
        return type("Output", (), {"content": content, "run_id": self.run_id, "failed": False})()


@app.post("/v1/execute-task")
def execute_task(task: TaskRequest):
    """Executes a chat run using the support-orchestrator Team and calls back to AMP."""
    print(f"=== Executing task {task.run_id} ===")
    print(f"  Message: {task.message[:80]}...")
    print(f"  Registration: {task.registration_id}")

    try:
        model = get_model_from_env()
        print(f"  Model: {model.provider}/{model.model_id}")
    except ValueError:
        return {"status": "error", "error": "No LLM provider configured"}

    observer = WolfpackObserver(
        AMP_URL,
        api_key=AMP_API_KEY,
        session_id=task.session_id,
        deployment=MeshIdentity(
            task.environment_id,
            task.environment_slug,
            task.registration_id,
            task.definition_key,
            task.definition_version,
            trigger_type="interactive_chat",
        ),
    )

    root = observer.start_trace("support-orchestrator")
    triage = Specialist("support-triage", observer, root)
    knowledge = Specialist("knowledge-specialist", observer, root)
    team = Team("support-orchestrator", [triage, knowledge], leader_model=model, telemetry=observer)

    print("  Running team...")
    start = time.time()
    result = team.run(task.message)
    duration = time.time() - start
    print(f"  Team completed in {duration:.2f}s")

    final = result.content or "Support Orchestrator: no response generated."

    observer.end_trace(root, input={"message": task.message}, output=final)
    observer.flush()
    print(f"  Flushed observer events to AMP")

    client = httpx.Client(trust_env=False)
    headers = {"X-API-Key": AMP_API_KEY}

    complete_resp = client.post(
        f"{AMP_URL}/api/public/chat/runs/{task.run_id}/callback/complete",
        headers=headers,
        json={"output": final, "trace_id": root["id"]},
    )

    if complete_resp.status_code == 200:
        print(f"  Callback completed: {complete_resp.json()}")
        return {"status": "completed", "output": final, "trace_id": root["id"], "duration_s": round(duration, 2)}
    else:
        print(f"  Callback failed: {complete_resp.status_code} {complete_resp.text}")
        return {"status": "callback_failed", "error": complete_resp.text}


@app.post("/v1/heartbeat")
def heartbeat():
    """Registers this runtime as online in the AMP Mesh."""
    return {"instance_id": INSTANCE_ID, "status": "alive"}


if __name__ == "__main__":
    port = int(os.environ.get("TEAM_AGENT_PORT", "9011"))
    print(f"Starting Team Agent runtime on port {port}...")
    uvicorn.run(app, host="127.0.0.1", port=port)