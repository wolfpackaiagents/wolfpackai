"""add schedule capability policies and decision audit

Revision ID: 0017_schedule_policies
Revises: 0017_schedules
"""

from alembic import op
import sqlalchemy as sa


revision = "0017_schedule_policies"
down_revision = "0017_schedules"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    project_columns = {column["name"] for column in inspector.get_columns("projects")}
    if "schedule_policy" not in project_columns:
        op.add_column("projects", sa.Column("schedule_policy", sa.JSON(), nullable=True))
    registration_columns = {column["name"] for column in inspector.get_columns("environment_registrations")}
    if "schedule_policy" not in registration_columns:
        op.add_column("environment_registrations", sa.Column("schedule_policy", sa.JSON(), nullable=True))
    if not inspector.has_table("policy_decision_audits"):
        op.create_table(
            "policy_decision_audits",
            sa.Column("id", sa.String(length=32), primary_key=True),
            sa.Column("project_id", sa.String(length=32), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("registration_id", sa.String(length=32), sa.ForeignKey("environment_registrations.id"), nullable=True),
            sa.Column("action", sa.String(length=32), nullable=False),
            sa.Column("decision", sa.String(length=24), nullable=False),
            sa.Column("reasons", sa.JSON(), nullable=False),
            sa.Column("request", sa.JSON(), nullable=False),
            sa.Column("policy", sa.JSON(), nullable=False),
            sa.Column("approval_id", sa.String(length=64), nullable=True),
            sa.Column("actor_api_key_id", sa.String(length=32), sa.ForeignKey("api_keys.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    indexes = {index["name"] for index in inspector.get_indexes("policy_decision_audits")}
    if "ix_policy_decision_audits_project_created" not in indexes:
        op.create_index("ix_policy_decision_audits_project_created", "policy_decision_audits", ["project_id", "created_at"])
    if "ix_policy_decision_audits_registration_created" not in indexes:
        op.create_index("ix_policy_decision_audits_registration_created", "policy_decision_audits", ["registration_id", "created_at"])


def downgrade():
    op.drop_index("ix_policy_decision_audits_registration_created", table_name="policy_decision_audits")
    op.drop_index("ix_policy_decision_audits_project_created", table_name="policy_decision_audits")
    op.drop_table("policy_decision_audits")
    op.drop_column("environment_registrations", "schedule_policy")
    op.drop_column("projects", "schedule_policy")
