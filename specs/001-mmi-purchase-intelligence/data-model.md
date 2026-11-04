# Data Model: Mundo Mascotix Intelligence

Conventions for every table: stable internal `id` (UUID), `external_id` where sourced from Siweb, `created_at`/`updated_at` in UTC, `source` + `schema_version`, idempotency/unique keys as listed. Money is `NUMERIC(18,4)` EUR with explicit `currency` (ISO). No cross-schema SQL; other services read via API or their own projections. Variants are keyed by Siweb `variant_id`; SKU is an attribute only.

## Schema `integration` (siweb-connector)

| Table | Key fields | Rules |
|---|---|---|
| sync_runs | id, kind (warehouses/products/variants/movements/suppliers/stock), window_start/end, frozen_date_to, status, counts_fetched/stored/errors, siweb_total, reconciled (bool), requests_used | Reconciled only if stored+errors = siweb_total |
| sync_checkpoints | kind, last_movement_id, last_created_at, backfill_cursor | One row per kind; advanced only after a run commits |
| external_mappings | entity, external_id, internal_id | Unique (entity, external_id) |
| import_errors | id, run_id, entity, external_id, error_code, detail (no PII), status (open/resolved/ignored), resolved_by | Quarantine list (spec FR-005); malformed dates, unreferenced sales, missing warehouse |
| raw_payload_index | blob_uri, run_id, sha256, fetched_at, expires_at | Payloads stripped of `supplier_cif` and `notes` before write |
| rate_budget_log | hour_bucket, used, denied | For quota alerts |
| outbox | event_id, type, payload_ref, status, attempts | Relay writes one message per subscribed queue |

## Schema `inventory`

| Table | Key fields | Rules |
|---|---|---|
| warehouses | id, external_id, name, is_unassigned | Explicit "unassigned" row |
| products | id, external_id, name, status (active/discontinued), missed_syncs, vat_rate (nullable), clinical_critical (bool, manual) | Tombstone after N missed syncs (default 3); `vat_rate` buyer-maintained unless Siweb provides it |
| variants | id, external_id (variant_id), product_id, sku, pack_size, uom, reorder_point | Pack/UoM explicit |
| stock_snapshots | variant_id, warehouse_id, snapshot_date, on_hand, available, reserved | Unique (variant, warehouse, date) |
| stock_lots | variant_id, warehouse_id, batch_number, expiry_date, quantity, seen_at | Malformed expiry → import_errors, never stored |
| stock_movements | external_id, created_at_utc, created_at_raw, variant_id, warehouse_id, quantity (signed), movement_type, reason, reference_type, reference_id, reference_number, batch_number, expiry_date, unit_cost, has_note, quarantined (bool) | Unique external_id; `notes` never stored |
| demand_observations | variant_id, warehouse_id, day, demand_qty, censored (bool), lineage (movement ids hash) | demand = sale_shipment − return_customer |
| flow_series | variant_id, warehouse_id, day, flow (loss_unclassified/loss_unspecified/expiry/damage/theft/transfer/adjustment/…), qty | Losses never counted as demand |
| stock_history | variant_id, warehouse_id, day, on_hand_reconstructed, reconciled_ok | Rebuilt backwards; mismatch vs forward snapshot flags ineligibility |
| product_segments | variant_id, abc, xyz, pattern (smooth/intermittent/lumpy/new/discontinued), forecast_eligible, reason, computed_at, run_id | |
| service_level_config | scope (segment/product), key, target, valid_from, changed_by | History retained; applies to later proposals only |
| data_quality_metrics | day, metric, value | e.g. share of post-cutover negative adjustments without structured reason |
| config_loss_cutover | effective_date, changed_by | Change reclassifies history, audited |

## Schema `forecasting`

| Table | Key fields |
|---|---|
| forecast_runs | id, started_at, model_versions, input_hash, status |
| forecast_values | run_id, variant_id, horizon_days, mean, quantiles, policy_used |
| backtest_metrics | run_id, segment, policy, stockout_cost, holding_cost, expiry_cost, windows |
| model_registry | name, version, params_hash, artifact_uri, adopted_for_segment |

## Schema `procurement`

| Table | Key fields | Rules |
|---|---|---|
| suppliers | id, external_contact_id, name | `supplier_cif` never stored |
| supplier_terms | supplier_id, min_order_value, min_qty_for_delivery, free_delivery_threshold, delivery_charge, order_days, delivery_schedule, valid_from, changed_by | Versioned; buyer-maintained |
| supplier_costs | id, product_id, supplier_id, variant_id (nullable override), version, cost_net, recargo_rate, cost_with_recargo, entered_includes_recargo, vat_rate_used, currency, pack_size, lead_time_days, min_order_qty, source (siweb_product_supplier/csv_price_list/manual), verified_at, verified_by, superseded_by | Immutable; new row per change; jump flag and `jump_confirmed_by` |
| cost_write_requests | id, cost_id, trigger (missing_cost/order_confirmed), proposed_value, previous_siweb_value, status (pending_review/approved_by_buyer/pending_link/sent/succeeded/failed/retrying/cancelled), attempts, last_error, requested_by, reviewed_by, idempotency_key | Unique idempotency_key; visible in UI until succeeded |
| replenishment_targets | variant_id, protection_horizon_days, expected_demand, safety_stock, target_level, inventory_position, inputs_hash | |
| proposals | id, week, status (draft/submitted/approved/exported/superseded), created_by, last_edited_by, version, inputs_hash, rule_versions, solver_status | Optimistic concurrency on `version` |
| proposal_lines | proposal_id, variant_id, supplier_id, qty, unit_cost_with_recargo, line_total, forecast_or_policy, safety_stock, constraints_applied, risk, confidence, explanation (structured JSON + rendered es-ES), alternatives_compared, manual_override | |
| supplier_order_groups | proposal_id, supplier_id, total_cost, delivery_charge, expected_delivery_date, minimum_status (met/topped_up/shortfall), shortfall_options | Supplier-grouped view |
| approvals | proposal_id, approver_id, decided_at, decision, mfa_auth_time, proposal_version | Refused if approver = creator or last editor |
| inbound_orders | id, proposal_id, supplier_id, status (confirmed/partially_received/received/cancelled), confirmed_by, confirmed_at, expected_delivery | Created at order confirmation |
| inbound_order_lines | order_id, variant_id, qty, confirmed_cost_with_recargo, received_qty | Matched to `purchase_receipt` movements (plain id or "Compra #n") |
| audit_events | id, ts, actor, action, entity, entity_id, before, after, prev_hash, hash | Hash-chained, append-only |
| outbox / inbox | as in integration | Inbox dedups by event_id |

## Schema `costwrite` (siweb-cost-writer)

| Table | Key fields |
|---|---|
| write_attempts | request_id, attempt_no, started_at, http_status, outcome, verified_after_write (bool), error_class |
| writer_audit | request_id, actor_ref, product_id, supplier_contact_id, previous_cost, new_cost, ts, hash chain |

## Key state transitions

```
Proposal:   draft ──submit──▶ submitted ──approve (≠ creator/last editor, fresh MFA)──▶ approved ──export/read──▶ exported
              ▲                  │ edit after submit → back to draft, approval eligibility reset
Order:      approved ──buyer confirms per supplier (qty + cost)──▶ confirmed ──receipts──▶ partially_received ──▶ received
CostWrite:  pending_review ──buyer approves──▶ sent ──▶ succeeded | failed ──▶ retrying ──▶ succeeded | cancelled
Import:     movement ──valid──▶ stored ; invalid/ambiguous ──▶ import_errors(open) ──resolve──▶ released or ignored
Product:    active ──missed N syncs──▶ discontinued ──reappears──▶ active
```

## Validation rules (from spec)

- `cost_with_recargo = cost_net × (1 + recargo_rate)`; rate lookup by `vat_rate` (10 → 1.4 %, 21 → 5.2 %, from a versioned config); unknown rate → net entry rejected.
- A product-supplier pair can enter a proposal only with a non-stale, non-blocked cost.
- Variant overrides that differ for one product trigger a warning before any cost write (Siweb stores supplier cost per product).
- Quantities respect pack multiples and supplier minimums, or the shortfall is explicit.
- Proposal regeneration with identical `inputs_hash` and `rule_versions` yields identical lines.
