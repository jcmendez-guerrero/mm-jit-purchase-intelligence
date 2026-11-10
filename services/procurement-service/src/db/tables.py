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
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    UniqueConstraint,
    false,
)

metadata = MetaData()
MONEY = Numeric(18, 4)

suppliers = Table(
    "suppliers", metadata,
    Column("id", String(36), primary_key=True),
    Column("external_contact_id", Integer, unique=True),   # Siweb contact id; supplier_cif is never stored
    Column("name", String(200), nullable=False),
    # MMI 004 (migration 0011): suppliers can be created and configured in the platform. Never stored: tax id, bank, notes.
    Column("name_key", String(200), nullable=False, server_default="", index=True),   # folded name, duplicate detection only
    Column("status", String(12), nullable=False, server_default="active"),            # active / deactivated
    Column("classification", String(16), nullable=False, server_default="unclassified"),   # purchasing / non_purchasing / unclassified
    Column("origin", String(10), nullable=False, server_default="platform"),          # platform / imported / erp
    Column("erp_link_state", String(12), nullable=False, server_default="none"),      # none / unverified / linked / pending_link
    Column("fiscal_type", String(16), nullable=False, server_default="national"),
    Column("country", String(2), nullable=False, server_default="ES"),
    Column("currency", String(3), nullable=False, server_default="EUR"),
    Column("payment_terms_days", Integer),
    Column("order_channel", String(8)),
    Column("has_note", Boolean, nullable=False, server_default=false()),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("created_by", String(120)),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_by", String(120)),
    Column("updated_at", DateTime(timezone=True)),
    Column("deactivated_by", String(120)),
    Column("deactivated_at", DateTime(timezone=True)),
    Column("merged_into", String(36)),                       # explicit merge pointer (the merged supplier is deactivated, history kept)
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
    # MMI 002 (migration 0005): effective-dated commercial terms, ADR-019 (never written to the ERP)
    Column("version", Integer, nullable=False, default=1, server_default="1"),
    Column("valid_to", DateTime(timezone=True)),
    Column("lead_time_days", Integer),
    Column("order_cutoff_time", String(5)),
    Column("delivery_weekdays", JSON),
    Column("discounts", JSON),
    Column("payment_terms_days", Integer),
    Column("preferred", Boolean, nullable=False, default=False, server_default=false()),
    Column("reliability", Integer),
    Column("disabled", Boolean, nullable=False, default=False, server_default=false()),
    Column("source", String(10), nullable=False, default="manual", server_default="manual"),   # erp / import / manual
    Column("reason", String(500)),
    Column("revision", Integer, nullable=False, default=1, server_default="1"),
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
    # MMI 002 (migration 0007): exact versions behind the proposal (FR-026)
    Column("scenario_id", String(36)),
    Column("terms_version_ids", JSON),
    Column("policy_version_ids", JSON),
    Column("dataset_version_id", String(36)),
    Column("forecast_run_id", String(36)),
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
    Column("discount", MONEY, nullable=False, default=0, server_default="0"),         # MMI 002: supplier order discount applied (migration 0010)
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
    # MMI 002 (migration 0008): the released value is the median of lot costs; margin check; admin override (FR-042..044)
    Column("median_cost", MONEY),
    Column("median_lot_refs", JSON),                                    # lots used with their quantities at lookup time
    Column("pvp_used", MONEY),
    Column("pvp_age_days", Integer),                                    # days since a sync last confirmed the price (FR-043: stale after 7)
    Column("margin_before", Numeric(7, 4)),
    Column("margin_after", Numeric(7, 4)),
    Column("rule_flags", JSON),
    Column("override_value", MONEY),
    Column("override_reason", String(500)),
    Column("override_by", String(120)),
    Column("override_at", DateTime(timezone=True)),
    Column("released_by", String(120)),                                 # must differ from override_by when an override exists
)
user_roles = Table(
    "user_roles", metadata,
    Column("user_id", String(120), primary_key=True),
    Column("roles", JSON, nullable=False),
    Column("active", Boolean, nullable=False, default=True),
    Column("updated_by", String(120), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("revision", Integer, nullable=False, default=0, server_default="0"),   # BFF role revision; older mirrors are ignored (MMI 002)
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


# ---- MMI 002 new tables: product-supplier terms (0005), policies and stocking (0006), scenarios (0007), lot costs (0008) ----
product_supplier_terms = Table(
    "product_supplier_terms", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("variant_id", Integer, nullable=False),
    Column("supplier_id", String(36), ForeignKey("suppliers.id"), nullable=False),
    Column("version", Integer, nullable=False),
    Column("valid_from", DateTime(timezone=True), nullable=False),
    Column("valid_to", DateTime(timezone=True)),
    Column("lead_time_days", Integer),                                  # NULL columns inherit the supplier value (ADR-019)
    Column("order_days", JSON),
    Column("order_cutoff_time", String(5)),
    Column("delivery_weekdays", JSON),
    Column("min_order_value", MONEY),
    Column("min_qty_for_delivery", Integer),
    Column("free_delivery_threshold", MONEY),
    Column("delivery_charge", MONEY),
    Column("discounts", JSON),
    Column("payment_terms_days", Integer),
    Column("preferred", Boolean),
    Column("reliability", Integer),
    Column("disabled", Boolean),
    Column("pack_multiple", Integer),
    Column("min_qty_units", Integer),
    Column("source", String(10), nullable=False),
    Column("reason", String(500)),
    Column("changed_by", String(120), nullable=False),
    Column("revision", Integer, nullable=False, default=1),
    UniqueConstraint("variant_id", "supplier_id", "version", name="uq_product_supplier_terms_version"),
)
policy_sets = Table(
    "policy_sets", metadata,
    Column("id", String(36), primary_key=True),
    Column("scope", String(10), nullable=False),                        # global / segment / product
    Column("key", String(40), nullable=False),
    Column("service_level", Numeric(5, 4)),
    Column("safety_stock_units", Integer),
    Column("min_units", Integer),
    Column("max_units", Integer),
    Column("replenishment_cadence_days", Integer),
    Column("valid_from", Date, nullable=False),
    Column("valid_to", Date),
    Column("revision", Integer, nullable=False, default=1),
    Column("changed_by", String(120), nullable=False),
    UniqueConstraint("scope", "key", "valid_from", "revision", name="uq_policy_sets_effective"),
)
budget_caps = Table(
    "budget_caps", metadata,
    Column("id", String(36), primary_key=True),
    Column("period", String(5), nullable=False),                        # week / month
    Column("scope", String(10), nullable=False),                        # global / supplier / category
    Column("scope_key", String(40)),
    Column("amount", MONEY, nullable=False),
    Column("valid_from", Date, nullable=False),
    Column("valid_to", Date),
    Column("revision", Integer, nullable=False, default=1),
    Column("changed_by", String(120), nullable=False),
)
stocking_settings = Table(
    "stocking_settings", metadata,
    Column("variant_id", Integer, primary_key=True, autoincrement=False),
    Column("stocking_mode", String(14), nullable=False, default="standard"),   # standard / always_stocked / on_request
    Column("min_floor_units", Integer, nullable=False, default=0),
    Column("valid_from", Date),
    Column("revision", Integer, nullable=False, default=1),
    Column("changed_by", String(120), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
policy_override_requests = Table(
    "policy_override_requests", metadata,
    Column("id", String(36), primary_key=True),
    Column("variant_id", Integer, nullable=False, index=True),
    Column("field", String(12), nullable=False),                        # safety_stock / min / max
    Column("recommended_value", Integer, nullable=False),
    Column("requested_value", Integer, nullable=False),
    Column("reason", String(500), nullable=False),
    Column("status", String(10), nullable=False, default="pending"),    # pending / approved / rejected / reverted
    Column("requested_by", String(120), nullable=False),
    Column("requested_at", DateTime(timezone=True), nullable=False),
    Column("decided_by", String(120)),                                  # must differ from requested_by and hold the approver role
    Column("decided_at", DateTime(timezone=True)),
    Column("recommendation_changed", Boolean, nullable=False, default=False),
)
scenarios = Table(
    "scenarios", metadata,
    Column("id", String(36), primary_key=True),
    Column("name", String(200), nullable=False),
    Column("parameters", JSON, nullable=False),
    Column("status", String(10), nullable=False),                       # computing / ready / failed / promoted
    Column("input_versions", JSON),
    Column("result_hash", String(64)),
    Column("idempotency_key", String(120), unique=True),
    Column("created_by", String(120), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("summary", JSON),                                            # baseline and scenario totals, changes with reasons, binding constraints, notes
)
scenario_results = Table(
    "scenario_results", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("scenario_id", String(36), ForeignKey("scenarios.id"), nullable=False, index=True),
    Column("supplier_id", String(36), nullable=False),
    Column("lines", JSON, nullable=False),
    Column("order_total", MONEY, nullable=False),
    Column("subtotal", MONEY),                                        # lines before shipping and discount (FR-029)
    Column("delivery_charge", MONEY),
    Column("discount", MONEY),
    Column("free_delivery", Boolean),
    Column("expected_delivery", Date),
    Column("budget_utilisation", Numeric(8, 4)),
    Column("binding_constraints", JSON),
)
scenario_sensitivity = Table(
    "scenario_sensitivity", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("scenario_id", String(36), ForeignKey("scenarios.id"), nullable=False, index=True),
    Column("constraint_key", String(60), nullable=False),
    Column("delta", String(40), nullable=False),
    Column("cost_impact", MONEY, nullable=False),
)
lot_acquisition_costs = Table(
    "lot_acquisition_costs", metadata,
    Column("id", String(36), primary_key=True),
    Column("variant_id", Integer, nullable=False),
    Column("supplier_id", String(36), ForeignKey("suppliers.id"), nullable=False),
    Column("order_ref", String(60)),
    Column("lot", String(60), nullable=False),
    Column("received_at", DateTime(timezone=True)),
    Column("quantity", Integer, nullable=False, default=0),
    Column("unit_cost", MONEY, nullable=False),                         # Recargo-inclusive; never the ERP movement price (PVP)
    Column("source", String(20), nullable=False),                       # confirmed_order / receipt_correction / buyer_entry
    Column("recorded_by", String(120), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
)
Index("ix_lot_acquisition_costs_pair", lot_acquisition_costs.c.variant_id, lot_acquisition_costs.c.supplier_id, lot_acquisition_costs.c.lot)

# MMI 004 (migration 0011)
supplier_review_items = Table(
    "supplier_review_items", metadata,
    Column("id", String(36), primary_key=True),
    Column("kind", String(32), nullable=False),            # possible_duplicate / payment_terms_unparsed / link_no_match / link_ambiguous / link_inactive_supplier / currency_mismatch
    Column("supplier_id", String(36), ForeignKey("suppliers.id")),
    Column("detail", String(200), nullable=False, server_default=""),   # never personal data
    Column("status", String(10), nullable=False, server_default="open"),   # open / resolved / ignored
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("resolved_by", String(120)),
    Column("resolved_at", DateTime(timezone=True)),
)
link_assignment_batches = Table(
    "link_assignment_batches", metadata,
    Column("id", String(36), primary_key=True),
    Column("created_by", String(120), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("criteria", JSON, nullable=False),
    Column("supplier_id", String(36), ForeignKey("suppliers.id"), nullable=False),
    Column("products_matched", Integer, nullable=False, server_default="0"),
    Column("products_changed", Integer, nullable=False, server_default="0"),
    Column("conflicts", Integer, nullable=False, server_default="0"),
    Column("status", String(10), nullable=False, server_default="previewed"),   # previewed / applied / cancelled
    Column("applied_at", DateTime(timezone=True)),
)
export_costs = Table(
    "export_costs", metadata,
    Column("sku", String(60), primary_key=True),
    Column("export_cost", MONEY),                           # reference only; never a supplier cost, never written to the ERP
    Column("pvp_gross", MONEY),                             # tax-inclusive selling price for the margin check
    Column("tax_rate", Numeric(5, 2)),
    Column("tax_included", Boolean, nullable=False, server_default=false()),
    Column("currency", String(3), nullable=False, server_default="EUR"),
    Column("loaded_at", DateTime(timezone=True), nullable=False),
    Column("load_run_id", String(36)),
)
# MMI-6 / feature 007 (migration 0012)
terms_idempotency = Table(
    "terms_idempotency", metadata,
    Column("scope", String(40), primary_key=True),          # supplier_terms / product_supplier_terms
    Column("key", String(120), primary_key=True),
    Column("request_hash", String(64), nullable=False),
    Column("result_version", Integer, nullable=False),
    Column("actor", String(120), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
)
fx_rates = Table(
    "fx_rates", metadata,
    Column("currency", String(3), primary_key=True),
    Column("published_on", Date, primary_key=True),
    Column("eur_per_unit", Numeric(20, 12), nullable=False),  # exact decimal; EUR per one unit of the currency
    Column("fetched_at", DateTime(timezone=True), nullable=False),
    Column("provider", String(20), nullable=False, server_default="ecb"),
)
