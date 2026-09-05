"""add scheduler leases, fencing, and deadlines

Revision ID: 0018_scheduled_run_leases
Revises: 0017_schedule_policies
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_scheduled_run_leases"
down_revision = "0017_schedule_policies"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("scheduled_task_runs")}
    additions = {
        "lease_expires_at": sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        "fencing_token": sa.Column("fencing_token", sa.Integer(), nullable=False, server_default="0"),
        "claimed_by": sa.Column("claimed_by", sa.String(length=128), nullable=True),
        "deadline_at": sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column("scheduled_task_runs", column)
    indexes = {index["name"] for index in inspector.get_indexes("scheduled_task_runs")}
    if "ix_scheduled_task_runs_claimable" not in indexes:
        op.create_index("ix_scheduled_task_runs_claimable", "scheduled_task_runs", ["status", "retry_at", "lease_expires_at"])


def downgrade():
    op.drop_index("ix_scheduled_task_runs_claimable", table_name="scheduled_task_runs")
    op.drop_column("scheduled_task_runs", "deadline_at")
    op.drop_column("scheduled_task_runs", "claimed_by")
    op.drop_column("scheduled_task_runs", "fencing_token")
    op.drop_column("scheduled_task_runs", "lease_expires_at")
