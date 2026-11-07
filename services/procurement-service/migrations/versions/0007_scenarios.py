"""procurement scenarios and version references on proposals (MMI 002).

Revision ID: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("scenarios", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(200), nullable=False),
                    sa.Column("parameters", sa.JSON, nullable=False), sa.Column("status", sa.String(10), nullable=False), sa.Column("input_versions", sa.JSON),
                    sa.Column("result_hash", sa.String(64)), sa.Column("idempotency_key", sa.String(120), unique=True),
                    sa.Column("created_by", sa.String(120), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("summary", sa.JSON))
    op.create_table("scenario_results", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
                    sa.Column("scenario_id", sa.String(36), sa.ForeignKey("scenarios.id"), nullable=False), sa.Column("supplier_id", sa.String(36), nullable=False),
                    sa.Column("lines", sa.JSON, nullable=False), sa.Column("order_total", sa.Numeric(18, 4), nullable=False), sa.Column("subtotal", sa.Numeric(18, 4)),
                    sa.Column("delivery_charge", sa.Numeric(18, 4)), sa.Column("discount", sa.Numeric(18, 4)), sa.Column("free_delivery", sa.Boolean), sa.Column("expected_delivery", sa.Date),
                    sa.Column("budget_utilisation", sa.Numeric(8, 4)), sa.Column("binding_constraints", sa.JSON))
    op.create_index("ix_scenario_results_scenario_id", "scenario_results", ["scenario_id"])
    op.create_table("scenario_sensitivity", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
                    sa.Column("scenario_id", sa.String(36), sa.ForeignKey("scenarios.id"), nullable=False), sa.Column("constraint_key", sa.String(60), nullable=False),
                    sa.Column("delta", sa.String(40), nullable=False), sa.Column("cost_impact", sa.Numeric(18, 4), nullable=False))
    op.create_index("ix_scenario_sensitivity_scenario_id", "scenario_sensitivity", ["scenario_id"])
    for col in (sa.Column("scenario_id", sa.String(36)), sa.Column("terms_version_ids", sa.JSON), sa.Column("policy_version_ids", sa.JSON),
                sa.Column("dataset_version_id", sa.String(36)), sa.Column("forecast_run_id", sa.String(36))):
        op.add_column("proposals", col)


def downgrade() -> None:
    for c in ("forecast_run_id", "dataset_version_id", "policy_version_ids", "terms_version_ids", "scenario_id"):
        op.drop_column("proposals", c)
    op.drop_index("ix_scenario_sensitivity_scenario_id", table_name="scenario_sensitivity")
    op.drop_index("ix_scenario_results_scenario_id", table_name="scenario_results")
    for t in ("scenario_sensitivity", "scenario_results", "scenarios"):
        op.drop_table(t)
