"""add project privacy configuration and privacy audit logs

Revision ID: 0006_privacy
Revises: 0005_score_configs
Create Date: 2026-08-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_privacy"
down_revision: Union[str, None] = "0005_score_configs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("pii_redaction_config", sa.JSON(), nullable=True))
    op.create_table(
        "privacy_audit_logs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("project_id", sa.String(length=32), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("subject_hash", sa.String(length=64), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_privacy_audit_logs_project_created", "privacy_audit_logs", ["project_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_privacy_audit_logs_project_created", table_name="privacy_audit_logs")
    op.drop_table("privacy_audit_logs")
    op.drop_column("projects", "pii_redaction_config")
