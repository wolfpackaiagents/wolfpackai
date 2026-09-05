"""add expiring Mesh registration heartbeats

Revision ID: 0016_registration_heartbeats
Revises: 0015_governance_roles
"""

from alembic import op
import sqlalchemy as sa


revision = "0016_registration_heartbeats"
down_revision = "0015_governance_roles"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("registration_heartbeats"):
        op.create_table(
            "registration_heartbeats",
            sa.Column("id", sa.String(length=32), primary_key=True),
            sa.Column("project_id", sa.String(length=32), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("registration_id", sa.String(length=32), sa.ForeignKey("environment_registrations.id"), nullable=False),
            sa.Column("instance_id", sa.String(length=128), nullable=False),
            sa.Column("version", sa.String(length=64), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("registration_id", "instance_id", name="uq_registration_heartbeats_registration_instance"),
        )
    if "ix_registration_heartbeats_registration_seen" not in {index["name"] for index in inspector.get_indexes("registration_heartbeats")}:
        op.create_index("ix_registration_heartbeats_registration_seen", "registration_heartbeats", ["registration_id", "last_seen"])


def downgrade():
    op.drop_index("ix_registration_heartbeats_registration_seen", table_name="registration_heartbeats")
    op.drop_table("registration_heartbeats")
