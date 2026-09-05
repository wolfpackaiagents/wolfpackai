"""Periodic price updater that refreshes the model_prices catalog.

Follows Langfuse approach: a background worker checks for updated pricing from a
known source. For now uses a hardcoded fallback dict.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..models.model_price import ModelPrice

logger = logging.getLogger(__name__)

HARDCODED_PRICES: dict[str, dict[str, Any]] = {
    "gpt-4o": {"provider": "openai", "input_price_per_1k": 0.0025, "output_price_per_1k": 0.01, "currency": "USD"},
    "gpt-4o-mini": {"provider": "openai", "input_price_per_1k": 0.00015, "output_price_per_1k": 0.0006, "currency": "USD"},
    "gpt-4.1": {"provider": "openai", "input_price_per_1k": 0.002, "output_price_per_1k": 0.008, "currency": "USD"},
    "gpt-4.1-mini": {"provider": "openai", "input_price_per_1k": 0.0004, "output_price_per_1k": 0.0016, "currency": "USD"},
    "gpt-4.1-nano": {"provider": "openai", "input_price_per_1k": 0.0001, "output_price_per_1k": 0.0004, "currency": "USD"},
    "o1": {"provider": "openai", "input_price_per_1k": 0.015, "output_price_per_1k": 0.06, "currency": "USD"},
    "o3-mini": {"provider": "openai", "input_price_per_1k": 0.0011, "output_price_per_1k": 0.0044, "currency": "USD"},
    "o4-mini": {"provider": "openai", "input_price_per_1k": 0.0011, "output_price_per_1k": 0.0044, "currency": "USD"},
    "claude-sonnet-4-20250514": {"provider": "anthropic", "input_price_per_1k": 0.003, "output_price_per_1k": 0.015, "currency": "USD"},
    "claude-4-5-sonnet-20250620": {"provider": "anthropic", "input_price_per_1k": 0.003, "output_price_per_1k": 0.015, "currency": "USD"},
    "claude-haiku-3-5-20241022": {"provider": "anthropic", "input_price_per_1k": 0.0008, "output_price_per_1k": 0.004, "currency": "USD"},
    "gemini-2.0-flash": {"provider": "google", "input_price_per_1k": 0.0001, "output_price_per_1k": 0.0004, "currency": "USD"},
    "gemini-2.0-flash-lite": {"provider": "google", "input_price_per_1k": 0.000075, "output_price_per_1k": 0.0003, "currency": "USD"},
    "gemini-2.5-pro-exp-03-25": {"provider": "google", "input_price_per_1k": 0.00125, "output_price_per_1k": 0.005, "currency": "USD"},
}


def check_and_update_prices(db: Session) -> int:
    now = datetime.now(timezone.utc)
    updated = 0

    for model_key, prices in HARDCODED_PRICES.items():
        existing: ModelPrice | None = db.query(ModelPrice).filter(ModelPrice.model_key == model_key).first()
        if existing is None:
            db.add(ModelPrice(
                id=uuid.uuid4().hex[:32],
                model_key=model_key,
                provider=prices["provider"],
                input_price_per_1k=prices["input_price_per_1k"],
                output_price_per_1k=prices["output_price_per_1k"],
                currency=prices["currency"],
                updated_at=now,
            ))
            logger.info("price_updater: added model_key=%s", model_key)
            updated += 1
        else:
            changed = False
            if existing.input_price_per_1k != prices["input_price_per_1k"]:
                existing.input_price_per_1k = prices["input_price_per_1k"]
                changed = True
            if existing.output_price_per_1k != prices["output_price_per_1k"]:
                existing.output_price_per_1k = prices["output_price_per_1k"]
                changed = True
            if existing.currency != prices["currency"]:
                existing.currency = prices["currency"]
                changed = True
            if changed:
                existing.updated_at = now
                logger.info("price_updater: updated model_key=%s", model_key)
                updated += 1

    if updated:
        db.commit()
    return updated