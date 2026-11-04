"""Core tables for schema ``procurement`` (mirrors migrations/versions/0001_costs.py)."""

from __future__ import annotations

from mmi_common.outbox import inbox_table, outbox_table
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
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
MONEY = Numeric(18, 4)

suppliers = Table(
    "suppliers", metadata,
    Column("id", String(36), primary_key=True),
    Column("external_contact_id", Integer, unique=True),   # Siweb contact id; supplier_cif is never stored
    Column("name", String(200), nullable=False),
)
supplier_terms = Table(
    "supplier_terms", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("supplier_id", String(36), ForeignKey("suppliers.id"), nullable=False),
    Column("min_order_value", MONEY),
    Column("min_qty_for_delivery", Integer),
    Column("free_delivery_threshold", MONEY),
    Column("delivery_charge", MONEY),
    Column("order_days", JSON, nullable=False),            # ISO weekdays 1..7
    Column("delivery_schedule", String(200)),
    Column("valid_from", DateTime(timezone=True), nullable=False),
    Column("changed_by", String(120), nullable=False),
)
supplier_costs = Table(
    "supplier_costs", metadata,
    Column("id", String(36), primary_key=True),
    Column("product_id", Integer, nullable=False),
    Column("supplier_id", String(36), ForeignKey("suppliers.id"), nullable=False),
    Column("variant_id", Integer),                           # NULL = product-level; set = per-variant override
    Column("version", Integer, nullable=False),
    Column("cost_net", MONEY),
    Column("recargo_rate", Numeric(6, 4)),                   # fraction, e.g. 0.0520
    Column("cost_with_recargo", MONEY, nullable=False),
    Column("entered_includes_recargo", Boolean, nullable=False),
    Column("vat_rate_used", Numeric(5, 2)),
    Column("currency", String(3), nullable=False, default="EUR"),
    Column("pack_size", Integer),
    Column("lead_time_days", Integer),
    Column("min_order_qty", Integer),
    Column("source", String(24), nullable=False),            # siweb_product_supplier / csv_price_list / manual
    Column("verified_at", DateTime(timezone=True), nullable=False),
    Column("verified_by", String(120)),
    Column("superseded_by", String(36)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("created_by", String(120), nullable=False),
    Column("jump_flag", Boolean, nullable=False, default=False),
    Column("jump_confirmed_by", String(120)),
    Column("jump_confirmed_at", DateTime(timezone=True)),
    UniqueConstraint("product_id", "supplier_id", "variant_id", "version", name="uq_cost_version"),
)
recargo_rates = Table(
    "recargo_rates", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("vat_rate", Numeric(5, 2), nullable=False),
    Column("recargo_rate", Numeric(5, 2), nullable=False),   # percent, e.g. 5.20
    Column("valid_from", DateTime(timezone=True), nullable=False),
    Column("changed_by", String(120), nullable=False),
)
cost_rule_config = Table(
    "cost_rule_config", metadata,
    Column("key", String(30), primary_key=True),             # stale_days / jump_threshold
    Column("value", Numeric(10, 4), nullable=False),
    Column("changed_by", String(120), nullable=False),
    Column("changed_at", DateTime(timezone=True), nullable=False),
)
erp_supplier_links = Table(
    "erp_supplier_links", metadata,
    Column("product_id", Integer, primary_key=True, autoincrement=False),
    Column("supplier_id", String(36), primary_key=True),
    Column("has_cost", Boolean, nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
)
product_refs = Table(
    "product_refs", metadata,
    Column("variant_id", Integer, primary_key=True, autoincrement=False),
    Column("product_id", Integer, nullable=False, index=True),
    Column("vat_rate", Numeric(5, 2)),                       # buyer-maintained until Siweb provides it (V5)
    Column("vat_source", String(20)),
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
outbox = outbox_table(metadata)
inbox = inbox_table(metadata)
