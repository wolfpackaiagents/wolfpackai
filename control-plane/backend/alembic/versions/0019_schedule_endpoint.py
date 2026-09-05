"""add administratively configured schedule dispatch endpoint

Revision ID: 0019_schedule_endpoint
Revises: 0018_scheduled_run_leases
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_schedule_endpoint"
down_revision = "0018_scheduled_run_leases"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("environment_registrations")}
    if "schedule_endpoint" not in columns:
        op.add_column("environment_registrations", sa.Column("schedule_endpoint", sa.String(length=2048), nullable=True))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if "schedule_endpoint" in {column["name"] for column in inspector.get_columns("environment_registrations")}:
        op.drop_column("environment_registrations", "schedule_endpoint")
