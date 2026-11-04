"""procurement schema: suppliers, terms, immutable cost versions, recargo and rule config, ERP links, audit chain.

Revision ID: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None
MONEY = sa.Numeric(18, 4)


def upgrade() -> None:
    op.create_table("suppliers", sa.Column("id", sa.String(36), primary_key=True), sa.Column("external_contact_id", sa.Integer, unique=True),
                    sa.Column("name", sa.String(200), nullable=False))
    op.create_table("supplier_terms", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
                    sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=False), sa.Column("min_order_value", MONEY),
                    sa.Column("min_qty_for_delivery", sa.Integer), sa.Column("free_delivery_threshold", MONEY), sa.Column("delivery_charge", MONEY),
                    sa.Column("order_days", sa.JSON, nullable=False), sa.Column("delivery_schedule", sa.String(200)),
                    sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False), sa.Column("changed_by", sa.String(120), nullable=False))
    op.create_table("supplier_costs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("product_id", sa.Integer, nullable=False),
                    sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=False), sa.Column("variant_id", sa.Integer),
                    sa.Column("version", sa.Integer, nullable=False), sa.Column("cost_net", MONEY), sa.Column("recargo_rate", sa.Numeric(6, 4)),
                    sa.Column("cost_with_recargo", MONEY, nullable=False), sa.Column("entered_includes_recargo", sa.Boolean, nullable=False),
                    sa.Column("vat_rate_used", sa.Numeric(5, 2)), sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
                    sa.Column("pack_size", sa.Integer), sa.Column("lead_time_days", sa.Integer), sa.Column("min_order_qty", sa.Integer),
                    sa.Column("source", sa.String(24), nullable=False), sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("verified_by", sa.String(120)), sa.Column("superseded_by", sa.String(36)),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_by", sa.String(120), nullable=False),
                    sa.Column("jump_flag", sa.Boolean, nullable=False, server_default=sa.false()), sa.Column("jump_confirmed_by", sa.String(120)),
                    sa.Column("jump_confirmed_at", sa.DateTime(timezone=True)),
                    sa.UniqueConstraint("product_id", "supplier_id", "variant_id", "version", name="uq_cost_version"),
                    sa.CheckConstraint("source in ('siweb_product_supplier','csv_price_list','manual')", name="ck_cost_source"),
                    sa.CheckConstraint("cost_with_recargo >= 0", name="ck_cost_nonneg"))
    op.create_index("ix_costs_current", "supplier_costs", ["product_id", "supplier_id", "variant_id", "superseded_by"])
    op.create_table("recargo_rates", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False),
                    sa.Column("recargo_rate", sa.Numeric(5, 2), nullable=False), sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("changed_by", sa.String(120), nullable=False))
    op.create_table("cost_rule_config", sa.Column("key", sa.String(30), primary_key=True), sa.Column("value", sa.Numeric(10, 4), nullable=False),
                    sa.Column("changed_by", sa.String(120), nullable=False), sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("erp_supplier_links", sa.Column("product_id", sa.Integer, primary_key=True, autoincrement=False),
                    sa.Column("supplier_id", sa.String(36), primary_key=True), sa.Column("has_cost", sa.Boolean, nullable=False),
                    sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("product_refs", sa.Column("variant_id", sa.Integer, primary_key=True, autoincrement=False), sa.Column("product_id", sa.Integer, nullable=False),
                    sa.Column("vat_rate", sa.Numeric(5, 2)), sa.Column("vat_source", sa.String(20)))
    op.create_index("ix_product_refs_product", "product_refs", ["product_id"])
    op.create_table("audit_events", sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True), sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("actor", sa.String(120), nullable=False), sa.Column("action", sa.String(40), nullable=False),
                    sa.Column("entity", sa.String(30), nullable=False), sa.Column("entity_id", sa.String(60), nullable=False),
                    sa.Column("before", sa.JSON), sa.Column("after", sa.JSON), sa.Column("prev_hash", sa.String(64), nullable=False, unique=True),
                    sa.Column("hash", sa.String(64), nullable=False))
    op.create_table("outbox", sa.Column("event_id", sa.String(36), primary_key=True), sa.Column("type", sa.String(120), nullable=False),
                    sa.Column("envelope", sa.JSON, nullable=False), sa.Column("status", sa.String(12), nullable=False),
                    sa.Column("attempts", sa.Integer, nullable=False, server_default="0"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("sent_at", sa.DateTime(timezone=True)))
    op.create_table("inbox", sa.Column("event_id", sa.String(36), primary_key=True), sa.Column("type", sa.String(120), nullable=False),
                    sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    for t in ("inbox", "outbox", "audit_events", "product_refs", "erp_supplier_links", "cost_rule_config", "recargo_rates", "supplier_costs",
              "supplier_terms", "suppliers"):
        op.drop_table(t)
