"""Tests for signed HTTP runtime dispatch and result callbacks."""

import json
import threading

import pytest

from wolfpack.schedules import HttpRuntimeRunner, sign_schedule_payload


def dispatch(**overrides):
    return {"run_id": "run-1", "schedule_id": "schedule-1", "fencing_token": 2, "attempt": 1, "target_instance_id": "replica-1", "payload": {"work": "report"}, "deadline_at": None, **overrides}


def test_runner_rejects_bad_signature_and_wrong_target():
    runner = HttpRuntimeRunner("replica-1", "dispatch-secret", "callback-secret", "http://amp.test", lambda _context: {})
    body = json.dumps(dispatch()).encode()
    with pytest.raises(PermissionError, match="signature"):
        runner.handle_dispatch(body, "sha256=bad")
    wrong = json.dumps(dispatch(target_instance_id="other")).encode()
    with pytest.raises(PermissionError, match="different"):
        runner.handle_dispatch(wrong, sign_schedule_payload("dispatch-secret", wrong))


def test_runner_completes_once_and_signs_callback(monkeypatch):
    completed, callbacks = threading.Event(), []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return False

    def urlopen(request, timeout):
        callbacks.append((request.full_url, json.loads(request.data), request.headers["X-wolfpack-schedule-signature"], timeout))
        completed.set()
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    runner = HttpRuntimeRunner("replica-1", "dispatch-secret", "callback-secret", "http://amp.test", lambda context: {"run": context.dispatch.run_id})
    body = json.dumps(dispatch(), separators=(",", ":")).encode()
    assert runner.handle_dispatch(body, sign_schedule_payload("dispatch-secret", body))["status"] == "accepted"
    assert runner.handle_dispatch(body, sign_schedule_payload("dispatch-secret", body))["duplicate"] is True
    assert completed.wait(1)
    assert callbacks[0][0].endswith("/runs/run-1/callback/complete")
    assert callbacks[0][1] == {"fencing_token": 2, "result": {"run": "run-1"}}
    assert callbacks[0][2] == sign_schedule_payload("callback-secret", json.dumps(callbacks[0][1], separators=(",", ":"), sort_keys=True).encode())
