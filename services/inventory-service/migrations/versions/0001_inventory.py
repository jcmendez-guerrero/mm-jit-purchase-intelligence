"""inventory schema: reference data, snapshots, lots, movements, outbox/inbox.

Revision ID: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("warehouses", sa.Column("external_id", sa.Integer, primary_key=True, autoincrement=False),
                    sa.Column("name", sa.String(120), nullable=False), sa.Column("is_unassigned", sa.Boolean, nullable=False, server_default=sa.false()))
    op.create_table("products", sa.Column("external_id", sa.Integer, primary_key=True, autoincrement=False),
                    sa.Column("name", sa.String(200), nullable=False), sa.Column("status", sa.String(12), nullable=False, server_default="active"),
                    sa.Column("missed_syncs", sa.Integer, nullable=False, server_default="0"), sa.Column("vat_rate", sa.Numeric(5, 2)),
                    sa.Column("clinical_critical", sa.Boolean, nullable=False, server_default=sa.false()))
    op.create_table("variants", sa.Column("external_id", sa.Integer, primary_key=True, autoincrement=False),
                    sa.Column("product_id", sa.Integer, sa.ForeignKey("products.external_id")), sa.Column("sku", sa.String(60)),
                    sa.Column("name", sa.String(200)), sa.Column("pack_size", sa.Integer), sa.Column("uom", sa.String(20)),
                    sa.Column("reorder_point", sa.Integer))
    op.create_table("stock_snapshots", sa.Column("variant_id", sa.Integer, nullable=False), sa.Column("warehouse_id", sa.Integer, nullable=False),
                    sa.Column("snapshot_date", sa.Date, nullable=False), sa.Column("on_hand", sa.Integer, nullable=False),
                    sa.Column("available", sa.Integer, nullable=False), sa.Column("reserved", sa.Integer, nullable=False),
                    sa.UniqueConstraint("variant_id", "warehouse_id", "snapshot_date", name="uq_snapshot"))
    op.create_table("stock_lots", sa.Column("variant_id", sa.Integer, nullable=False), sa.Column("warehouse_id", sa.Integer, nullable=False),
                    sa.Column("batch_number", sa.String(60)), sa.Column("expiry_date", sa.Date), sa.Column("quantity", sa.Integer, nullable=False),
                    sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("stock_movements", sa.Column("external_id", sa.BigInteger, primary_key=True, autoincrement=False),
                    sa.Column("created_at_utc", sa.DateTime(timezone=True)), sa.Column("created_at_raw", sa.String(40), nullable=False),
                    sa.Column("variant_id", sa.Integer, nullable=False), sa.Column("warehouse_id", sa.Integer, nullable=False),
                    sa.Column("quantity", sa.Integer, nullable=False), sa.Column("movement_type", sa.String(10)),
                    sa.Column("reason", sa.String(40), nullable=False), sa.Column("reference_type", sa.String(40)),
                    sa.Column("reference_id", sa.BigInteger), sa.Column("reference_number", sa.String(60)),
                    sa.Column("batch_number", sa.String(60)), sa.Column("expiry_date", sa.Date), sa.Column("unit_cost", sa.Numeric(18, 6)),
                    sa.Column("has_note", sa.Boolean, nullable=False, server_default=sa.false()),
                    sa.Column("quarantined", sa.Boolean, nullable=False, server_default=sa.false()))
    op.create_index("ix_movements_variant_created", "stock_movements", ["variant_id", "created_at_utc"])
    op.create_table("outbox", sa.Column("event_id", sa.String(36), primary_key=True), sa.Column("type", sa.String(120), nullable=False),
                    sa.Column("envelope", sa.JSON, nullable=False), sa.Column("status", sa.String(12), nullable=False),
                    sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("sent_at", sa.DateTime(timezone=True)))
    op.create_table("inbox", sa.Column("event_id", sa.String(36), primary_key=True), sa.Column("type", sa.String(120), nullable=False),
                    sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    for t in ("inbox", "outbox", "stock_movements", "stock_lots", "stock_snapshots", "variants", "products", "warehouses"):
        op.drop_table(t)
