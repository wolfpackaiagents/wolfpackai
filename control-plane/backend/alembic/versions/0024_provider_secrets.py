"""add encrypted project-scoped provider secrets"""

from alembic import op
import sqlalchemy as sa


revision = "0024_provider_secrets"
down_revision = "0023_cost_attribution_links"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("provider_secrets"):
        op.create_table(
            "provider_secrets",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("provider", sa.String(64), nullable=False),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("encrypted_data_key", sa.Text(), nullable=False),
            sa.Column("ciphertext", sa.Text(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("rotation_interval_days", sa.Integer(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_rotated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("project_id", "provider", "name", name="uq_provider_secret_name"),
        )
        op.create_index("ix_provider_secrets_project_provider", "provider_secrets", ["project_id", "provider"])
    if not inspector.has_table("provider_secret_audits"):
        op.create_table(
            "provider_secret_audits",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("provider_secret_id", sa.String(32), nullable=False),
            sa.Column("action", sa.String(16), nullable=False),
            sa.Column("actor_api_key_id", sa.String(32), sa.ForeignKey("api_keys.id"), nullable=True),
            sa.Column("details", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_provider_secret_audits_project_created", "provider_secret_audits", ["project_id", "created_at"])


def downgrade():
    op.drop_index("ix_provider_secret_audits_project_created", table_name="provider_secret_audits")
    op.drop_table("provider_secret_audits")
    op.drop_index("ix_provider_secrets_project_provider", table_name="provider_secrets")
    op.drop_table("provider_secrets")
