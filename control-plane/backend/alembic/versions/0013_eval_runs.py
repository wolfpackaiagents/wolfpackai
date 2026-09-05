"""add deterministic evaluation datasets and runs"""

from alembic import op
import sqlalchemy as sa

revision = "0013_eval_runs"
down_revision = ("0012_mesh_interactions", "0012_managed_alert_rules")
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("eval_runs"):
        return
    op.create_table("eval_datasets", sa.Column("id", sa.String(32), primary_key=True), sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False), sa.Column("name", sa.String(128), nullable=False), sa.Column("description", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("project_id", "name", name="uq_eval_dataset_name"))
    op.create_table("eval_dataset_items", sa.Column("id", sa.String(32), primary_key=True), sa.Column("dataset_id", sa.String(32), sa.ForeignKey("eval_datasets.id"), nullable=False), sa.Column("trace_id", sa.String(64), sa.ForeignKey("traces.id"), nullable=False), sa.Column("expected_output", sa.JSON()), sa.Column("metadata", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_eval_dataset_items_dataset", "eval_dataset_items", ["dataset_id"])
    op.create_table("eval_runs", sa.Column("id", sa.String(32), primary_key=True), sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False), sa.Column("dataset_id", sa.String(32), sa.ForeignKey("eval_datasets.id"), nullable=False), sa.Column("score_name", sa.String(128), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("total_cases", sa.Integer(), nullable=False), sa.Column("passed_cases", sa.Integer(), nullable=False), sa.Column("average_score", sa.Float()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True)))
    op.create_index("ix_eval_runs_project_created", "eval_runs", ["project_id", "created_at"])
    op.create_table("eval_run_results", sa.Column("id", sa.String(32), primary_key=True), sa.Column("eval_run_id", sa.String(32), sa.ForeignKey("eval_runs.id"), nullable=False), sa.Column("dataset_item_id", sa.String(32), sa.ForeignKey("eval_dataset_items.id"), nullable=False), sa.Column("trace_id", sa.String(64), sa.ForeignKey("traces.id"), nullable=False), sa.Column("actual_output", sa.JSON()), sa.Column("value", sa.Float(), nullable=False), sa.Column("score_id", sa.String(64), sa.ForeignKey("scores.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_eval_run_results_run", "eval_run_results", ["eval_run_id"])


def downgrade():
    op.drop_table("eval_run_results")
    op.drop_table("eval_runs")
    op.drop_table("eval_dataset_items")
    op.drop_table("eval_datasets")
