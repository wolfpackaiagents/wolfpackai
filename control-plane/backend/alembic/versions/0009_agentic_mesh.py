"""add Agentic Mesh registry

Revision ID: 0009_agentic_mesh
Revises: 0008_approval_project_uniqueness
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009_agentic_mesh"
down_revision: Union[str, None] = "0008_approval_project_uniqueness"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("environments"):
        op.create_table("environments", sa.Column("id", sa.String(32), primary_key=True), sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False), sa.Column("slug", sa.String(64), nullable=False), sa.Column("name", sa.String(128), nullable=False), sa.Column("description", sa.Text()), sa.Column("status", sa.String(20), nullable=False, server_default="active"), sa.Column("labels", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("project_id", "slug", name="uq_environments_project_slug"))
        op.create_index("ix_environments_project_status", "environments", ["project_id", "status"])
    if not inspector.has_table("mesh_definitions"):
        op.create_table("mesh_definitions", sa.Column("id", sa.String(32), primary_key=True), sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False), sa.Column("key", sa.String(128), nullable=False), sa.Column("kind", sa.String(20), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("version", sa.String(64), nullable=False), sa.Column("description", sa.Text()), sa.Column("summary", sa.JSON(), nullable=False), sa.Column("artifact_digest", sa.String(128)), sa.Column("policy_hash", sa.String(128)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("project_id", "key", "version", name="uq_mesh_definitions_project_key_version"))
        op.create_index("ix_mesh_definitions_project_kind", "mesh_definitions", ["project_id", "kind"])
    if not inspector.has_table("environment_registrations"):
        op.create_table("environment_registrations", sa.Column("id", sa.String(32), primary_key=True), sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False), sa.Column("environment_id", sa.String(32), sa.ForeignKey("environments.id"), nullable=False), sa.Column("definition_id", sa.String(32), sa.ForeignKey("mesh_definitions.id"), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("tags", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("environment_id", "definition_id", name="uq_environment_registrations_environment_definition"))
        op.create_index("ix_environment_registrations_environment_enabled", "environment_registrations", ["environment_id", "enabled"])


def downgrade() -> None:
    op.drop_table("environment_registrations")
    op.drop_table("mesh_definitions")
    op.drop_table("environments")
