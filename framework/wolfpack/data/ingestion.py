"""Explicit conversion of structured source rows into Knowledge documents."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Iterable

from ..knowledge.knowledge import Knowledge


def ingest_rows(knowledge: Knowledge, rows: Iterable[dict[str, Any]], *, source_id: str, cursor: str | None = None) -> int:
    """Index a snapshot of structured rows without implying live-source freshness."""
    count = 0
    for row in rows:
        content = json.dumps(row, sort_keys=True, default=str)
        metadata = {
            "source_id": source_id,
            "content_hash": sha256(content.encode()).hexdigest(),
            "sync_cursor": cursor,
            "source_kind": "structured_snapshot",
        }
        knowledge.add_text(content, metadata=metadata, chunk=False)
        count += 1
    return count
