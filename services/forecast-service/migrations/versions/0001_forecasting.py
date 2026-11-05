"""forecasting schema: runs, values, backtest metrics, model registry, outbox/inbox.

Revision ID: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("forecast_runs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("through_day", sa.String(10)),
                    sa.Column("model_versions", sa.JSON, nullable=False), sa.Column("input_hash", sa.String(64), nullable=False),
                    sa.Column("config", sa.JSON, nullable=False), sa.Column("status", sa.String(12), nullable=False),
                    sa.Column("total_count", sa.Integer, nullable=False, server_default="0"), sa.Column("eligible_count", sa.Integer, nullable=False, server_default="0"))
    op.create_index("ix_forecast_runs_input_hash", "forecast_runs", ["input_hash"])
    op.create_table("forecast_values", sa.Column("run_id", sa.String(36), primary_key=True), sa.Column("variant_id", sa.Integer, primary_key=True, autoincrement=False),
                    sa.Column("horizon_days", sa.Integer, primary_key=True, autoincrement=False), sa.Column("mean", sa.Float),
                    sa.Column("quantiles", sa.JSON, nullable=False), sa.Column("policy_used", sa.String(30), nullable=False),
                    sa.Column("eligible", sa.Boolean, nullable=False), sa.Column("reasons", sa.String(200), nullable=False),
                    sa.Column("service_level", sa.Numeric(5, 4), nullable=False))
    op.create_table("backtest_metrics", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), sa.Column("run_id", sa.String(36), nullable=False),
                    sa.Column("segment", sa.String(14), nullable=False), sa.Column("policy", sa.String(30), nullable=False),
                    sa.Column("stockout_cost", sa.Numeric(18, 4), nullable=False), sa.Column("holding_cost", sa.Numeric(18, 4), nullable=False),
                    sa.Column("expiry_cost", sa.Numeric(18, 4), nullable=False), sa.Column("windows", sa.Integer, nullable=False),
                    sa.Column("adopted", sa.Boolean, nullable=False), sa.UniqueConstraint("run_id", "segment", "policy", name="uq_backtest"))
    op.create_table("model_registry", sa.Column("name", sa.String(30), primary_key=True), sa.Column("version", sa.String(20), primary_key=True),
                    sa.Column("params_hash", sa.String(64), nullable=False), sa.Column("artifact_uri", sa.String(300)),
                    sa.Column("adopted_for_segment", sa.String(14)))
    op.create_table("outbox", sa.Column("event_id", sa.String(36), primary_key=True), sa.Column("type", sa.String(120), nullable=False),
                    sa.Column("envelope", sa.JSON, nullable=False), sa.Column("status", sa.String(12), nullable=False),
                    sa.Column("attempts", sa.Integer, nullable=False, server_default="0"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("sent_at", sa.DateTime(timezone=True)))
    op.create_table("inbox", sa.Column("event_id", sa.String(36), primary_key=True), sa.Column("type", sa.String(120), nullable=False),
                    sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    for t in ("inbox", "outbox", "model_registry", "backtest_metrics", "forecast_values", "forecast_runs"):
        op.drop_table(t)
