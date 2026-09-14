"""add normalized prediction simulation ledger"""
from alembic import op
import sqlalchemy as sa

revision = "0030_prediction_ledger"
down_revision = "0029_predictions"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "prediction_entities" not in tables:
        op.create_table(
            "prediction_entities",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("prediction_run_id", sa.String(32), sa.ForeignKey("prediction_runs.id"), nullable=False),
            sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("entity_type", sa.String(64), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("state", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("metadata", sa.JSON, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_prediction_entities_run", "prediction_entities", ["prediction_run_id"])
        op.create_index("ix_prediction_entities_project_run", "prediction_entities", ["project_id", "prediction_run_id"])

    if "prediction_relationships" not in tables:
        op.create_table(
            "prediction_relationships",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("prediction_run_id", sa.String(32), sa.ForeignKey("prediction_runs.id"), nullable=False),
            sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("source_entity_id", sa.String(32), sa.ForeignKey("prediction_entities.id"), nullable=False),
            sa.Column("target_entity_id", sa.String(32), sa.ForeignKey("prediction_entities.id"), nullable=False),
            sa.Column("relationship_type", sa.String(64), nullable=False),
            sa.Column("attributes", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_prediction_relationships_run", "prediction_relationships", ["prediction_run_id"])
        op.create_index("ix_prediction_relationships_source", "prediction_relationships", ["source_entity_id"])
        op.create_index("ix_prediction_relationships_target", "prediction_relationships", ["target_entity_id"])

    if "prediction_rounds" not in tables:
        op.create_table(
            "prediction_rounds",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("prediction_run_id", sa.String(32), sa.ForeignKey("prediction_runs.id"), nullable=False),
            sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("number", sa.Integer, nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'open'")),
            sa.Column("data", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("prediction_run_id", "number", name="uq_prediction_rounds_run_number"),
        )
        op.create_index("ix_prediction_rounds_run", "prediction_rounds", ["prediction_run_id"])

    if "prediction_events" not in tables:
        op.create_table(
            "prediction_events",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("prediction_run_id", sa.String(32), sa.ForeignKey("prediction_runs.id"), nullable=False),
            sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("round_id", sa.String(32), sa.ForeignKey("prediction_rounds.id"), nullable=True),
            sa.Column("entity_id", sa.String(32), sa.ForeignKey("prediction_entities.id"), nullable=True),
            sa.Column("agent_run_id", sa.String(32), sa.ForeignKey("prediction_agent_runs.id"), nullable=True),
            sa.Column("sequence", sa.BigInteger, nullable=False),
            sa.Column("event_type", sa.String(64), nullable=False),
            sa.Column("payload", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("idempotency_key", sa.String(128), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("prediction_run_id", "sequence", name="uq_prediction_events_run_sequence"),
            sa.UniqueConstraint("prediction_run_id", "idempotency_key", name="uq_prediction_events_run_idempotency"),
        )
        op.create_index("ix_prediction_events_run_sequence", "prediction_events", ["prediction_run_id", "sequence"])
        op.create_index("ix_prediction_events_entity", "prediction_events", ["entity_id"])
        op.create_index("ix_prediction_events_round", "prediction_events", ["round_id"])

    if "prediction_entity_revisions" not in tables:
        op.create_table(
            "prediction_entity_revisions",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("prediction_run_id", sa.String(32), sa.ForeignKey("prediction_runs.id"), nullable=False),
            sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("entity_id", sa.String(32), sa.ForeignKey("prediction_entities.id"), nullable=False),
            sa.Column("revision", sa.Integer, nullable=False),
            sa.Column("state", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("entity_id", "revision", name="uq_prediction_entity_revisions_entity_revision"),
        )
        op.create_index("ix_prediction_entity_revisions_run_entity", "prediction_entity_revisions", ["prediction_run_id", "entity_id"])

    columns = {column["name"] for column in inspector.get_columns("prediction_agent_runs")}
    if "entity_id" not in columns:
        op.add_column("prediction_agent_runs", sa.Column("entity_id", sa.String(32), sa.ForeignKey("prediction_entities.id"), nullable=True))


def downgrade():
    op.drop_column("prediction_agent_runs", "entity_id")
    op.drop_table("prediction_entity_revisions")
    op.drop_table("prediction_events")
    op.drop_table("prediction_rounds")
    op.drop_table("prediction_relationships")
    op.drop_table("prediction_entities")
