"""scope approval identifiers to projects

Revision ID: 0008_approval_project_uniqueness
Revises: 0007_alerts
Create Date: 2026-08-23
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0008_approval_project_uniqueness"
down_revision: Union[str, None] = "0007_alerts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE approvals DROP CONSTRAINT IF EXISTS approvals_approval_id_key")
    op.create_unique_constraint("uq_approvals_project_approval_id", "approvals", ["project_id", "approval_id"])


def downgrade() -> None:
    op.drop_constraint("uq_approvals_project_approval_id", "approvals", type_="unique")
    op.create_unique_constraint("approvals_approval_id_key", "approvals", ["approval_id"])
