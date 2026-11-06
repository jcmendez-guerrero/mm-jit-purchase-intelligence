"""lot acquisition cost ledger and the median, margin and override fields of cost-write requests (MMI 002, FR-040..044).

The ledger is append-only: a correction on arrival is a new entry (source receipt_correction), so history is never rewritten.

Revision ID: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

CWR_COLUMNS = [
    sa.Column("median_cost", sa.Numeric(18, 4)), sa.Column("median_lot_refs", sa.JSON), sa.Column("pvp_used", sa.Numeric(18, 4)),
    sa.Column("margin_before", sa.Numeric(7, 4)), sa.Column("margin_after", sa.Numeric(7, 4)), sa.Column("rule_flags", sa.JSON),
    sa.Column("override_value", sa.Numeric(18, 4)), sa.Column("override_reason", sa.String(500)), sa.Column("override_by", sa.String(120)),
    sa.Column("override_at", sa.DateTime(timezone=True)), sa.Column("released_by", sa.String(120)),
]


def upgrade() -> None:
    op.create_table("lot_acquisition_costs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("variant_id", sa.Integer, nullable=False),
                    sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=False), sa.Column("order_ref", sa.String(60)),
                    sa.Column("lot", sa.String(60), nullable=False), sa.Column("received_at", sa.DateTime(timezone=True)),
                    sa.Column("quantity", sa.Integer, nullable=False, server_default="0"), sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False),
                    sa.Column("source", sa.String(20), nullable=False), sa.Column("recorded_by", sa.String(120), nullable=False),
                    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_lot_acquisition_costs_pair", "lot_acquisition_costs", ["variant_id", "supplier_id", "lot"])
    for col in CWR_COLUMNS:
        op.add_column("cost_write_requests", col)
    if op.get_bind().dialect.name == "postgresql":      # forbid_change() was created in 0004
        op.execute("CREATE TRIGGER lot_acquisition_costs_append_only BEFORE UPDATE OR DELETE ON lot_acquisition_costs FOR EACH ROW EXECUTE FUNCTION forbid_change()")
        op.execute("CREATE TRIGGER lot_acquisition_costs_no_truncate BEFORE TRUNCATE ON lot_acquisition_costs FOR EACH STATEMENT EXECUTE FUNCTION forbid_change()")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS lot_acquisition_costs_no_truncate ON lot_acquisition_costs")
        op.execute("DROP TRIGGER IF EXISTS lot_acquisition_costs_append_only ON lot_acquisition_costs")
    for col in reversed(CWR_COLUMNS):
        op.drop_column("cost_write_requests", col.name)
    op.drop_index("ix_lot_acquisition_costs_pair", table_name="lot_acquisition_costs")
    op.drop_table("lot_acquisition_costs")
