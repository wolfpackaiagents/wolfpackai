"""add durable channel sessions and delivery receipts"""
from alembic import op
import sqlalchemy as sa

revision = "0020_channels"
down_revision = "0019_schedule_endpoint"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("channel_sessions"):
        op.create_table("channel_sessions", sa.Column("id", sa.String(32), primary_key=True), sa.Column("project_id", sa.String(32), nullable=False), sa.Column("channel", sa.String(64), nullable=False), sa.Column("scoped_key", sa.String(255), nullable=False), sa.Column("session_id", sa.String(64), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("project_id", "channel", "scoped_key", name="uq_channel_session_scope"))
    if not inspector.has_table("channel_deliveries"):
        op.create_table("channel_deliveries", sa.Column("id", sa.String(32), primary_key=True), sa.Column("project_id", sa.String(32), nullable=False), sa.Column("channel", sa.String(64), nullable=False), sa.Column("idempotency_key", sa.String(255), nullable=False), sa.Column("session_id", sa.String(64), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("provider_message_id", sa.String(255)), sa.Column("error", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("project_id", "idempotency_key", name="uq_channel_delivery_idempotency"))


def downgrade():
    op.drop_table("channel_deliveries")
    op.drop_table("channel_sessions")
