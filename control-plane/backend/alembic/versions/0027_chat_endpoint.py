"""add chat_endpoint to environment_registrations for external agent dispatch"""
from alembic import op
import sqlalchemy as sa

revision = "0027_chat_endpoint"
down_revision = "0026_chat_conversations"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("environment_registrations")}
    if "chat_endpoint" not in columns:
        op.add_column("environment_registrations", sa.Column("chat_endpoint", sa.String(2048)))


def downgrade():
    op.drop_column("environment_registrations", "chat_endpoint")