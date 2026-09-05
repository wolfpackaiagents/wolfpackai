"""Evaluation of schedule capabilities without coupling to schedule persistence."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ..models.entities import Approval, PolicyDecisionAudit

SCHEDULE_ACTIONS = {"schedule.read", "schedule.create", "schedule.update", "schedule.cancel"}
DECISIONS = {"allow", "deny", "require_approval"}
DEFAULT_POLICY = {
    "decisions": {action: "allow" for action in sorted(SCHEDULE_ACTIONS)},
    "restrictions": {},
}


def normalize_policy(policy: dict[str, Any] | None) -> dict[str, Any]:
    """Return a complete policy, accepting stored partial registration overrides."""
    policy = policy or {}
    decisions = {**DEFAULT_POLICY["decisions"], **(policy.get("decisions") or {})}
    restrictions = {**(policy.get("restrictions") or {})}
    return {"decisions": decisions, "restrictions": restrictions}


def merge_policy(project_policy: dict[str, Any] | None, registration_policy: dict[str, Any] | None) -> dict[str, Any]:
    project = normalize_policy(project_policy)
    registration = registration_policy or {}
    return {
        "decisions": {**project["decisions"], **(registration.get("decisions") or {})},
        "restrictions": {**project["restrictions"], **(registration.get("restrictions") or {})},
    }


@dataclass(frozen=True)
class PolicyOutcome:
    decision: str
    reasons: list[str]
    policy: dict[str, Any]
    approval_id: str | None = None


class SchedulePolicyService:
    def __init__(self, db: Session, project_id: str, actor_api_key_id: str):
        self.db = db
        self.project_id = project_id
        self.actor_api_key_id = actor_api_key_id

    def decide(
        self,
        *,
        action: str,
        policy: dict[str, Any],
        registration_id: str | None,
        schedule_type: str | None,
        interval_seconds: int | None,
        active_schedule_count: int | None,
        schedule_id: str | None,
        metadata: dict[str, Any],
    ) -> PolicyOutcome:
        reasons: list[str] = []
        restrictions = policy["restrictions"]
        allowed_types = restrictions.get("allowed_types")
        if action in {"schedule.create", "schedule.update"} and allowed_types is not None and schedule_type not in allowed_types:
            reasons.append("schedule_type_not_allowed")
        if action in {"schedule.create", "schedule.update"} and active_schedule_count is not None and restrictions.get("max_active_schedules") is not None and active_schedule_count >= restrictions["max_active_schedules"]:
            reasons.append("max_active_schedules_reached")
        if action in {"schedule.create", "schedule.update"} and interval_seconds is not None and restrictions.get("min_interval_seconds") is not None and interval_seconds < restrictions["min_interval_seconds"]:
            reasons.append("interval_below_minimum")

        decision = "deny" if reasons else policy["decisions"][action]
        approval_id = None
        if decision == "require_approval":
            approval_id = f"schedule-policy-{uuid.uuid4().hex}"
            self.db.add(
                Approval(
                    id=uuid.uuid4().hex,
                    approval_id=approval_id,
                    project_id=self.project_id,
                    tool_name=action,
                    requirement="confirmation",
                    tool_arguments={
                        "schedule_id": schedule_id,
                        "schedule_type": schedule_type,
                        "interval_seconds": interval_seconds,
                        "active_schedule_count": active_schedule_count,
                    },
                    status="pending",
                    metadata_field={
                        "source": "schedule_policy",
                        "registration_id": registration_id,
                        "metadata": metadata,
                        "schedule_mutation": {"action": action, "schedule_id": schedule_id, "body": metadata.get("body"), "mutation": metadata.get("mutation")},
                    },
                )
            )

        self.db.add(
            PolicyDecisionAudit(
                project_id=self.project_id,
                registration_id=registration_id,
                action=action,
                decision=decision,
                reasons=reasons,
                request={
                    "schedule_id": schedule_id,
                    "schedule_type": schedule_type,
                    "interval_seconds": interval_seconds,
                    "active_schedule_count": active_schedule_count,
                    "metadata": metadata,
                },
                policy=policy,
                approval_id=approval_id,
                actor_api_key_id=self.actor_api_key_id if self.actor_api_key_id != "admin" else None,
            )
        )
        self.db.commit()
        return PolicyOutcome(decision=decision, reasons=reasons, policy=policy, approval_id=approval_id)
