"""persist verified Mesh execution scope"""
from alembic import op
import sqlalchemy as sa

revision = "0010_trace_mesh_scope"
down_revision = "0009_agentic_mesh"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("traces", sa.Column("environment_id", sa.String(32), nullable=True))
    op.add_column("traces", sa.Column("registration_id", sa.String(32), nullable=True))
    op.add_column("traces", sa.Column("definition_id", sa.String(32), nullable=True))
    op.add_column("traces", sa.Column("definition_version", sa.String(64), nullable=True))
    op.add_column("traces", sa.Column("attribution_status", sa.String(20), nullable=False, server_default="unattributed"))
    op.create_index("ix_traces_project_scope_timestamp", "traces", ["project_id", "environment_id", "registration_id", "timestamp"])

def downgrade():
    op.drop_index("ix_traces_project_scope_timestamp", table_name="traces")
    op.drop_column("traces", "attribution_status")
    op.drop_column("traces", "definition_version")
    op.drop_column("traces", "definition_id")
    op.drop_column("traces", "registration_id")
    op.drop_column("traces", "environment_id")
