"""Alembic migration integration test — runs migrations against a temporary PostgreSQL database.

Requires a running PostgreSQL (e.g. via `docker compose -f docker/docker-compose.yml up -d postgres`).
Skips automatically if no database connection is available.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool


@pytest.mark.skipif(
    not os.environ.get("POSTGRES_TEST_URL"),
    reason="POSTGRES_TEST_URL not set (e.g. postgresql://wolfpack:wolfpack@localhost:5439/wolfpack)"
)
def test_alembic_upgrade_to_head():
    """Upgrade an empty PostgreSQL database to the latest migration head."""
    database_url = os.environ["POSTGRES_TEST_URL"]
    from alembic.config import Config as AlembicConfig
    from alembic.command import upgrade as alembic_upgrade

    base = os.path.join(os.path.dirname(__file__), "..")
    alembic_cfg = AlembicConfig(os.path.join(base, "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    alembic_cfg.set_main_option("script_location", os.path.join(base, "alembic"))

    engine = create_engine(database_url, poolclass=NullPool)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    engine.dispose()

    alembic_upgrade(alembic_cfg, "head")

    engine = create_engine(database_url, poolclass=NullPool)
    with engine.begin() as conn:
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        version = result.scalar()
        assert version is not None, "alembic_version not set after upgrade"

        result = conn.execute(text("SELECT COUNT(*) FROM model_prices"))
        count = result.scalar()
        assert count == 7, f"Expected 7 seed prices, got {count}"

        result = conn.execute(text("SELECT id FROM model_prices LIMIT 1"))
        price_id = result.scalar()
        assert price_id is not None and len(price_id) == 32, f"Price ID must be 32 chars, got {price_id!r} (len {len(price_id) if price_id else 0})"
    engine.dispose()