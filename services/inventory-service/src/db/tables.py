"""Core tables for schema ``inventory`` (mirrors migrations/versions/0001_inventory.py).

Keys are Siweb ids (AGENTS.md rule 5: products are keyed by ``variant_id``). Free-text notes have no column,
only ``has_note``. The schema comes from the role's search_path, so the unit tests run on SQLite.
"""

from __future__ import annotations

from mmi_common.outbox import inbox_table, outbox_table
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    UniqueConstraint,
)

metadata = MetaData()
ALL_WAREHOUSES = -1   # company-wide snapshot until per-warehouse lots are synced
UNASSIGNED_WAREHOUSE = 0

warehouses = Table(
    "warehouses", metadata,
    Column("external_id", Integer, primary_key=True, autoincrement=False),
    Column("name", String(120), nullable=False),
    Column("is_unassigned", Boolean, nullable=False, default=False),
)
products = Table(
    "products", metadata,
    Column("external_id", Integer, primary_key=True, autoincrement=False),
    Column("name", String(200), nullable=False),
    Column("status", String(12), nullable=False, default="active"),  # active / discontinued
    Column("missed_syncs", Integer, nullable=False, default=0),
    Column("vat_rate", Numeric(5, 2)),                               # buyer-maintained unless Siweb provides it
    Column("clinical_critical", Boolean, nullable=False, default=False),
)
variants = Table(
    "variants", metadata,
    Column("external_id", Integer, primary_key=True, autoincrement=False),  # Siweb variant_id
    Column("product_id", Integer, ForeignKey("products.external_id")),
    Column("sku", String(60)),
    Column("name", String(200)),
    Column("pack_size", Integer),
    Column("uom", String(20)),
    Column("reorder_point", Integer),
)
stock_snapshots = Table(
    "stock_snapshots", metadata,
    Column("variant_id", Integer, nullable=False),
    Column("warehouse_id", Integer, nullable=False),
    Column("snapshot_date", Date, nullable=False),
    Column("on_hand", Integer, nullable=False),
    Column("available", Integer, nullable=False),
    Column("reserved", Integer, nullable=False),
    UniqueConstraint("variant_id", "warehouse_id", "snapshot_date", name="uq_snapshot"),
)
stock_lots = Table(
    "stock_lots", metadata,
    Column("variant_id", Integer, nullable=False),
    Column("warehouse_id", Integer, nullable=False),
    Column("batch_number", String(60)),
    Column("expiry_date", Date),
    Column("quantity", Integer, nullable=False),
    Column("seen_at", DateTime(timezone=True), nullable=False),
)
stock_movements = Table(
    "stock_movements", metadata,
    Column("external_id", BigInteger, primary_key=True, autoincrement=False),
    Column("created_at_utc", DateTime(timezone=True)),
    Column("created_at_raw", String(40), nullable=False),
    Column("variant_id", Integer, nullable=False),
    Column("warehouse_id", Integer, nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("movement_type", String(10)),
    Column("reason", String(40), nullable=False),
    Column("reference_type", String(40)),
    Column("reference_id", BigInteger),
    Column("reference_number", String(60)),
    Column("batch_number", String(60)),
    Column("expiry_date", Date),
    Column("unit_cost", Numeric(18, 6)),
    Column("has_note", Boolean, nullable=False, default=False),
    Column("quarantined", Boolean, nullable=False, default=False),
)
outbox = outbox_table(metadata)
inbox = inbox_table(metadata)
