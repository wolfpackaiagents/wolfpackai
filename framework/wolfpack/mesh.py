"""Stable deployment identity for a Wolfpack execution registered in AMP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class MeshIdentity:
    """Links runtime telemetry to an immutable AMP environment registration."""

    environment_id: str
    environment_slug: str
    registration_id: str
    definition_key: str
    definition_version: str
    policy_hash: str | None = None
    trigger_type: str = "interactive"

    def metadata(self) -> Dict[str, str]:
        values = {
            "environment_id": self.environment_id,
            "environment_slug": self.environment_slug,
            "registration_id": self.registration_id,
            "definition_key": self.definition_key,
            "definition_version": self.definition_version,
            "trigger_type": self.trigger_type,
        }
        if self.policy_hash:
            values["policy_hash"] = self.policy_hash
        return values
