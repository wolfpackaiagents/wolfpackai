"""add durable private chat conversations and turns"""

from alembic import op
import sqlalchemy as sa


revision = "0026_chat_conversations"
down_revision = "0025_model_prices"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("chat_conversations"):
        op.create_table(
            "chat_conversations",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("project_id", sa.String(32), nullable=False),
            sa.Column("owner_api_key_id", sa.String(32), nullable=False),
            sa.Column("registration_id", sa.String(32), nullable=False),
            sa.Column("session_id", sa.String(64), nullable=False),
            sa.Column("title", sa.String(255)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True)),
        )
        op.create_index("ix_chat_conversations_owner_updated", "chat_conversations", ["project_id", "owner_api_key_id", "updated_at"])
        op.create_index("ix_chat_conversations_project_deleted", "chat_conversations", ["project_id", "deleted_at"])
    if not inspector.has_table("chat_turns"):
        op.create_table(
            "chat_turns",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("project_id", sa.String(32), nullable=False),
            sa.Column("conversation_id", sa.String(32), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("idempotency_key", sa.String(128)),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("output", sa.Text()),
            sa.Column("trace_id", sa.String(64)),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True)),
            sa.Column("completed_at", sa.DateTime(timezone=True)),
            sa.Column("error", sa.Text()),
            sa.Column("chat_run_id", sa.String(32), unique=True),
            sa.UniqueConstraint("conversation_id", "sequence", name="uq_chat_turns_conversation_sequence"),
            sa.UniqueConstraint("conversation_id", "idempotency_key", name="uq_chat_turns_conversation_idempotency"),
        )
        op.create_index("ix_chat_turns_conversation_created", "chat_turns", ["conversation_id", "created_at"])

    chat_run_columns = {column["name"] for column in sa.inspect(bind).get_columns("chat_runs")}
    for name, column in (
        ("conversation_id", sa.Column("conversation_id", sa.String(32))),
        ("turn_id", sa.Column("turn_id", sa.String(32))),
        ("idempotency_key", sa.Column("idempotency_key", sa.String(128))),
        ("started_at", sa.Column("started_at", sa.DateTime(timezone=True))),
        ("completed_at", sa.Column("completed_at", sa.DateTime(timezone=True))),
        ("error", sa.Column("error", sa.Text())),
    ):
        if name not in chat_run_columns:
            op.add_column("chat_runs", column)
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("chat_runs")}
    if "ix_chat_runs_conversation_created" not in indexes:
        op.create_index("ix_chat_runs_conversation_created", "chat_runs", ["conversation_id", "created_at"])


def downgrade():
    op.drop_index("ix_chat_runs_conversation_created", table_name="chat_runs")
    for name in ("error", "completed_at", "started_at", "idempotency_key", "turn_id", "conversation_id"):
        op.drop_column("chat_runs", name)
    op.drop_table("chat_turns")
    op.drop_table("chat_conversations")
