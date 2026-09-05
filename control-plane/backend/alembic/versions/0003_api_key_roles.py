"""add API key roles

Revision ID: 0003_api_key_roles
Revises: 0002_approvals
Create Date: 2026-08-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_api_key_roles"
down_revision: Union[str, None] = "0002_approvals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("role", sa.String(length=20), server_default="admin", nullable=False))
    op.alter_column("api_keys", "role", server_default="editor")


def downgrade() -> None:
    op.drop_column("api_keys", "role")
