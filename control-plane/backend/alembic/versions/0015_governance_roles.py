"""persist project governance role permissions

Revision ID: 0015_governance_roles
Revises: 0014_mesh_interaction_context
"""

from alembic import op
import sqlalchemy as sa


revision = "0015_governance_roles"
down_revision = "0014_mesh_interaction_context"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("projects")}
    if "governance_roles" not in columns:
        op.add_column("projects", sa.Column("governance_roles", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("projects", "governance_roles")
