"""add score configurations

Revision ID: 0005_score_configs
Revises: 0004_ingestion_jobs
Create Date: 2026-08-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_score_configs"
down_revision: Union[str, None] = "0004_ingestion_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "score_configs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=32), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("data_type", sa.String(length=16), server_default="NUMERIC", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "name", name="uq_score_config_name"),
    )


def downgrade() -> None:
    op.drop_table("score_configs")
