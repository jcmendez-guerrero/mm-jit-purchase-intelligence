"""forecast parameters, accuracy, and dataset/parameter version columns on forecast runs (MMI 002).

Revision ID: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("forecast_parameters", sa.Column("id", sa.String(36), primary_key=True), sa.Column("scope", sa.String(40), nullable=False),
                    sa.Column("key", sa.String(60), nullable=False), sa.Column("value", sa.JSON, nullable=False), sa.Column("valid_from", sa.Date, nullable=False),
                    sa.Column("valid_to", sa.Date), sa.Column("revision", sa.Integer, nullable=False, server_default="1"),
                    sa.Column("changed_by", sa.String(120), nullable=False),
                    sa.UniqueConstraint("scope", "key", "valid_from", name="uq_forecast_parameters_effective"))
    op.create_table("forecast_accuracy", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
                    sa.Column("run_id", sa.String(36), sa.ForeignKey("forecast_runs.id"), nullable=False), sa.Column("segment", sa.String(20), nullable=False),
                    sa.Column("metric", sa.String(20), nullable=False), sa.Column("value", sa.Numeric(12, 6), nullable=False), sa.Column("window_days", sa.Integer),
                    sa.UniqueConstraint("run_id", "segment", "metric", name="uq_forecast_accuracy_natural"))
    op.add_column("forecast_runs", sa.Column("dataset_version_id", sa.String(36)))
    op.add_column("forecast_runs", sa.Column("parameter_version_ids", sa.JSON))


def downgrade() -> None:
    op.drop_column("forecast_runs", "parameter_version_ids")
    op.drop_column("forecast_runs", "dataset_version_id")
    op.drop_table("forecast_accuracy")
    op.drop_table("forecast_parameters")
