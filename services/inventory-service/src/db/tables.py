"""Core tables for schema ``inventory`` (mirrors migrations/versions/0001_inventory.py).

Keys are Siweb ids (AGENTS.md rule 5: products are keyed by ``variant_id``). Free-text notes have no column,
only ``has_note``. The schema comes from the role's search_path, so the unit tests run on SQLite.
"""

from __future__ import annotations

from mmi_common.outbox import inbox_table, outbox_table
from sqlalchemy import (
    JSON,
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
    Column("price", Numeric(18, 6)),  # selling price in EUR, used only to rank value (ABC)
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
    Column("quarantine_codes", String(120)),
)
outbox = outbox_table(metadata)
inbox = inbox_table(metadata)

demand_observations = Table(
    "demand_observations", metadata,
    Column("variant_id", Integer, primary_key=True, autoincrement=False),
    Column("warehouse_id", Integer, primary_key=True, autoincrement=False),
    Column("day", Date, primary_key=True),
    Column("demand_qty", Integer, nullable=False),
    Column("censored", Boolean, nullable=False, default=False),
    Column("lineage", String(32), nullable=False),  # hash of the contributing movement ids
)
flow_series = Table(
    "flow_series", metadata,
    Column("variant_id", Integer, primary_key=True, autoincrement=False),
    Column("warehouse_id", Integer, primary_key=True, autoincrement=False),
    Column("day", Date, primary_key=True),
    Column("flow", String(30), primary_key=True),
    Column("qty", Integer, nullable=False),
)
stock_history = Table(
    "stock_history", metadata,
    Column("variant_id", Integer, primary_key=True, autoincrement=False),
    Column("warehouse_id", Integer, primary_key=True, autoincrement=False),
    Column("day", Date, primary_key=True),
    Column("on_hand_reconstructed", Integer, nullable=False),
    Column("censored", Boolean, nullable=False, default=False),
    Column("reconciled_ok", Boolean, nullable=False, default=True),
)
data_quality_metrics = Table(
    "data_quality_metrics", metadata,
    Column("day", Date, primary_key=True),
    Column("metric", String(60), primary_key=True),
    Column("value", Numeric(18, 6), nullable=False),
)
config_loss_cutover = Table(
    "config_loss_cutover", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("effective_date", Date, nullable=False),
    Column("changed_by", String(120), nullable=False),
    Column("changed_at", DateTime(timezone=True), nullable=False),
)
review_decisions = Table(
    "review_decisions", metadata,
    Column("external_id", BigInteger, primary_key=True, autoincrement=False),
    Column("decision", String(10), nullable=False),  # confirm / ignore
    Column("decided_by", String(120), nullable=False),
    Column("decided_at", DateTime(timezone=True), nullable=False),
)

product_segments = Table(
    "product_segments", metadata,
    Column("variant_id", Integer, primary_key=True, autoincrement=False),
    Column("abc", String(1), nullable=False),
    Column("xyz", String(1), nullable=False),
    Column("pattern", String(14), nullable=False),  # smooth / intermittent / lumpy / new / discontinued
    Column("forecast_eligible", Boolean, nullable=False),
    Column("reason", String(200), nullable=False),  # comma-separated reason codes; empty when eligible
    Column("metrics", JSON, nullable=False),        # the numbers behind the labels (rationale)
    Column("computed_at", DateTime(timezone=True), nullable=False),
    Column("run_id", String(36), nullable=False),
)
service_level_config = Table(
    "service_level_config", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("scope", String(10), nullable=False),    # abc / critical / sparse / product
    Column("key", String(20), nullable=False),      # A/B/C, "*", or the product id
    Column("target", Numeric(5, 4), nullable=False),
    Column("valid_from", DateTime(timezone=True), nullable=False),
    Column("changed_by", String(120), nullable=False),
)
criticality_changes = Table(
    "criticality_changes", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("product_id", Integer, nullable=False),
    Column("clinical_critical", Boolean, nullable=False),
    Column("changed_by", String(120), nullable=False),
    Column("changed_at", DateTime(timezone=True), nullable=False),
)
