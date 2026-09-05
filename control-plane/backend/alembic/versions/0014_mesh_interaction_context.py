"""add typed Mesh interaction context

Revision ID: 0014_mesh_interaction_context
Revises: 0013_eval_runs
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_mesh_interaction_context"
down_revision = "0013_eval_runs"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("mesh_interactions") as batch:
        batch.add_column(sa.Column("source_display_name", sa.String(255), nullable=True))
        batch.add_column(sa.Column("target_display_name", sa.String(255), nullable=True))
        batch.add_column(sa.Column("operation", sa.String(255), nullable=True))
        batch.add_column(sa.Column("tool_name", sa.String(255), nullable=True))


def downgrade():
    with op.batch_alter_table("mesh_interactions") as batch:
        batch.drop_column("tool_name")
        batch.drop_column("operation")
        batch.drop_column("target_display_name")
        batch.drop_column("source_display_name")
