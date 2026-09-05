"""Tests for the AMP scheduled tasks client and Agent toolkit."""

import json

from wolfpack.schedules import AmpScheduleClient, ScheduleTaskRequest, ScheduleToolkit


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def task_payload(**overrides):
    return {
        "id": "sch_1",
        "registration_id": "reg_1",
        "name": "Daily report",
        "schedule_type": "cron",
        "cron": "0 9 * * 1-5",
        "payload": {"team": "ops", "_wolfpack_task": "reports.daily"},
        "timezone": "America/Sao_Paulo",
        "status": "active",
        **overrides,
    }


def test_amp_schedule_client_uses_public_schedule_contract(monkeypatch):
    client = AmpScheduleClient("http://amp.test", "pk-test", registration_id="reg_1")
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request.method, request.full_url, json.loads(request.data) if request.data else None, timeout))
        if request.full_url.endswith("/schedules?status=paused"):
            return FakeResponse([task_payload(status="paused")])
        if request.full_url.endswith("/pause"):
            return FakeResponse(task_payload(status="paused"))
        if request.full_url.endswith("/resume"):
            return FakeResponse(task_payload(status="active"))
        if request.method == "DELETE" and request.full_url.endswith("/schedules/sch_1"):
            return FakeResponse(task_payload(status="cancelled"))
        return FakeResponse(task_payload())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    created = client.schedule_task(ScheduleTaskRequest(name="Daily report", cron="0 9 * * 1-5", task="reports.daily", payload={"team": "ops"}, timezone="America/Sao_Paulo"))
    paused = client.list_tasks(status="paused")
    assert client.pause_task("sch_1").status == "paused"
    assert client.resume_task("sch_1").status == "active"
    assert client.cancel_task("sch_1").status == "cancelled"

    assert created.id == "sch_1"
    assert paused[0].status == "paused"
    assert created.task == "reports.daily"
    assert paused[0].task == "reports.daily"
    assert requests == [
        ("POST", "http://amp.test/api/public/schedules", {"registration_id": "reg_1", "name": "Daily report", "schedule_type": "cron", "cron": "0 9 * * 1-5", "payload": {"team": "ops", "_wolfpack_task": "reports.daily"}, "timezone": "America/Sao_Paulo"}, 10),
        ("GET", "http://amp.test/api/public/schedules?status=paused", None, 10),
        ("POST", "http://amp.test/api/public/schedules/sch_1/pause", None, 10),
        ("POST", "http://amp.test/api/public/schedules/sch_1/resume", None, 10),
        ("DELETE", "http://amp.test/api/public/schedules/sch_1", None, 10),
    ]


def test_schedule_toolkit_applies_hitl_to_mutations_only():
    toolkit = ScheduleToolkit(AmpScheduleClient("http://amp.test"))

    assert toolkit.name == "amp_schedule"
    assert set(toolkit.functions) == {"schedule_task", "list_tasks", "pause_task", "resume_task", "cancel_task"}
    assert toolkit.functions["list_tasks"].requires_confirmation is False
    for name in ("schedule_task", "pause_task", "resume_task", "cancel_task"):
        assert toolkit.functions[name].requires_confirmation is True
        result = toolkit.functions[name].get_function_call("call_1", {"schedule_id": "sch_1"}).execute()
        assert result.status == "tool_confirmation"
