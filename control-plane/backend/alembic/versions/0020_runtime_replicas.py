"""add operator-authorized HTTP runtime replicas

Revision ID: 0020_runtime_replicas
Revises: 0019_schedule_endpoint
"""

from alembic import op
import sqlalchemy as sa


revision = "0020_runtime_replicas"
down_revision = "0019_schedule_endpoint"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("runtime_replicas"):
        return
    op.create_table(
        "runtime_replicas",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("registration_id", sa.String(32), sa.ForeignKey("environment_registrations.id"), nullable=False),
        sa.Column("instance_id", sa.String(128), nullable=False),
        sa.Column("endpoint", sa.String(2048), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("registration_id", "instance_id", name="uq_runtime_replicas_registration_instance"),
    )
    op.create_index("ix_runtime_replicas_registration_enabled", "runtime_replicas", ["registration_id", "enabled"])


def downgrade():
    op.drop_index("ix_runtime_replicas_registration_enabled", table_name="runtime_replicas")
    op.drop_table("runtime_replicas")
