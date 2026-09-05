"""add approvals table

Revision ID: 0002_approvals
Revises: 0001_wolfpack_init
Create Date: 2026-08-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_approvals"
down_revision: Union[str, None] = "0001_wolfpack_init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "approvals",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("approval_id", sa.String(64), unique=True, index=True, nullable=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("trace_id", sa.String(64), sa.ForeignKey("traces.id"), nullable=True),
        sa.Column("tool_call_id", sa.String(64), nullable=True),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column("requirement", sa.String(32), server_default="confirmation", nullable=False),
        sa.Column("status", sa.String(24), server_default="pending", nullable=False),
        sa.Column("tool_arguments", sa.JSON(), nullable=True),
        sa.Column("confirmation", sa.Boolean(), nullable=True),
        sa.Column("confirmation_note", sa.Text(), nullable=True),
        sa.Column("user_input", sa.JSON(), nullable=True),
        sa.Column("feedback", sa.JSON(), nullable=True),
        sa.Column("resolved_by", sa.String(128), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
    )
    op.create_index("ix_approvals_trace", "approvals", ["trace_id"])
    op.create_index("ix_approvals_status", "approvals", ["project_id", "status"])
    op.create_index("ix_approvals_created", "approvals", ["project_id", "created_at"])


def downgrade() -> None:
    op.drop_table("approvals")