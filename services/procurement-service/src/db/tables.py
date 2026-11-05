"""Core tables for schema ``procurement`` (mirrors migrations/versions/0001_costs.py)."""

from __future__ import annotations

from mmi_common.outbox import inbox_table, outbox_table
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
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
    Column("sku", String(60)),                               # catalogue attributes for exports only; never a key
    Column("name", String(200)),
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
proposals = Table(
    "proposals", metadata,
    Column("id", String(36), primary_key=True),
    Column("week", String(10), nullable=False, index=True),            # ISO week, e.g. 2026-W45
    Column("status", String(12), nullable=False),                       # draft / submitted / approved / exported / superseded
    Column("created_by", String(120), nullable=False),
    Column("last_edited_by", String(120), nullable=False),
    Column("version", Integer, nullable=False, default=1),             # optimistic concurrency token
    Column("inputs_hash", String(64), nullable=False),
    Column("rule_versions", JSON, nullable=False),
    Column("solver_status", String(20), nullable=False),
    Column("budget", MONEY),
    Column("flags", JSON, nullable=False),                              # shortfall options, notes
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("submitted_at", DateTime(timezone=True)),
)
proposal_lines = Table(
    "proposal_lines", metadata,
    Column("id", String(36), primary_key=True),
    Column("proposal_id", String(36), ForeignKey("proposals.id"), nullable=False, index=True),
    Column("variant_id", Integer, nullable=False),
    Column("product_id", Integer, nullable=False),
    Column("supplier_id", String(36), nullable=False),
    Column("qty", Integer, nullable=False),
    Column("unit_cost_with_recargo", MONEY, nullable=False),
    Column("line_total", MONEY, nullable=False),
    Column("forecast_or_policy", String(30), nullable=False),
    Column("safety_stock", Integer),
    Column("constraints_applied", JSON, nullable=False),
    Column("risk", String(8), nullable=False),
    Column("confidence", String(8), nullable=False),
    Column("explanation", JSON, nullable=False),
    Column("alternatives_compared", JSON, nullable=False),
    Column("manual_override", Boolean, nullable=False, default=False),
    Column("topup", Boolean, nullable=False, default=False),
    UniqueConstraint("proposal_id", "variant_id", name="uq_line_variant"),
)
replenishment_targets = Table(
    "replenishment_targets", metadata,
    Column("proposal_id", String(36), primary_key=True),
    Column("variant_id", Integer, primary_key=True, autoincrement=False),
    Column("protection_horizon_days", Integer, nullable=False),
    Column("expected_demand", Float),
    Column("safety_stock", Integer),
    Column("target_level", Integer, nullable=False),
    Column("inventory_position", Integer, nullable=False),
    Column("inputs_hash", String(64), nullable=False),
)
supplier_order_groups = Table(
    "supplier_order_groups", metadata,
    Column("proposal_id", String(36), primary_key=True),
    Column("supplier_id", String(36), primary_key=True),
    Column("subtotal", MONEY, nullable=False),
    Column("delivery_charge", MONEY, nullable=False),
    Column("total_cost", MONEY, nullable=False),
    Column("expected_delivery_date", Date),
    Column("minimum_status", String(10), nullable=False),                # met / topped_up / shortfall
    Column("free_delivery", Boolean, nullable=False, default=False),
    Column("shortfall_options", JSON, nullable=False),
)
approvals = Table(
    "approvals", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("proposal_id", String(36), nullable=False, index=True),
    Column("approver_id", String(120), nullable=False),
    Column("decided_at", DateTime(timezone=True), nullable=False),
    Column("decision", String(10), nullable=False),                     # approved / rejected
    Column("mfa_auth_time", DateTime(timezone=True), nullable=False),
    Column("proposal_version", Integer, nullable=False),
)
inbound_orders = Table(
    "inbound_orders", metadata,
    Column("id", String(36), primary_key=True),
    Column("proposal_id", String(36), nullable=False),
    Column("supplier_id", String(36), nullable=False),
    Column("status", String(20), nullable=False),                       # confirmed / partially_received / received / cancelled
    Column("confirmed_by", String(120), nullable=False),
    Column("confirmed_at", DateTime(timezone=True), nullable=False),
    Column("expected_delivery", Date),
    Column("erp_purchase_ref", Integer),                                # buyer may link the ERP purchase number
    UniqueConstraint("proposal_id", "supplier_id", name="uq_order_per_supplier"),
)
inbound_order_lines = Table(
    "inbound_order_lines", metadata,
    Column("order_id", String(36), primary_key=True),
    Column("variant_id", Integer, primary_key=True, autoincrement=False),
    Column("qty", Integer, nullable=False),
    Column("confirmed_cost_with_recargo", MONEY, nullable=False),
    Column("received_qty", Integer, nullable=False, default=0),
)
receipt_matches = Table(
    "receipt_matches", metadata,
    Column("movement_id", BigInteger, primary_key=True, autoincrement=False),     # each receipt movement is applied once
    Column("order_id", String(36), nullable=False),
    Column("variant_id", Integer, nullable=False),
    Column("qty", Integer, nullable=False),
    Column("matched_at", DateTime(timezone=True), nullable=False),
)
cost_write_requests = Table(
    "cost_write_requests", metadata,
    Column("id", String(36), primary_key=True),
    Column("cost_id", String(36), nullable=False),
    Column("product_id", Integer, nullable=False),
    Column("supplier_id", String(36), nullable=False),
    Column("trigger", String(16), nullable=False),                      # missing_cost / order_confirmed
    Column("proposed_value", MONEY, nullable=False),
    Column("previous_siweb_value", MONEY),
    Column("status", String(16), nullable=False),
    Column("attempts", Integer, nullable=False, default=0),
    Column("last_error", String(200)),
    Column("requested_by", String(120), nullable=False),
    Column("reviewed_by", String(120)),
    Column("idempotency_key", String(120), nullable=False, unique=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
user_roles = Table(
    "user_roles", metadata,
    Column("user_id", String(120), primary_key=True),
    Column("roles", JSON, nullable=False),
    Column("active", Boolean, nullable=False, default=True),
    Column("updated_by", String(120), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
forecast_runs_seen = Table(
    "forecast_runs_seen", metadata,
    Column("run_id", String(36), primary_key=True),
    Column("input_hash", String(64), nullable=False),
    Column("eligible_count", Integer, nullable=False),
    Column("received_at", DateTime(timezone=True), nullable=False),
)
receipt_cursor = Table(
    "receipt_cursor", metadata,
    Column("id", Integer, primary_key=True, autoincrement=False),       # always 1
    Column("last_movement_id", BigInteger, nullable=False),
)
outbox = outbox_table(metadata)
inbox = inbox_table(metadata)
