"""forecast explanations and per-product backtests (feature 018).

Additive only: two new tables. forecast_explanations rows are immutable once their run completes.

Revision ID: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "forecast_explanations",
        sa.Column("run_id", sa.String(36), sa.ForeignKey("forecast_runs.id"), primary_key=True),
        sa.Column("variant_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("sku", sa.String(60)),
        sa.Column("model_version", sa.String(120), nullable=False),
        sa.Column("dataset_version_id", sa.String(36)),
        sa.Column("config_version_id", sa.String(36)),
        sa.Column("history_start", sa.Date),
        sa.Column("history_end", sa.Date),
        sa.Column("abc", sa.String(1)),
        sa.Column("xyz", sa.String(1)),
        sa.Column("pattern", sa.String(14)),
        sa.Column("intermittent", sa.Boolean, nullable=False),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("method_reason_code", sa.String(40), nullable=False),
        sa.Column("censored_days", sa.Integer, nullable=False),
        sa.Column("anomaly_days_excluded", sa.Integer, nullable=False),
        sa.Column("provenance_mix", sa.JSON, nullable=False),
        sa.Column("low", sa.Float),
        sa.Column("expected", sa.Float),
        sa.Column("high", sa.Float),
        sa.Column("confidence", sa.String(10)),
        sa.Column("confidence_reason_codes", sa.JSON, nullable=False),
        sa.Column("eligibility", sa.String(20), nullable=False),
        sa.Column("eligibility_reason_codes", sa.JSON, nullable=False),
    )
    op.create_index("ix_forecast_explanations_sku", "forecast_explanations", ["sku"])
    op.create_table(
        "product_backtest",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("backtest_run_id", sa.String(36), nullable=False),
        sa.Column("variant_id", sa.Integer, nullable=False),
        sa.Column("sku", sa.String(60)),
        sa.Column("periods", sa.Integer, nullable=False),
        sa.Column("wape", sa.Numeric(12, 6)),
        sa.Column("bias", sa.Numeric(12, 6)),
        sa.Column("baseline_wape", sa.Numeric(12, 6)),
        sa.Column("baseline_bias", sa.Numeric(12, 6)),
        sa.Column("beats_baseline", sa.Boolean, nullable=False),
        sa.Column("model_version", sa.String(120), nullable=False),
        sa.Column("dataset_version_id", sa.String(36)),
        sa.Column("config_version_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("backtest_run_id", "variant_id", name="uq_product_backtest"),
    )


    op.create_index("ix_product_backtest_sku", "product_backtest", ["sku"])
    op.create_table(
        "backtest_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scope", sa.String(12), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("requested_by", sa.String(120), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("uq_backtest_one_running_catalogue", "backtest_jobs", ["scope"], unique=True,
                    postgresql_where=sa.text("scope = 'catalogue' AND status = 'running'"), sqlite_where=sa.text("scope = 'catalogue' AND status = 'running'"))


def downgrade() -> None:
    op.drop_index("uq_backtest_one_running_catalogue", table_name="backtest_jobs")
    op.drop_table("backtest_jobs")
    op.drop_table("product_backtest")
    op.drop_table("forecast_explanations")
