"""Optional AMP score publishing client."""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Dict, Optional

from .runner import EvalScore


class AmpScorePublisher:
    """Publishes evaluation scores to the AMP public API."""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def publish(self, trace_id: str, score: EvalScore) -> None:
        payload: Dict[str, Any] = {
            "trace_id": trace_id,
            "name": score.name,
            "source": "EVAL",
        }
        if isinstance(score.value, float):
            payload["value"] = score.value
        else:
            payload["string_value"] = score.value
        if score.comment is not None:
            payload["comment"] = score.comment
        self._post("/scores", payload)

    def _post(self, path: str, payload: Dict[str, Any]) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/api/public{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "X-API-Key": self.api_key or ""},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10):
            pass
