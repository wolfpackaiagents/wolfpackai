"""add managed alert rules and alert lifecycle

Revision ID: 0012_managed_alert_rules
Revises: 0011_chat_runs
Create Date: 2026-08-23
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_managed_alert_rules"
down_revision = "0011_chat_runs"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    alert_columns = {column["name"] for column in inspector.get_columns("alerts")}
    for name, column in (
        ("status", sa.Column("status", sa.String(length=16), nullable=False, server_default="open")),
        ("acknowledged_at", sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True)),
        ("resolved_at", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True)),
        ("resolved_by", sa.Column("resolved_by", sa.String(length=128), nullable=True)),
    ):
        if name not in alert_columns:
            op.add_column("alerts", column)
    if not inspector.has_table("alert_rules"):
        op.create_table(
            "alert_rules",
            sa.Column("id", sa.String(length=32), primary_key=True),
            sa.Column("project_id", sa.String(length=32), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("source", sa.String(length=32), nullable=True),
            sa.Column("event_type", sa.String(length=64), nullable=True),
            sa.Column("severity", sa.String(length=16), nullable=False, server_default="warning"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("project_id", "name", name="uq_alert_rules_project_name"),
        )
    if "ix_alert_rules_project_enabled" not in {index["name"] for index in inspector.get_indexes("alert_rules")}:
        op.create_index("ix_alert_rules_project_enabled", "alert_rules", ["project_id", "enabled"])


def downgrade():
    op.drop_index("ix_alert_rules_project_enabled", table_name="alert_rules")
    op.drop_table("alert_rules")
    op.drop_column("alerts", "resolved_by")
    op.drop_column("alerts", "resolved_at")
    op.drop_column("alerts", "acknowledged_at")
    op.drop_column("alerts", "status")
