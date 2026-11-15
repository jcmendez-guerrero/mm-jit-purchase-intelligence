"""data quality and forecast intelligence: quality snapshots, anomaly flags, portfolio aggregate, forecast inbox (feature 012).

Additive only: four new tables and two nullable columns on product_segments (older rows keep NULL).
If feature 011's own 0008 revision merges first, renumber this one to 0009 and point down_revision at it.

Revision ID: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("product_segments", sa.Column("config_version_id", sa.String(36), nullable=True))
    op.add_column("product_segments", sa.Column("method", sa.String(30), nullable=True))
    op.create_table(
        "data_quality_snapshot",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("variant_id", sa.Integer, nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("days_in_period", sa.Integer, nullable=False),
        sa.Column("days_with_data", sa.Integer, nullable=False),
        sa.Column("coverage_ratio", sa.Numeric(7, 6), nullable=False),
        sa.Column("gap_days", sa.JSON, nullable=False),
        sa.Column("rejected_count", sa.Integer, nullable=False),
        sa.Column("quarantined_count", sa.Integer, nullable=False),
        sa.Column("ambiguous_count", sa.Integer, nullable=False),
        sa.Column("reason_counts", sa.JSON, nullable=False),
        sa.Column("excluded_by_type", sa.JSON, nullable=False),
        sa.Column("anomaly_count", sa.Integer, nullable=False),
        sa.Column("censored_days", sa.Integer, nullable=False),
        sa.Column("origin", sa.String(12), nullable=False),
        sa.Column("config_version_id", sa.String(36), nullable=False),
        sa.Column("dataset_version_id", sa.String(36)),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("built_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("variant_id", "period_start", "period_end", "config_version_id", "input_hash", name="uq_quality_snapshot_inputs"),
    )
    op.create_index("ix_data_quality_snapshot_variant_id", "data_quality_snapshot", ["variant_id"])
    op.create_table(
        "anomaly_flags",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("variant_id", sa.Integer, nullable=False),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("rule_id", sa.String(30), nullable=False),
        sa.Column("original_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("decision", sa.String(10), nullable=False),
        sa.Column("decided_by", sa.String(120)),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("reason_code", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("variant_id", "day", "rule_id", name="uq_anomaly_flag"),
    )
    op.create_index("ix_anomaly_flags_variant_id", "anomaly_flags", ["variant_id"])
    op.create_table(
        "forecast_inbox",
        sa.Column("message_id", sa.String(64), primary_key=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "portfolio_aggregate",
        sa.Column("variant_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("origin", sa.String(12), nullable=False),
        sa.Column("abc", sa.String(1), nullable=False),
        sa.Column("xyz", sa.String(1), nullable=False),
        sa.Column("pattern", sa.String(14), nullable=False),
        sa.Column("intermittent", sa.Boolean, nullable=False),
        sa.Column("coverage_ratio", sa.Numeric(7, 6)),
        sa.Column("rejected_share", sa.Numeric(7, 6)),
        sa.Column("anomaly_share", sa.Numeric(7, 6)),
        sa.Column("eligibility", sa.String(20), nullable=False),
        sa.Column("confidence", sa.String(10)),
        sa.Column("received_run_id", sa.String(36)),
        sa.Column("received_at", sa.DateTime(timezone=True)),
        sa.Column("category", sa.String(120)),
        sa.Column("supplier", sa.String(120)),
    )


def downgrade() -> None:
    op.drop_table("portfolio_aggregate")
    op.drop_table("forecast_inbox")
    op.drop_index("ix_anomaly_flags_variant_id", table_name="anomaly_flags")
    op.drop_table("anomaly_flags")
    op.drop_index("ix_data_quality_snapshot_variant_id", table_name="data_quality_snapshot")
    op.drop_table("data_quality_snapshot")
    with op.batch_alter_table("product_segments") as b:
        b.drop_column("method")
        b.drop_column("config_version_id")
