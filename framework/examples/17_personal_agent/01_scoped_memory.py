"""Deterministic scoped personal memory without a model or external service.

Run with: uv run python examples/17_personal_agent/01_scoped_memory.py
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wolfpack.memory import MemoryConsent, MemoryProvenance, ScopedPersonalMemory


def main() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    memory = ScopedPersonalMemory(now=lambda: now)
    consent = MemoryConsent(True, "personal planning", now)
    provenance = MemoryProvenance("user", "conversation-17", now)

    memory.remember_profile("alex", "planning", "timezone", "America/Sao_Paulo", consent=consent, provenance=provenance)
    memory.remember_fact("alex", "planning", "coffee", "prefers decaf", consent=consent, provenance=provenance, ttl=timedelta(days=7))
    memory.remember_fact("alex", "health", "coffee", "not shared with planning", consent=consent, provenance=provenance)

    print(memory.get("alex", "planning", "timezone").value)
    print(memory.get("alex", "planning", "coffee").value)
    print(memory.get("alex", "health", "coffee").value)
    print(memory.forget("alex", "planning", key="coffee"))
    print(memory.get("alex", "planning", "coffee"))


if __name__ == "__main__":
    main()
