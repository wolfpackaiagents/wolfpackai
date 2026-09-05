"""add operational and framework alerts

Revision ID: 0007_alerts
Revises: 0006_privacy
Create Date: 2026-08-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_alerts"
down_revision: Union[str, None] = "0006_privacy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("project_id", sa.String(length=32), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("ingestion_job_id", sa.String(length=32), sa.ForeignKey("ingestion_jobs.id"), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), server_default="warning", nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_alerts_project_created", "alerts", ["project_id", "created_at"])
    op.create_index("ix_alerts_project_source", "alerts", ["project_id", "source"])


def downgrade() -> None:
    op.drop_index("ix_alerts_project_source", table_name="alerts")
    op.drop_index("ix_alerts_project_created", table_name="alerts")
    op.drop_table("alerts")
