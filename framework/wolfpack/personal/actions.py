"""Draft-first external actions with policy checks and explicit approval."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, Optional


@dataclass(frozen=True)
class ActionPolicy:
    """Local policy for actions a personal agent may propose or execute."""

    allowed_actions: Optional[FrozenSet[str]] = None
    approval_required: bool = True

    def permits(self, action_type: str) -> bool:
        return self.allowed_actions is None or action_type in self.allowed_actions


@dataclass
class ExternalAction:
    """A proposed external side effect; it cannot execute while only drafted."""

    id: str
    action_type: str
    target: str
    payload: Dict[str, Any]
    policy: ActionPolicy
    status: str
    rationale: Optional[str] = None
    approval_note: Optional[str] = None
    result: Any = None


class ExternalActionManager:
    """Keeps external work as inspectable drafts until policy allows execution."""

    def __init__(self, policy: ActionPolicy, *, id_factory: Optional[Callable[[], str]] = None):
        self.policy = policy
        self._id_factory = id_factory or self._default_id
        self._next_id = 0
        self._actions: Dict[str, ExternalAction] = {}

    def draft(self, action_type: str, target: str, payload: Dict[str, Any], *, rationale: Optional[str] = None) -> ExternalAction:
        if not action_type or not target:
            raise ValueError("action_type and target must be non-empty.")
        status = "blocked" if not self.policy.permits(action_type) else ("pending_approval" if self.policy.approval_required else "approved")
        action = ExternalAction(self._id_factory(), action_type, target, dict(payload), self.policy, status, rationale)
        self._actions[action.id] = action
        return action

    def approve(self, action_id: str, *, note: Optional[str] = None) -> ExternalAction:
        action = self._get(action_id)
        if action.status != "pending_approval":
            raise ValueError(f"Action {action_id} cannot be approved from status {action.status}.")
        action.status = "approved"
        action.approval_note = note
        return action

    def reject(self, action_id: str, *, note: Optional[str] = None) -> ExternalAction:
        action = self._get(action_id)
        if action.status not in {"pending_approval", "approved"}:
            raise ValueError(f"Action {action_id} cannot be rejected from status {action.status}.")
        action.status = "rejected"
        action.approval_note = note
        return action

    def execute(self, action_id: str, executor: Callable[[ExternalAction], Any]) -> ExternalAction:
        action = self._get(action_id)
        if action.status != "approved":
            raise PermissionError(f"Action {action_id} must be approved before execution.")
        if not action.policy.permits(action.action_type):
            action.status = "blocked"
            raise PermissionError(f"Action type {action.action_type!r} is blocked by policy.")
        action.result = executor(action)
        action.status = "executed"
        return action

    def get(self, action_id: str) -> Optional[ExternalAction]:
        return self._actions.get(action_id)

    def _get(self, action_id: str) -> ExternalAction:
        action = self.get(action_id)
        if action is None:
            raise KeyError(f"No action with id={action_id}")
        return action

    def _default_id(self) -> str:
        self._next_id += 1
        return f"action-{self._next_id}"
