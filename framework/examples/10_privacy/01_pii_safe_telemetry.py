"""Send privacy-safe telemetry to a local deterministic ingestion sink.

The agent masks PII before the model sees the prompt. The observer independently
redacts every telemetry field before it is sent, including model output and
metadata. `user_id` and `data_subject` metadata make the trace linkable to a
data-subject request without placing contact details in telemetry.

Run from the framework directory:
    uv run python examples/10_privacy/01_pii_safe_telemetry.py
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from wolfpack import Agent, MeshIdentity, PIIGuardrail, get_model_from_env
from wolfpack.models.base import BaseModel, ModelResponse
from wolfpack.models.message import Message
from wolfpack.observer.client import WolfpackObserver


class LocalIngestionHandler(BaseHTTPRequestHandler):
    """Accepts a single ingestion request and retains its JSON payload."""

    received: list[dict] = []

    def do_POST(self) -> None:
        content_length = int(self.headers["Content-Length"])
        self.received.append(json.loads(self.rfile.read(content_length)))
        self.send_response(202)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


class DeterministicModel(BaseModel):
    """Returns PII deliberately so observer-side redaction is visible."""

    provider = "example"
    model_id = "deterministic"

    def invoke(self, messages, tools=None) -> ModelResponse:
        return ModelResponse(
            message=Message(role="assistant", content="We will reply to ana@example.com."),
            usage={"input_tokens": 4, "output_tokens": 8},
        )


def main() -> None:
    LocalIngestionHandler.received = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), LocalIngestionHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        observer = WolfpackObserver(
            base_url=f"http://127.0.0.1:{server.server_port}",
            user_id="customer-42",
            session_id="support-session-9",
            metadata={"data_subject": {"region": "BR", "lawful_basis": "support"}},
            deployment=MeshIdentity(
                os.environ.get("WOLFPACK_ENVIRONMENT_ID", "development"),
                os.environ.get("WOLFPACK_ENVIRONMENT_SLUG", "development"),
                os.environ.get("WOLFPACK_REGISTRATION_ID", "privacy-demo"),
                "privacy-demo",
                "1.0.0",
                trigger_type="interactive",
            ),
        )
        try:
            if os.environ.get("WOLFPACK_REAL_MODEL") == "1":
                model = get_model_from_env()
            else:
                model = DeterministicModel()
        except Exception:
            model = DeterministicModel()
        agent = Agent(
            name="privacy-demo",
            model=model,
            role="A privacy-safe assistant",
            goal="Handle user data while masking PII before it reaches the model.",
            backstory="A wolfpack agent configured with PII masking and privacy-safe telemetry.",
            pii_guardrail=PIIGuardrail(mode="mask"),
            telemetry=observer,
        )
        output = agent.run("My email is ana@example.com. Please update my address.")
        observer.flush()
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    events = LocalIngestionHandler.received[0]["events"]
    # Find the TRACE end event (which carries user_id/session_id/metadata).
    event = next(
        item["body"] for item in events
        if item.get("type") == "observation-end" and item["body"]["type"] == "TRACE"
    )
    persisted = json.dumps(event)
    assert "ana@example.com" not in persisted
    assert event["user_id"] == "customer-42"
    assert event["metadata"]["data_subject"]["lawful_basis"] == "support"

    print("agent output:", output.content)
    print("persisted output:", event["output"])
    print("data subject:", event["user_id"])
    print("PII was masked before telemetry persistence.")


if __name__ == "__main__":
    main()
