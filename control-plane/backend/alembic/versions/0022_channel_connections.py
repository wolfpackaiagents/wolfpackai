"""add declarative AMP channel connections"""

from alembic import op
import sqlalchemy as sa

revision = "0022_channel_connections"
down_revision = "0021_runtime_channels_merge"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("channel_connections"):
        op.create_table(
            "channel_connections",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("project_id", sa.String(32), nullable=False),
            sa.Column("channel", sa.String(32), nullable=False),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("registration_id", sa.String(32), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("secret_refs", sa.JSON(), nullable=False),
            sa.Column("allowlist", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("project_id", "channel", "name", name="uq_channel_connection_name"),
        )
        op.create_index("ix_channel_connections_project_registration", "channel_connections", ["project_id", "registration_id"])


def downgrade():
    op.drop_index("ix_channel_connections_project_registration", table_name="channel_connections")
    op.drop_table("channel_connections")
