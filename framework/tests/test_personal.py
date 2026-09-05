"""Tests for consent-bound memory and personal-agent primitives."""

from datetime import datetime, timedelta, timezone

import pytest

from wolfpack.memory import ConsentRequiredError, MemoryConsent, MemoryProvenance, ScopedPersonalMemory
from wolfpack.personal import ActionPolicy, ExternalActionManager, ReminderService
from wolfpack.schedules import ScheduleTask


def test_scoped_memory_requires_consent_preserves_provenance_and_isolates_scopes():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    memory = ScopedPersonalMemory(now=lambda: now)
    consent = MemoryConsent(True, "planning assistance", now, "chat")
    provenance = MemoryProvenance("user", "turn-4", now)

    profile = memory.remember_profile("person-1", "planning", "name", "Alex", consent=consent, provenance=provenance)
    memory.remember_fact("person-1", "health", "name", "private", consent=consent, provenance=provenance)

    assert profile.provenance.reference == "turn-4"
    assert memory.get("person-1", "planning", "name").value == "Alex"
    assert memory.get("person-1", "health", "name").value == "private"
    with pytest.raises(ConsentRequiredError):
        memory.remember_fact("person-1", "planning", "email", "alex@example.test", consent=MemoryConsent(False, "unknown", now), provenance=provenance)


def test_scoped_memory_expires_and_forgets_matching_values():
    current = [datetime(2026, 1, 1, tzinfo=timezone.utc)]
    memory = ScopedPersonalMemory(now=lambda: current[0])
    consent = MemoryConsent(True, "reminders", current[0])
    provenance = MemoryProvenance("user")
    memory.remember_fact("person-1", "planning", "temporary", True, consent=consent, provenance=provenance, ttl=timedelta(minutes=5))
    memory.remember_fact("person-1", "planning", "permanent", True, consent=consent, provenance=provenance)

    current[0] += timedelta(minutes=5)
    assert memory.get("person-1", "planning", "temporary") is None
    assert memory.forget("person-1", "planning") == 1
    assert memory.list("person-1", "planning") == []


def test_reminder_service_adapts_to_schedule_client_without_network():
    received = []

    class FakeScheduleClient:
        def schedule_task(self, request):
            received.append(request)
            return ScheduleTask(id="sch-1", status="active", **request.model_dump())

    reminder = ReminderService(FakeScheduleClient()).create(
        "Hydrate", "0 * * * *", "Drink water", payload={"subject_id": "person-1", "message": "ignored"}
    )

    assert received[0].payload == {"subject_id": "person-1", "message": "Drink water"}
    assert reminder.schedule_id == "sch-1"
    assert reminder.status == "active"
    with pytest.raises(RuntimeError, match="schedule client"):
        ReminderService().create("No client", "0 * * * *", "No-op")


def test_external_actions_are_drafted_then_approved_before_execution():
    calls = []
    manager = ExternalActionManager(ActionPolicy(allowed_actions=frozenset({"email.send"})))
    action = manager.draft("email.send", "alex@example.test", {"subject": "Hello"})

    assert action.status == "pending_approval"
    with pytest.raises(PermissionError, match="approved"):
        manager.execute(action.id, calls.append)
    manager.approve(action.id, note="owner approved")
    executed = manager.execute(action.id, lambda proposed: calls.append(proposed.target) or "queued")

    assert calls == ["alex@example.test"]
    assert executed.status == "executed"
    assert executed.result == "queued"


def test_external_action_policy_blocks_disallowed_actions():
    manager = ExternalActionManager(ActionPolicy(allowed_actions=frozenset({"email.send"})))
    action = manager.draft("calendar.delete", "event-1", {})

    assert action.status == "blocked"
    with pytest.raises(ValueError, match="cannot be approved"):
        manager.approve(action.id)
