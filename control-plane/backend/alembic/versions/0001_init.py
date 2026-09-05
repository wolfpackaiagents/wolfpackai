"""create initial schema

Revision ID: 0001_wolfpack_init
Revises:
Create Date: 2026-08-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_wolfpack_init"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("organization_id", sa.String(32), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("retention_days", sa.Integer(), server_default="30", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_projects_org_id", "projects", ["organization_id"])
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("public_key", sa.String(64), unique=True, nullable=False),
        sa.Column("hashed_secret_key", sa.String(128), nullable=False),
        sa.Column("display_secret_key", sa.String(32), nullable=False),
        sa.Column("note", sa.String(255), server_default=""),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_api_keys_project_id", "api_keys", ["project_id"])
    op.create_table(
        "traces",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("user_id", sa.String(128), nullable=True),
        sa.Column("version", sa.String(64), nullable=True),
        sa.Column("release", sa.String(64), nullable=True),
        sa.Column("environment", sa.String(64), nullable=True),
        sa.Column("input", sa.JSON(), nullable=True),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("total_cost", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_table(
        "observations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("trace_id", sa.String(64), sa.ForeignKey("traces.id"), nullable=False),
        sa.Column("parent_observation_id", sa.String(64), nullable=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("level", sa.String(16), server_default="DEFAULT", nullable=False),
        sa.Column("status_message", sa.Text(), nullable=True),
        sa.Column("model", sa.String(255), nullable=True),
        sa.Column("model_parameters", sa.JSON(), nullable=True),
        sa.Column("input", sa.JSON(), nullable=True),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("usage", sa.JSON(), nullable=True),
        sa.Column("cost", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("environment", sa.String(64), nullable=True),
        sa.Column("fingerprint", sa.JSON(), nullable=True),
    )
    op.create_table(
        "scores",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("trace_id", sa.String(64), sa.ForeignKey("traces.id"), nullable=False),
        sa.Column("observation_id", sa.String(64), nullable=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("data_type", sa.String(16), server_default="NUMERIC", nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("string_value", sa.String(500), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("source", sa.String(32), server_default="API", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "prompts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(16), server_default="text", nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("labels", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "name", "version", name="uq_prompt_name_version"),
    )


def downgrade() -> None:
    op.drop_table("prompts")
    op.drop_table("scores")
    op.drop_table("observations")
    op.drop_table("traces")
    op.drop_table("api_keys")
    op.drop_table("projects")
    op.drop_table("organizations")