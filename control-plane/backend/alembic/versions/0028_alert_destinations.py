"""add alert_destinations table for Slack, Discord, and SMTP notification targets"""
from alembic import op
import sqlalchemy as sa

revision = "0028_alert_destinations"
down_revision = "0027_chat_endpoint"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    if "alert_destinations" not in tables:
        op.create_table(
            "alert_destinations",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("destination_type", sa.String(32), nullable=False),
            sa.Column("config", sa.JSON, nullable=False),
            sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
            sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("project_id", "name", name="uq_alert_destinations_project_name"),
        )
        op.create_index("ix_alert_destinations_project_enabled", "alert_destinations", ["project_id", "enabled"])


def downgrade():
    op.drop_table("alert_destinations")