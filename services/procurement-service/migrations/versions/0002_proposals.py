"""proposals, targets, order groups, approvals, inbound orders, cost write requests.

Revision ID: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None
MONEY = sa.Numeric(18, 4)


def upgrade() -> None:
    op.add_column("product_refs", sa.Column("sku", sa.String(60)))
    op.add_column("product_refs", sa.Column("name", sa.String(200)))
    op.create_table("proposals", sa.Column("id", sa.String(36), primary_key=True), sa.Column("week", sa.String(10), nullable=False),
                    sa.Column("status", sa.String(12), nullable=False), sa.Column("created_by", sa.String(120), nullable=False),
                    sa.Column("last_edited_by", sa.String(120), nullable=False), sa.Column("version", sa.Integer, nullable=False, server_default="1"),
                    sa.Column("inputs_hash", sa.String(64), nullable=False), sa.Column("rule_versions", sa.JSON, nullable=False),
                    sa.Column("solver_status", sa.String(20), nullable=False), sa.Column("budget", MONEY), sa.Column("flags", sa.JSON, nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("submitted_at", sa.DateTime(timezone=True)),
                    sa.CheckConstraint("status in ('draft','submitted','approved','exported','superseded')", name="ck_proposal_status"))
    op.create_index("ix_proposals_week", "proposals", ["week"])
    op.create_table("proposal_lines", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("proposal_id", sa.String(36), sa.ForeignKey("proposals.id"), nullable=False), sa.Column("variant_id", sa.Integer, nullable=False),
                    sa.Column("product_id", sa.Integer, nullable=False), sa.Column("supplier_id", sa.String(36), nullable=False),
                    sa.Column("qty", sa.Integer, nullable=False), sa.Column("unit_cost_with_recargo", MONEY, nullable=False),
                    sa.Column("line_total", MONEY, nullable=False), sa.Column("forecast_or_policy", sa.String(30), nullable=False),
                    sa.Column("safety_stock", sa.Integer), sa.Column("constraints_applied", sa.JSON, nullable=False),
                    sa.Column("risk", sa.String(8), nullable=False), sa.Column("confidence", sa.String(8), nullable=False),
                    sa.Column("explanation", sa.JSON, nullable=False), sa.Column("alternatives_compared", sa.JSON, nullable=False),
                    sa.Column("manual_override", sa.Boolean, nullable=False, server_default=sa.false()), sa.Column("topup", sa.Boolean, nullable=False, server_default=sa.false()),
                    sa.UniqueConstraint("proposal_id", "variant_id", name="uq_line_variant"), sa.CheckConstraint("qty >= 0", name="ck_line_qty"))
    op.create_index("ix_lines_proposal", "proposal_lines", ["proposal_id"])
    op.create_table("replenishment_targets", sa.Column("proposal_id", sa.String(36), primary_key=True),
                    sa.Column("variant_id", sa.Integer, primary_key=True, autoincrement=False), sa.Column("protection_horizon_days", sa.Integer, nullable=False),
                    sa.Column("expected_demand", sa.Float), sa.Column("safety_stock", sa.Integer), sa.Column("target_level", sa.Integer, nullable=False),
                    sa.Column("inventory_position", sa.Integer, nullable=False), sa.Column("inputs_hash", sa.String(64), nullable=False))
    op.create_table("supplier_order_groups", sa.Column("proposal_id", sa.String(36), primary_key=True), sa.Column("supplier_id", sa.String(36), primary_key=True),
                    sa.Column("subtotal", MONEY, nullable=False), sa.Column("delivery_charge", MONEY, nullable=False), sa.Column("total_cost", MONEY, nullable=False),
                    sa.Column("expected_delivery_date", sa.Date), sa.Column("minimum_status", sa.String(10), nullable=False),
                    sa.Column("free_delivery", sa.Boolean, nullable=False, server_default=sa.false()), sa.Column("shortfall_options", sa.JSON, nullable=False))
    op.create_table("approvals", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), sa.Column("proposal_id", sa.String(36), nullable=False),
                    sa.Column("approver_id", sa.String(120), nullable=False), sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("decision", sa.String(10), nullable=False), sa.Column("mfa_auth_time", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("proposal_version", sa.Integer, nullable=False))
    op.create_index("ix_approvals_proposal", "approvals", ["proposal_id"])
    op.create_table("inbound_orders", sa.Column("id", sa.String(36), primary_key=True), sa.Column("proposal_id", sa.String(36), nullable=False),
                    sa.Column("supplier_id", sa.String(36), nullable=False), sa.Column("status", sa.String(20), nullable=False),
                    sa.Column("confirmed_by", sa.String(120), nullable=False), sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("expected_delivery", sa.Date), sa.Column("erp_purchase_ref", sa.Integer),
                    sa.UniqueConstraint("proposal_id", "supplier_id", name="uq_order_per_supplier"))
    op.create_table("inbound_order_lines", sa.Column("order_id", sa.String(36), primary_key=True), sa.Column("variant_id", sa.Integer, primary_key=True, autoincrement=False),
                    sa.Column("qty", sa.Integer, nullable=False), sa.Column("confirmed_cost_with_recargo", MONEY, nullable=False),
                    sa.Column("received_qty", sa.Integer, nullable=False, server_default="0"))
    op.create_table("receipt_matches", sa.Column("movement_id", sa.BigInteger, primary_key=True, autoincrement=False), sa.Column("order_id", sa.String(36), nullable=False),
                    sa.Column("variant_id", sa.Integer, nullable=False), sa.Column("qty", sa.Integer, nullable=False), sa.Column("matched_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("cost_write_requests", sa.Column("id", sa.String(36), primary_key=True), sa.Column("cost_id", sa.String(36), nullable=False),
                    sa.Column("product_id", sa.Integer, nullable=False), sa.Column("supplier_id", sa.String(36), nullable=False),
                    sa.Column("trigger", sa.String(16), nullable=False), sa.Column("proposed_value", MONEY, nullable=False), sa.Column("previous_siweb_value", MONEY),
                    sa.Column("status", sa.String(16), nullable=False), sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
                    sa.Column("last_error", sa.String(200)), sa.Column("requested_by", sa.String(120), nullable=False), sa.Column("reviewed_by", sa.String(120)),
                    sa.Column("idempotency_key", sa.String(120), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    for t in ("cost_write_requests", "receipt_matches", "inbound_order_lines", "inbound_orders", "approvals", "supplier_order_groups", "replenishment_targets",
              "proposal_lines", "proposals"):
        op.drop_table(t)
    op.drop_column("product_refs", "name")
    op.drop_column("product_refs", "sku")
