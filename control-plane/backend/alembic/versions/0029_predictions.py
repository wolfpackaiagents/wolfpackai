"""add prediction_runs and prediction_agent_runs tables"""
from alembic import op
import sqlalchemy as sa

revision = "0029_predictions"
down_revision = "0028_alert_destinations"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    if "prediction_runs" not in tables:
        op.create_table(
            "prediction_runs",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("seed_summary", sa.Text, nullable=True),
            sa.Column("horizon_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("scenario_params", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("personas", sa.JSON, nullable=False, server_default=sa.text("'[]'::json")),
            sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'running'")),
            sa.Column("report", sa.JSON, nullable=True),
            sa.Column("accuracy_score", sa.Float, nullable=True),
            sa.Column("metadata", sa.JSON, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_prediction_runs_project_created", "prediction_runs", ["project_id", "created_at"])
    if "prediction_agent_runs" not in tables:
        op.create_table(
            "prediction_agent_runs",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("prediction_run_id", sa.String(32), sa.ForeignKey("prediction_runs.id"), nullable=False),
            sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("persona_name", sa.String(128), nullable=False),
            sa.Column("persona_profile", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("trace_id", sa.String(64), nullable=True),
            sa.Column("prediction", sa.JSON, nullable=True),
            sa.Column("confidence", sa.Float, nullable=True),
            sa.Column("interactions", sa.JSON, nullable=False, server_default=sa.text("'[]'::json")),
            sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_prediction_agent_runs_run", "prediction_agent_runs", ["prediction_run_id"])


def downgrade():
    op.drop_table("prediction_agent_runs")
    op.drop_table("prediction_runs")