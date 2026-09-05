"""Run status and human-in-the-loop requirements.

Patterns borrowed from agno (RunRequirement + RunStatus state machine) and
vercel/ai (HMAC-bound approvals). A run can be paused on one or more
`RunRequirement`s (confirmation, user input, feedback or external execution);
each is resolved independently and the run can only resume when all are resolved.

Wolfpack keeps this module provider-agnostic: approval storage/publishing is handled
by an `ApprovalStore` abstraction (local SQLite by default; the AMP Control Plane
when configured). The framework is fully usable without AMP.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class UserInputField:
    """A single field the human must provide (agno-style user_input_schema)."""

    def __init__(self, name: str, type: str = "text", description: str = "", required: bool = True, **extra: Any):
        self.name = name
        self.type = type
        self.description = description
        self.required = required
        self.extra = extra

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
            **self.extra,
        }


def _os_secret() -> Optional[str]:
    return os.environ.get("WOLFPACK_APPROVAL_SECRET")


class RunRequirement:
    """One outstanding human gate for a run.

    Mirrors the four agno gates:
      - confirmation       (approve/reject a sensitive action)
      - user_input         (collect typed fields before proceeding)
      - feedback           (let the human steer with options)
      - external_execution (await a result from an async/external executor)

    `is_resolved()` is False until every pending gate is satisfied.
    """

    def __init__(
        self,
        run_id: str,
        tool_call_id: str,
        tool_name: str,
        tool_arguments: Dict[str, Any],
        requirement: str = "confirmation",
        confirmation: Optional[bool] = None,
        confirmation_note: Optional[str] = None,
        user_input_schema: Optional[List[Any]] = None,
        user_input: Optional[Dict[str, Any]] = None,
        feedback_schema: Optional[List[Any]] = None,
        feedback: Optional[Dict[str, Any]] = None,
        external_execution_required: bool = False,
        external_execution_result: Optional[str] = None,
        approval_id: Optional[str] = None,
        signature: Optional[str] = None,
        status: str = "pending",
        id: Optional[str] = None,
        created_at: Optional[float] = None,
    ):
        self.id = id or uuid.uuid4().hex
        self.run_id = run_id
        self.tool_call_id = tool_call_id
        self.tool_name = tool_name
        self.tool_arguments = tool_arguments
        self.requirement = requirement
        self.confirmation = confirmation
        self.confirmation_note = confirmation_note
        self.user_input_schema = user_input_schema or []
        self.user_input = user_input
        self.feedback_schema = feedback_schema or []
        self.feedback = feedback
        self.external_execution_required = external_execution_required
        self.external_execution_result = external_execution_result
        self.status = status
        self.approval_id = approval_id
        self.signature = signature
        self.created_at = created_at if created_at is not None else time.time()

    # ----- gates -----

    @property
    def needs_confirmation(self) -> bool:
        return self.requirement == "confirmation" and self.confirmation is None and self.status == "pending"

    @property
    def needs_user_input(self) -> bool:
        return self.requirement == "user_input" and self.user_input is None and self.status == "pending"

    @property
    def needs_feedback(self) -> bool:
        return self.requirement == "feedback" and self.feedback is None and self.status == "pending"

    @property
    def needs_external_execution(self) -> bool:
        return (
            self.requirement == "external_execution"
            and self.external_execution_result is None
            and self.status == "pending"
        )

    def is_resolved(self) -> bool:
        if self.status != "pending":
            return True
        return not (
            self.needs_confirmation or self.needs_user_input or self.needs_feedback or self.needs_external_execution
        )

    def is_pending(self) -> bool:
        return not self.is_resolved()

    # ----- resolution mutators (updates signature state on approve/reject) -----

    def confirm(self, signed: bool = True) -> None:
        if self.requirement != "confirmation":
            raise ValueError(f"Requirement {self.id} is not a confirmation gate.")
        if signed and not self._signature_valid():
            self.status = "unauthorized"
            self.confirmation = False
            return
        self.confirmation = True
        self.status = "approved"

    def reject(self, note: Optional[str] = None) -> None:
        if self.requirement != "confirmation":
            raise ValueError(f"Requirement {self.id} is not a confirmation gate.")
        self.confirmation = False
        self.confirmation_note = note
        self.status = "rejected"

    def provide_user_input(self, values: Dict[str, Any]) -> None:
        if self.requirement != "user_input":
            raise ValueError(f"Requirement {self.id} is not a user_input gate.")
        self.user_input = values
        self.status = "resolved"

    def provide_feedback(self, values: Dict[str, Any]) -> None:
        if self.requirement != "feedback":
            raise ValueError(f"Requirement {self.id} is not a feedback gate.")
        self.feedback = values
        self.status = "resolved"

    def set_external_execution_result(self, result: str) -> None:
        if not self.external_execution_required:
            raise ValueError(f"Requirement {self.id} has no external execution gate.")
        self.external_execution_result = result
        self.status = "resolved"

    # ----- HMAC (vercel-style) to prevent forged/replayed approvals -----

    def _signing_secret(self) -> Optional[str]:
        return _os_secret()

    def _message(self) -> str:
        return json.dumps(
            {
                "approval_id": self.approval_id,
                "tool_call_id": self.tool_call_id,
                "tool_name": self.tool_name,
                "args": self.tool_arguments,
            },
            sort_keys=True,
        )

    def _signature_valid(self) -> bool:
        secret = self._signing_secret()
        if not secret:
            return True  # no secret configured -> skip verification (trust the store)
        if not self.signature:
            return False
        expected = hmac.new(secret.encode(), self._message().encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, self.signature)

    def sign(self, secret: str) -> str:
        sig = hmac.new(secret.encode(), self._message().encode(), hashlib.sha256).hexdigest()
        self.signature = sig
        return sig

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "tool_call_id": self.tool_call_id,
            "tool_name": self.tool_name,
            "tool_arguments": self.tool_arguments,
            "requirement": self.requirement,
            "confirmation": self.confirmation,
            "confirmation_note": self.confirmation_note,
            "user_input_schema": [u.to_dict() if hasattr(u, "to_dict") else u for u in self.user_input_schema],
            "user_input": self.user_input,
            "feedback_schema": [f.to_dict() if hasattr(f, "to_dict") else f for f in self.feedback_schema],
            "feedback": self.feedback,
            "external_execution_required": self.external_execution_required,
            "external_execution_result": self.external_execution_result,
            "status": self.status,
            "approval_id": self.approval_id,
            "signature": self.signature,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunRequirement":
        return cls(**data)


# Alias to keep the name used by the AMP contract.
RequestInputField = UserInputField