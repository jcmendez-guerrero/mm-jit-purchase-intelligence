"""demand series, flows, stock history, quality metrics, loss cutover config, review decisions.

Revision ID: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stock_movements", sa.Column("quarantine_codes", sa.String(120)))
    op.create_table("demand_observations", sa.Column("variant_id", sa.Integer, primary_key=True, autoincrement=False),
                    sa.Column("warehouse_id", sa.Integer, primary_key=True, autoincrement=False), sa.Column("day", sa.Date, primary_key=True),
                    sa.Column("demand_qty", sa.Integer, nullable=False), sa.Column("censored", sa.Boolean, nullable=False, server_default=sa.false()),
                    sa.Column("lineage", sa.String(32), nullable=False))
    op.create_table("flow_series", sa.Column("variant_id", sa.Integer, primary_key=True, autoincrement=False),
                    sa.Column("warehouse_id", sa.Integer, primary_key=True, autoincrement=False), sa.Column("day", sa.Date, primary_key=True),
                    sa.Column("flow", sa.String(30), primary_key=True), sa.Column("qty", sa.Integer, nullable=False))
    op.create_table("stock_history", sa.Column("variant_id", sa.Integer, primary_key=True, autoincrement=False),
                    sa.Column("warehouse_id", sa.Integer, primary_key=True, autoincrement=False), sa.Column("day", sa.Date, primary_key=True),
                    sa.Column("on_hand_reconstructed", sa.Integer, nullable=False), sa.Column("censored", sa.Boolean, nullable=False, server_default=sa.false()),
                    sa.Column("reconciled_ok", sa.Boolean, nullable=False, server_default=sa.true()))
    op.create_table("data_quality_metrics", sa.Column("day", sa.Date, primary_key=True), sa.Column("metric", sa.String(60), primary_key=True),
                    sa.Column("value", sa.Numeric(18, 6), nullable=False))
    op.create_table("config_loss_cutover", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
                    sa.Column("effective_date", sa.Date, nullable=False), sa.Column("changed_by", sa.String(120), nullable=False),
                    sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("review_decisions", sa.Column("external_id", sa.BigInteger, primary_key=True, autoincrement=False),
                    sa.Column("decision", sa.String(10), nullable=False), sa.Column("decided_by", sa.String(120), nullable=False),
                    sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    for t in ("review_decisions", "config_loss_cutover", "data_quality_metrics", "stock_history", "flow_series", "demand_observations"):
        op.drop_table(t)
    op.drop_column("stock_movements", "quarantine_codes")
