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


PLACEHOLDER = "[PII_REDACTED]"
# A hex id with a long run of digits: the phone pattern reads it as a phone number.
DIGIT_RUN_ID = "01234567890123456789012345678901"
HEX_ID = "1234567890123456789012345678901a"
UUID_ID = "12345678-9012-3456-7890-12345678901a"


def test_redaction_leaves_ids_timestamps_and_developer_labels_intact():
    observer = WolfpackObserver(
        "http://amp.test",
        metadata={"studio_project_id": HEX_ID, "studio_revision_id": UUID_ID, "created": "2026-09-20T18:01:43.123Z"},
    )

    trace = observer.start_trace("support-agent", run_id=DIGIT_RUN_ID)
    span = observer.start_span("llm_call", "gpt-4o-mini", parent=trace)
    observer.end_span(span, output="ok")
    observer.end_trace(trace, output="Contact ana@example.com")

    assert observer._buffer
    for event in observer._buffer:
        body = event["body"]
        structural = [event["id"], event["timestamp"], body.get("id"), body.get("trace_id")]
        structural += [body.get("parent_observation_id"), body.get("start_time"), body.get("end_time")]
        assert PLACEHOLDER not in json.dumps(structural), event
        assert body["metadata"]["studio_project_id"] == HEX_ID
        assert body["metadata"]["studio_revision_id"] == UUID_ID
        assert body["metadata"]["created"] == "2026-09-20T18:01:43.123Z"
    trace_end = next(e["body"] for e in observer._buffer if e["body"]["type"] == "TRACE" and e["body"].get("end_time"))
    assert trace_end["id"] == DIGIT_RUN_ID
    assert trace_end["output"] == f"Contact {PLACEHOLDER}"


def test_redaction_still_masks_user_content_inside_approval_metadata():
    from types import SimpleNamespace

    observer = WolfpackObserver("http://amp.test")
    requirement = SimpleNamespace(
        id="req_1",
        approval_id=None,
        run_id=DIGIT_RUN_ID,
        tool_name="send_mail",
        requirement="confirmation",
        created_at=1_758_000_000.0,
        status="approved",
        tool_arguments={"to": "ana@example.com", "body": "call +1 202-555-0111"},
        confirmation=True,
        user_input="reach me at ana@example.com",
        confirmation_note="phone +1 202-555-0111",
    )

    observer.start_for_approval(requirement)
    observer.end_for_approval(requirement)

    start, end = (event["body"] for event in observer._buffer)
    assert start["trace_id"] == DIGIT_RUN_ID and end["trace_id"] == DIGIT_RUN_ID
    assert start["metadata"]["tool_arguments"] == {"to": PLACEHOLDER, "body": f"call {PLACEHOLDER}"}
    assert end["metadata"]["user_input"] == f"reach me at {PLACEHOLDER}"
    assert end["metadata"]["note"] == f"phone {PLACEHOLDER}"
    assert start["metadata"]["tool_name"] == "send_mail"


def test_redaction_still_masks_structural_looking_keys_inside_user_content():
    observer = WolfpackObserver("http://amp.test")

    trace = observer.start_trace("support-agent", run_id="run-nested")
    span = observer.start_span("tool", "lookup", parent=trace)
    observer.end_span(span, input={"name": "call +1 202-555-0111", "id": "ana@example.com"}, output="ok")

    tool_end = next(e["body"] for e in observer._buffer if e["body"]["type"] == "TOOL" and e["body"].get("end_time"))
    assert tool_end["input"] == {"name": f"call {PLACEHOLDER}", "id": PLACEHOLDER}
    assert tool_end["name"] == "lookup"


def test_redaction_masks_free_form_metadata_by_default():
    observer = WolfpackObserver("http://amp.test", session_id="ana@example.com")

    trace = observer.start_trace("agent", run_id="run-meta")
    span = observer.start_span("llm_call", "gpt-4o-mini", parent=trace)
    routing = {"attempts": [{"model": "a", "error": "400 invalid input: ana@example.com"}], "selected": "b"}
    observer.end_span(span, output="ok", metadata={"routing": routing, "note_free": "call +1 202-555-0111"})
    observer.record_interaction("a", "b", "delegation", trace_id="run-meta", metadata={"note": "ana@example.com"})

    serialized = json.dumps(observer._buffer)
    assert "ana@example.com" not in serialized
    assert "+1 202-555-0111" not in serialized
    generation = next(e["body"] for e in observer._buffer if e["body"]["type"] == "GENERATION" and e["body"].get("end_time"))
    assert generation["metadata"]["routing"]["selected"] == "b"
    assert generation["metadata"]["routing"]["attempts"][0]["error"] == f"400 invalid input: {PLACEHOLDER}"
    assert all(e["body"].get("session_id") in (None, PLACEHOLDER) for e in observer._buffer)


def test_redaction_does_not_treat_card_or_phone_numbers_as_identifiers():
    observer = WolfpackObserver("http://amp.test", metadata={"card": "4111111111111111", "phone": "12025550111"})

    trace = observer.start_trace("agent", run_id="run-card")
    observer.end_trace(trace, output="4111111111111111")

    end = next(e["body"] for e in observer._buffer if e["body"]["type"] == "TRACE" and e["body"].get("end_time"))
    assert end["output"] == PLACEHOLDER
    assert end["metadata"]["card"] == PLACEHOLDER
    assert end["metadata"]["phone"] == PLACEHOLDER
