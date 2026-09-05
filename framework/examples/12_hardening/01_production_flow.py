"""Run a hardened agent flow and verify AMP-compatible observer telemetry.

The example starts a local HTTP sink that accepts the AMP ingestion contract, then
runs a deterministic quote agent through PII masking, a tool allowlist, structured
output validation, and observer flushing. It needs no API key or external service.

Run from the framework directory:
    uv run python examples/12_hardening/01_production_flow.py
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from pydantic import BaseModel

from wolfpack import Agent, MeshIdentity, PIIGuardrail, tool
from wolfpack.models.base import BaseModel as WolfpackBaseModel
from wolfpack.models.base import ModelResponse
from wolfpack.models.message import Message, ToolCall
from wolfpack.observer.client import WolfpackObserver


class LocalAmpHandler(BaseHTTPRequestHandler):
    """Records AMP ingestion requests so the example can verify the full trace."""

    requests: list[dict[str, Any]] = []

    def do_POST(self) -> None:
        if self.path != "/api/public/ingestion":
            self.send_error(404)
            return

        content_length = int(self.headers["Content-Length"])
        self.requests.append(
            {
                "api_key": self.headers.get("X-API-Key"),
                "payload": json.loads(self.rfile.read(content_length)),
            }
        )
        self.send_response(202)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


class QuoteDecision(BaseModel):
    """The validated response contract returned to the calling application."""

    decision: str
    quote_id: str
    total_cents: int


@tool
def calculate_quote(plan: str, seats: int) -> dict[str, Any]:
    """Calculates the approved annual subscription quote.

    Args:
        plan: The permitted subscription plan.
        seats: The requested number of seats.
    """
    if plan != "standard" or not 1 <= seats <= 100:
        raise ValueError("Only the standard plan for 1 to 100 seats is permitted.")
    return {"quote_id": "quote-2026-001", "total_cents": seats * 1_200}


class DeterministicQuoteModel(WolfpackBaseModel):
    """Produces a tool call and validated output without relying on a provider."""

    provider = "example"
    model_id = "deterministic-quote-model"

    def __init__(self) -> None:
        self.requests: list[list[dict[str, Any]]] = []

    def invoke(self, messages, tools=None) -> ModelResponse:
        self.requests.append(messages)
        if len(self.requests) == 1:
            return ModelResponse(
                message=Message(
                    role="assistant",
                    tool_calls=[
                        ToolCall(
                            id="quote-call-1",
                            name="calculate_quote",
                            arguments='{"plan":"standard","seats":5}',
                        )
                    ],
                ),
                usage={"input_tokens": 40, "output_tokens": 12},
            )
        return ModelResponse(
            message=Message(
                role="assistant",
                content='{"decision":"approved","quote_id":"quote-2026-001","total_cents":6000}',
            ),
            usage={"input_tokens": 28, "output_tokens": 18},
        )


def main() -> None:
    LocalAmpHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), LocalAmpHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    model = DeterministicQuoteModel()
    try:
        observer = WolfpackObserver(
            base_url=f"http://127.0.0.1:{server.server_port}",
            api_key="pk-local-hardening",
            project="billing",
            max_batch=100,
            session_id="renewal-session-42",
            user_id="customer-42",
            metadata={"environment": "staging", "data_classification": "internal"},
            deployment=MeshIdentity(
                os.environ.get("WOLFPACK_ENVIRONMENT_ID", "development"),
                os.environ.get("WOLFPACK_ENVIRONMENT_SLUG", "development"),
                os.environ.get("WOLFPACK_REGISTRATION_ID", "renewal-quote-agent"),
                "renewal-quote-agent",
                "1.0.0",
                trigger_type="interactive",
            ),
        )
        agent = Agent(
            name="renewal-quote-agent",
            model=model,
            role="A billing specialist",
            goal="Create approved renewal quotes using only the supplied tools.",
            backstory="A hardened wolfpack agent with PII masking, tool allowlists, structured output, and AMP telemetry.",
            system="Create approved renewal quotes using only the supplied tools.",
            tools=[calculate_quote],
            tool_allowlist=["calculate_quote"],
            pii_guardrail=PIIGuardrail(mode="mask"),
            output_schema=QuoteDecision,
            telemetry=observer,
        )
        output = agent.run("Prepare a five-seat renewal for ana@example.com.")
        observer.flush()
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    assert not output.failed, output.error
    assert output.content == '{"decision": "approved", "quote_id": "quote-2026-001", "total_cents": 6000}'
    assert "ana@example.com" not in json.dumps(model.requests)
    assert len(LocalAmpHandler.requests) == 1

    request = LocalAmpHandler.requests[0]
    events = request["payload"]["events"]
    bodies = [event["body"] for event in events]
    # Find the TRACE end event which carries session_id/user_id/metadata.
    trace = next(
        body for body in bodies
        if body.get("type") == "TRACE" and "session_id" in body
    )

    assert request["api_key"] == "pk-local-hardening"
    assert {body["type"] for body in bodies} >= {"TRACE", "GENERATION", "TOOL", "SPAN"}
    assert trace["session_id"] == "renewal-session-42"
    assert trace["user_id"] == "customer-42"
    assert trace["metadata"]["environment"] == "staging"
    assert json.loads(trace["output"]) == QuoteDecision(
        decision="approved", quote_id="quote-2026-001", total_cents=6000
    ).model_dump()
    assert "ana@example.com" not in json.dumps(request)

    print("Hardened quote completed:", output.content)
    print(f"Published {len(events)} AMP-compatible events for run {output.run_id}.")
    print("Verified PII masking, tool policy, structured output, and observer telemetry.")


if __name__ == "__main__":
    main()
