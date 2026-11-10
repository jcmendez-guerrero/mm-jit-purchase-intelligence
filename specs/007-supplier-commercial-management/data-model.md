# Data Model: Supplier Commercial Management

Existing tables are reused unchanged unless noted (`services/procurement-service/src/db/tables.py`).

## Existing (reused)

| Entity | Table | Key fields | Rules |
|---|---|---|---|
| Supplier | `suppliers` | id, name, fiscal type, country, currency, payment terms, active, classification, ERP link state | name duplicate warning (case/accent-insensitive); no tax id or bank details |
| Terms version | `supplier_terms` | supplier_id, `version`, `valid_from`, `valid_to`, lead_time_days, min_order_value, min_qty_for_delivery, free_delivery_threshold, delivery_charge, order_days, delivery_weekdays, order_cutoff_time, discounts (JSON, max 5 tiers), payment_terms_days, preferred, reliability, disabled, source, reason, changed_by | append-only; non-negative money/qty; cutoff `HH:MM`; weekdays ISO 1..7 unique; percent in (0,100]; `free_delivery_threshold >= min_order_value`; window end after start, no start inside another window, no swallowing a later version |
| Product-level override | `product_supplier_terms` | variant_id, supplier_id, `version`, same term columns (NULL inherits), pack_multiple, min_qty_units | same validation; precedence per ADR-019 |
| Cost record | `supplier_costs` | product_id, supplier_id, variant_id, version, cost_net, cost_with_recargo, source, verified_by/at, jump_flag | versioned; manual never overwrites ERP cost silently |
| Audit entry | `audit_events` | actor, action, target, before, after, hash chain | tamper-evident |
| Proposal line | `proposal_lines` + `proposals.terms_version_ids` | explanation.terms (versions, value sources) | versions frozen at generation |

## New (additive migration)

**`terms_idempotency`**

| Field | Type | Notes |
|---|---|---|
| key | string(120) | unique with `scope` |
| scope | string(40) | `supplier_terms` or `product_supplier_terms` |
| request_hash | string(64) | SHA-256 of canonical body + target |
| result_version | integer | version created |
| actor | string(120) | |
| created_at | timestamptz | UTC; rows older than 7 days purged by the worker pass of T038 |

State transition: `absent -> recorded` on first successful save; repeat with same hash returns `result_version`; different hash -> `idempotency_key_reuse` (422).

**`fx_rates`** (filled by the daily rate job, read by proposal generation)

| Field | Type | Notes |
|---|---|---|
| currency | string(3) | ISO code of the supplier currency; unique with `published_on` |
| eur_per_unit | decimal(20,12) | exact decimal; the inverse of the ECB quote for EUR as base (12 decimals so a currency quoted at 17,000 per euro keeps its accuracy) |
| published_on | date | publication date reported by the service |
| fetched_at | timestamptz | UTC fetch time |
| provider | string(20) | always `ecb` |

Rules: a rate is usable for allocation only if `published_on` is at most 7 days before the proposal date; the newest row per currency wins; rows are never edited, and rows older than 400 days are purged by the same worker pass that fetches rates (T038); no other housekeeping exists today. A currency with no row is "unsupported or missing" and leads to exclusion plus a review item.

## Field-name glossary ("minimum order units")

| Spec term | Supplier terms | Product-level override | Cost record |
|---|---|---|---|
| Minimum order units | `min_qty_for_delivery` | `min_qty_units` | `min_order_qty` |
| Minimum order value | `min_order_value` | `min_order_value` | n/a |
| Pack multiple | n/a | `pack_multiple` | `pack_size` |

## New audit actions (no schema change)

`terms.refused`, `supplier.refused`, `link.refused`: payload = actor, target id, error code, HTTP status; never the request body.

## Derived (computed, not stored)

**Expected delivery date** = `delivery_date(next_order_date, longest lead time of the supplier's lines, delivery_weekdays)`, where `next_order_date` is the first order day (order days and the local-time cutoff applied) computed once when the inputs are built and carried in `SupplierTermsIn` (so it is part of the inputs hash and the proposal stays reproducible within a day). A supplier with no order days or cutoff uses today. Pure functions in `terms/schedule.py`; stored per group in `supplier_order_groups.expected_delivery_date` and shown per line in `explanation.terms.expected_delivery_date`.
