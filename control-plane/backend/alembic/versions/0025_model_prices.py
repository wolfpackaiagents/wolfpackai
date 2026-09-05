"""add model_prices table for catalog-based cost estimation"""

from alembic import op
import sqlalchemy as sa
from datetime import timezone

revision = "0025_model_prices"
down_revision = "0024_provider_secrets"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("model_prices"):
        op.create_table(
            "model_prices",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("model_key", sa.String(255), unique=True, nullable=False, index=True),
            sa.Column("provider", sa.String(64), nullable=False),
            sa.Column("input_price_per_1k", sa.Float(), nullable=False),
            sa.Column("output_price_per_1k", sa.Float(), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    now = "2025-08-01T00:00:00+00:00"
    seed_data = [
        {"model_key": "gpt-4o", "provider": "openai", "input_price_per_1k": 0.0025, "output_price_per_1k": 0.01, "currency": "USD"},
        {"model_key": "gpt-4o-mini", "provider": "openai", "input_price_per_1k": 0.00015, "output_price_per_1k": 0.0006, "currency": "USD"},
        {"model_key": "claude-sonnet-4-20250514", "provider": "anthropic", "input_price_per_1k": 0.003, "output_price_per_1k": 0.015, "currency": "USD"},
        {"model_key": "claude-haiku-3-5-20241022", "provider": "anthropic", "input_price_per_1k": 0.0008, "output_price_per_1k": 0.004, "currency": "USD"},
        {"model_key": "gemini-2.0-flash", "provider": "google", "input_price_per_1k": 0.0001, "output_price_per_1k": 0.0004, "currency": "USD"},
        {"model_key": "gemini-2.0-flash-lite", "provider": "google", "input_price_per_1k": 0.000075, "output_price_per_1k": 0.0003, "currency": "USD"},
        {"model_key": "gemini-2.5-pro-exp-03-25", "provider": "google", "input_price_per_1k": 0.00125, "output_price_per_1k": 0.005, "currency": "USD"},
    ]
    bind = op.get_bind()
    for row in seed_data:
        existing = bind.execute(
            sa.text("SELECT 1 FROM model_prices WHERE model_key = :model_key"),
            {"model_key": row["model_key"]},
        ).fetchone()
        if not existing:
            bind.execute(
                sa.text(
                    """INSERT INTO model_prices (id, model_key, provider, input_price_per_1k, output_price_per_1k, currency, updated_at)
                       VALUES (md5(random()::text || clock_timestamp()::text), :model_key, :provider, :input_price_per_1k, :output_price_per_1k, :currency, :updated_at)"""
                ),
                {"model_key": row["model_key"], "provider": row["provider"], "input_price_per_1k": row["input_price_per_1k"], "output_price_per_1k": row["output_price_per_1k"], "currency": row["currency"], "updated_at": now},
            )


def downgrade():
    op.drop_table("model_prices")