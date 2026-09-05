from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index, String

from ..core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ModelPrice(Base):
    __tablename__ = "model_prices"
    __table_args__ = (Index("ix_model_prices_model_key", "model_key"),)

    id = Column(String(32), primary_key=True)
    model_key = Column(String(255), unique=True, nullable=False)
    provider = Column(String(64), nullable=False)
    input_price_per_1k = Column(Float, nullable=False)
    output_price_per_1k = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, server_default="USD")
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now)