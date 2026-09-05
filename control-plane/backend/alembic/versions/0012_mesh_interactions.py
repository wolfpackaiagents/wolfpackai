"""add Mesh runtime interactions

Revision ID: 0012_mesh_interactions
Revises: 0011_chat_runs
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_mesh_interactions"
down_revision = "0011_chat_runs"
branch_labels = None
depends_on = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table("mesh_interactions"):
        op.create_table(
            "mesh_interactions",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("trace_id", sa.String(64), sa.ForeignKey("traces.id"), nullable=True),
            sa.Column("source", sa.String(255), nullable=False),
            sa.Column("target", sa.String(255), nullable=False),
            sa.Column("interaction_type", sa.String(32), nullable=False, server_default="delegation"),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_mesh_interactions_project_created", "mesh_interactions", ["project_id", "created_at"])
        op.create_index("ix_mesh_interactions_project_edge", "mesh_interactions", ["project_id", "source", "target"])
        op.create_index("ix_mesh_interactions_trace", "mesh_interactions", ["trace_id"])


def downgrade():
    op.drop_table("mesh_interactions")
