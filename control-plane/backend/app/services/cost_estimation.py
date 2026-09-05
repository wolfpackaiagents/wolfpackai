"""Catalog-based cost estimation using the model_prices table.

Follows the Langfuse approach: when the provider does not return a cost in the
response, the platform estimates it from a curated price catalog stored in the
model_prices table.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models.model_price import ModelPrice

logger = logging.getLogger(__name__)


def estimate_cost(db: Session, model_key: str, input_tokens: int, output_tokens: int) -> Optional[dict[str, Any]]:
    if not model_key or (not input_tokens and not output_tokens):
        return None

    price_row: Optional[ModelPrice] = db.query(ModelPrice).filter(ModelPrice.model_key == model_key).first()
    if price_row is None:
        return None

    input_cost = (input_tokens / 1000.0) * price_row.input_price_per_1k
    output_cost = (output_tokens / 1000.0) * price_row.output_price_per_1k
    total_cost = round(input_cost + output_cost, 10)

    return {
        "cost": total_cost,
        "cost_currency": price_row.currency,
        "cost_source": "catalog_estimated",
    }