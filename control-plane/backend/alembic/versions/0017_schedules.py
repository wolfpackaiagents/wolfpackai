"""add durable schedules and scheduled task runs

Revision ID: 0017_schedules
Revises: 0016_registration_heartbeats
"""

from alembic import op
import sqlalchemy as sa


revision = "0017_schedules"
down_revision = "0016_registration_heartbeats"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("schedules"):
        op.create_table(
        "schedules",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("project_id", sa.String(length=32), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("registration_id", sa.String(length=32), sa.ForeignKey("environment_registrations.id"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("schedule_type", sa.String(length=16), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True)),
        sa.Column("interval_seconds", sa.Integer()),
        sa.Column("cron", sa.String(length=128)),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("retry_delay_seconds", sa.Integer(), nullable=False),
        sa.Column("misfire_policy", sa.String(length=16), nullable=False),
        sa.Column("misfire_grace_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paused_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("project_id", "name", name="uq_schedules_project_name"),
        )
    schedule_indexes = {index["name"] for index in inspector.get_indexes("schedules")}
    if "ix_schedules_project_status_next" not in schedule_indexes:
        op.create_index("ix_schedules_project_status_next", "schedules", ["project_id", "status", "next_run_at"])
    if "ix_schedules_registration" not in schedule_indexes:
        op.create_index("ix_schedules_registration", "schedules", ["registration_id"])
    if not inspector.has_table("scheduled_task_runs"):
        op.create_table(
        "scheduled_task_runs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("project_id", sa.String(length=32), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("schedule_id", sa.String(length=32), sa.ForeignKey("schedules.id"), nullable=False),
        sa.Column("registration_id", sa.String(length=32), sa.ForeignKey("environment_registrations.id"), nullable=False),
        sa.Column("occurrence_key", sa.String(length=160), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("retry_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("result", sa.JSON()),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("schedule_id", "occurrence_key", name="uq_scheduled_task_runs_schedule_occurrence"),
        )
    run_indexes = {index["name"] for index in inspector.get_indexes("scheduled_task_runs")}
    if "ix_scheduled_task_runs_project_status" not in run_indexes:
        op.create_index("ix_scheduled_task_runs_project_status", "scheduled_task_runs", ["project_id", "status", "scheduled_for"])
    if "ix_scheduled_task_runs_schedule_scheduled" not in run_indexes:
        op.create_index("ix_scheduled_task_runs_schedule_scheduled", "scheduled_task_runs", ["schedule_id", "scheduled_for"])


def downgrade():
    op.drop_index("ix_scheduled_task_runs_schedule_scheduled", table_name="scheduled_task_runs")
    op.drop_index("ix_scheduled_task_runs_project_status", table_name="scheduled_task_runs")
    op.drop_table("scheduled_task_runs")
    op.drop_index("ix_schedules_registration", table_name="schedules")
    op.drop_index("ix_schedules_project_status_next", table_name="schedules")
    op.drop_table("schedules")
