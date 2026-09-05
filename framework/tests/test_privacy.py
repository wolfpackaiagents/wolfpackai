"""Tests for privacy-safe Wolfpack telemetry."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from wolfpack.observer.client import WolfpackObserver
from wolfpack.mesh import MeshIdentity


class _IngestionHandler(BaseHTTPRequestHandler):
    received: list[dict] = []

    def do_POST(self) -> None:
        content_length = int(self.headers["Content-Length"])
        self.received.append(json.loads(self.rfile.read(content_length)))
        self.send_response(202)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def test_observer_redacts_pii_and_attaches_data_subject_context():
    _IngestionHandler.received = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _IngestionHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        observer = WolfpackObserver(
            base_url=f"http://127.0.0.1:{server.server_port}",
            user_id="customer-42",
            session_id="support-session-9",
            metadata={"data_subject": {"region": "BR", "lawful_basis": "support"}},
        )
        trace = observer.start_trace("support-agent", run_id="run-privacy")
        observer.end_trace(trace, output="Contact ana@example.com or +1 202-555-0111.")
        observer.flush()
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    body = next(event["body"] for event in _IngestionHandler.received[0]["events"] if event["type"] == "observation-end")
    serialized = json.dumps(body)
    assert "ana@example.com" not in serialized
    assert "+1 202-555-0111" not in serialized
    assert body["output"] == "Contact [PII_REDACTED] or [PII_REDACTED]."
    assert body["user_id"] == "customer-42"
    assert body["session_id"] == "support-session-9"
    assert body["metadata"] == {"data_subject": {"region": "BR", "lawful_basis": "support"}}


def test_observer_can_disable_pii_redaction():
    observer = WolfpackObserver("http://amp.test", redact_pii=False)
    observer._flush = lambda events: None

    trace = observer.start_trace("support-agent", run_id="run-raw")
    observer.end_trace(trace, output="Contact ana@example.com")

    end_event = next(event for event in observer._buffer if event["type"] == "observation-end")
    assert end_event["body"]["output"] == "Contact ana@example.com"


def test_observer_propagates_mesh_identity_to_trace_and_spans():
    observer = WolfpackObserver(
        "http://amp.test",
        deployment=MeshIdentity(
            environment_id="env_staging",
            environment_slug="staging",
            registration_id="reg_support",
            definition_key="support-triage",
            definition_version="1.2.0",
            policy_hash="policy-v3",
        ),
    )
    trace = observer.start_trace("support-triage", run_id="run-mesh")
    span = observer.start_span("llm_call", "gpt-4o-mini", parent=trace)
    observer.end_span(span, output={"content": "classified"})
    observer.end_trace(trace, output="complete")

    bodies = [event["body"] for event in observer._buffer]
    trace_body = next(body for body in bodies if body["type"] == "TRACE" and body.get("end_time"))
    span_body = next(body for body in bodies if body["type"] == "GENERATION" and body.get("end_time"))
    assert trace_body["environment"] == "staging"
    assert trace_body["metadata"]["mesh"]["registration_id"] == "reg_support"
    assert span_body["metadata"]["mesh"]["definition_key"] == "support-triage"


def test_observer_records_explicit_mesh_interaction_context():
    observer = WolfpackObserver("http://amp.test")

    observer.record_interaction(
        "triage",
        "knowledge-search",
        "tool",
        trace_id="trace-chain",
        operation="tool.invoke",
        tool_name="search_support_knowledge",
        source_display_name="Support Triage",
        target_display_name="Knowledge Search",
    )

    interaction = observer._buffer[0]["body"]["metadata"]["mesh_interaction"]
    assert interaction == {
        "source": "triage",
        "target": "knowledge-search",
        "interaction_type": "tool",
        "operation": "tool.invoke",
        "tool_name": "search_support_knowledge",
        "source_display_name": "Support Triage",
        "target_display_name": "Knowledge Search",
        "metadata": {},
    }
