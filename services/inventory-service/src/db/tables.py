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
    Column("family", String(120)),                                    # ERP product family as synchronised: a dashboard filter option only
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
    Column("price_confirmed_at", DateTime(timezone=True)),  # last successful sync that carried this price (stale after 7 days)
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

inbound_lines = Table(
    "inbound_lines", metadata,
    Column("order_id", String(36), primary_key=True),
    Column("variant_id", Integer, primary_key=True, autoincrement=False),
    Column("proposal_id", String(36), nullable=False),
    Column("supplier_id", String(36), nullable=False),
    Column("qty", Integer, nullable=False),
    Column("confirmed_at", DateTime(timezone=True), nullable=False),
)


# ---- MMI 002 (migration 0005): category history, demand rules, dashboard aggregates, lot-cost projection, audit ----
segment_history = Table(
    "segment_history", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("variant_id", Integer, nullable=False, index=True),
    Column("changed_at", DateTime(timezone=True), nullable=False),
    Column("abc", String(1), nullable=False),
    Column("xyz", String(1), nullable=False),
    Column("pattern", String(14), nullable=False),
    Column("critical", Boolean, nullable=False, default=False),         # manual flag, never inferred
    Column("reason_key", String(60), nullable=False),                    # why the category changed (stable code)
    Column("run_id", String(36), nullable=False),
)
demand_exclusions = Table(
    "demand_exclusions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("variant_id", Integer),                                       # NULL = all products
    Column("from_day", Date, nullable=False),
    Column("to_day", Date, nullable=False),
    Column("reason", String(500), nullable=False),
    Column("active", Boolean, nullable=False, default=True),             # reversible: deactivate, never delete
    Column("revision", Integer, nullable=False, default=1),
    Column("changed_by", String(120), nullable=False),
)
censoring_rules = Table(
    "censoring_rules", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("rule", String(40), nullable=False),
    Column("value", Integer, nullable=False),
    Column("valid_from", Date, nullable=False),
    Column("revision", Integer, nullable=False, default=1),
    Column("changed_by", String(120), nullable=False),
)
agg_daily_kpis = Table(
    "agg_daily_kpis", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("day", Date, nullable=False, index=True),
    Column("warehouse_id", Integer),
    Column("category_id", String(40)),
    Column("supplier_id", String(36)),
    Column("inventory_value", Numeric(18, 4), nullable=False),           # quantity per lot x lot acquisition cost (FR-041)
    Column("valued_with_estimate_count", Integer, nullable=False, default=0),
    Column("coverage_days_avg", Numeric(10, 2)),
    Column("stockout_risk_count", Integer, nullable=False, default=0),
    Column("expiring_value", Numeric(18, 4), nullable=False, default=0),
    Column("refreshed_at", DateTime(timezone=True), nullable=False),
)
agg_demand_trend = Table(
    "agg_demand_trend", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("day", Date, nullable=False, index=True),
    Column("scope_key", String(40), nullable=False),                     # variant id or segment key
    Column("actual_qty", Numeric(18, 4)),                                # ERP-derived demand only
    Column("estimated_qty", Numeric(18, 4)),                             # imported estimates, kept apart and labelled
    Column("forecast_mean", Numeric(18, 4)),
    Column("forecast_low", Numeric(18, 4)),
    Column("forecast_high", Numeric(18, 4)),
)
agg_abc_xyz = Table(
    "agg_abc_xyz", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("day", Date, nullable=False, index=True),
    Column("abc", String(1), nullable=False),
    Column("xyz", String(1), nullable=False),
    Column("variant_count", Integer, nullable=False),
    Column("value", Numeric(18, 4), nullable=False),
)
lot_cost_projection = Table(
    "lot_cost_projection", metadata,
    Column("variant_id", Integer, primary_key=True, autoincrement=False),
    Column("supplier_id", String(36), primary_key=True),
    Column("lot", String(60), primary_key=True),
    Column("unit_cost", Numeric(18, 4), nullable=False),                 # Recargo-inclusive acquisition cost (never PVP)
    Column("source", String(20), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
audit_events = Table(
    "audit_events", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("actor", String(120), nullable=False),
    Column("action", String(40), nullable=False),
    Column("entity", String(30), nullable=False),
    Column("entity_id", String(60), nullable=False),
    Column("before", JSON),
    Column("after", JSON),
    Column("prev_hash", String(64), nullable=False, unique=True),
    Column("hash", String(64), nullable=False),
)
