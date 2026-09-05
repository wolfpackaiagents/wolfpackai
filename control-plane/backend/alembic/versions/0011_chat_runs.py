"""add scoped Chat runs"""
from alembic import op
import sqlalchemy as sa
revision="0011_chat_runs"; down_revision="0010_trace_mesh_scope"; branch_labels=None; depends_on=None
def upgrade():
    if not sa.inspect(op.get_bind()).has_table("chat_runs"):
        op.create_table("chat_runs", sa.Column("id", sa.String(32), primary_key=True), sa.Column("project_id", sa.String(32), nullable=False), sa.Column("registration_id", sa.String(32), nullable=False), sa.Column("session_id", sa.String(64), nullable=False), sa.Column("message", sa.Text(), nullable=False), sa.Column("output", sa.Text()), sa.Column("trace_id", sa.String(64)), sa.Column("status", sa.String(20), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
        op.create_index("ix_chat_runs_project_created", "chat_runs", ["project_id", "created_at"])
def downgrade():
    op.drop_table("chat_runs")
