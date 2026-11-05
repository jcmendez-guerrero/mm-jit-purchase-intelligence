# Data Model: MMI 002 — Operational Console

Conventions are those of 001: UUID `id`, UTC timestamps plus original strings where applicable, money `NUMERIC(18,4)` EUR, products keyed by Siweb `variant_id`, `source` and `schema_version`, no cross-schema SQL, free-text notes never stored. All editable rows carry `revision` (integer, optimistic concurrency) and every change appends to the owning service's hash-chained audit. **Existing** = already in PR #1; **Extend** = add columns; **New** = new table.

## Schema `bff` (api-bff) — New

| Table | Key fields | Rules |
|---|---|---|
| user_roles | user_id (unique), roles (subset of viewer/buyer/approver/admin), active, revision, updated_at, updated_by | Survives restart; admin-only changes; last admin cannot be removed |
| role_audit | id, user_id, before_roles, after_roles, actor, at, prev_hash, hash | Append-only, hash-chained |
| role_mirror_outbox | id, user_id, roles_snapshot, status (pending/sent/failed), attempts, last_error_key, next_attempt_at | Relay calls procurement internal endpoint; failures visible in Admin |

## Schema `procurement`

| Table | State | Key fields | Rules |
|---|---|---|---|
| supplier_terms | Extend | supplier_id, version, valid_from, valid_to, lead_time_days, order_days, order_cutoff_time, delivery_weekdays, min_order_value, min_qty_for_delivery, free_delivery_threshold, delivery_charge, discounts (list: type pct/amount, threshold basis value/qty, threshold, value), payment_terms_days, preferred (bool), reliability (0–100, nullable), disabled (bool), source (erp/import/manual), reason, changed_by | Append-only; no overlapping windows per supplier; threshold ≥ minimum order; non-negative amounts; weekdays unique 1..7 |
| product_supplier_terms | New | variant_id, supplier_id, version, valid_from, valid_to, same term fields as above (all nullable = inherit), pack_multiple, min_qty_units, min_order_value, preferred, disabled, source, reason, changed_by | Most specific value wins (ADR-019); no ERP write |
| terms_conflicts | New (derived view/table) | variant_id, supplier_id, field, erp_value, local_value, winner, detected_at | Shown with conflict badge; no silent override |
| policy_sets | New | id, scope (global/segment/product), key, service_level, safety_stock_units, min_units, max_units, replenishment_cadence_days, valid_from, valid_to, revision, changed_by | Ranges validated; supersedes `service-levels` ownership (R2) via migration |
| budget_caps | New | id, period (week/month), scope (global/supplier/category), amount EUR, valid_from, valid_to, revision | Clinical-critical needs shown if cap insufficient |
| scenarios | New | id, name, base_run_ref, parameters (budget, disabled suppliers, terms deltas, service-level deltas), status (computing/ready/failed/promoted), created_by, input_versions (terms, policy, dataset ids), result_hash, created_at | Never writes live tables |
| scenario_results | New | scenario_id, supplier_id, lines (variant, qty, unit_cost, discount, shipping), order_total, expected_delivery, budget_utilisation, binding_constraints (key + params) | Reproducible from `input_versions` |
| scenario_sensitivity | New | scenario_id, constraint_key, delta, cost_impact | Top N binding constraints only |
| lot_acquisition_costs | New | id, variant_id, lot (batch_number), received_at, quantity, unit_cost EUR, source (confirmed_order/receipt/import/manual), source_ref, recorded_by, revision | Append-only; unit_cost ≥ 0; never taken from ERP movement price (PVP); feeds inventory value and the median suggestion; changes emit `procurement.lot_cost.changed.v1` |
| cost_write_requests | Extend | + suggested_median_cost, + suggestion_lot_refs | Suggestion is advisory; release, fresh MFA and writer checks unchanged |
| user_roles | Existing | mirror of BFF roles | Written only through the internal endpoint |
| proposals / proposal_lines | Extend | + scenario_id (nullable), + terms_version_ids, + policy_version_ids, + dataset_version_id | Every proposal records versions used (FR-026) |

## Schema `forecasting`

| Table | State | Key fields | Rules |
|---|---|---|---|
| seed_datasets | New | id, version, name, status (uploaded/validated/approved/active/superseded/rolled_back/rejected), kind_summary, origin (synthetic/real), file_ref, file_sha256, uploader, uploaded_at, activated_by, activated_at, supersedes_id, row_counts (accepted/quarantined/rejected) | One active per scope; mixed origin refused; duplicate checksum flagged |
| seed_mappings | New | id, name, column_map, created_by | Reusable |
| seed_rows | New | dataset_id, row_no, variant_id, day, warehouse_external_id (nullable), quantity, kind (observed_external/estimated/manual_forecast), provenance_label | Quantity ≥ 0; variant must exist; date range sane |
| seed_quarantine | New | dataset_id, row_no, reason_key, reason_params, raw_row_hash | Spanish message rendered from key; no raw notes stored |
| forecast_parameters | New | id, scope, key, value, valid_from, valid_to, revision, changed_by | Allowed keys/ranges from an approved list |
| forecast_runs | Extend | + dataset_version_id, + parameter_version_ids, + terms/policy refs (ids only), + seed_used (bool per variant in values) | Seeds flagged in output |
| forecast_accuracy | New | run_id, segment, metric (WAPE/bias/stockout-rate), value, window | Source for accuracy chart |
| import_jobs | New | id, dataset_id, stage, state, started_at, finished_at, error_key | Visible in Admin; idempotent re-run |

## Schema `inventory`

| Table | State | Key fields | Rules |
|---|---|---|---|
| demand_exclusions | New | id, variant_id (nullable = all), from_day, to_day, reason, revision, changed_by | Excluded days not used by forecast; reversible; audited |
| censoring_rules | New | id, rule (e.g. min consecutive zero-stock days), value, valid_from, revision | Replaces fixed constants |
| lot_cost_projection | New | variant_id, lot, unit_cost, source, updated_at | Read-only copy fed by procurement events; no cross-schema SQL |
| agg_daily_kpis | New | day, warehouse_id (nullable), category_id (nullable), supplier_id (nullable), inventory_value (quantity per lot × lot acquisition cost), valued_with_estimate_count, coverage_days_avg, stockout_risk_count, expiring_value, refreshed_at | Refreshed by existing worker pass |
| agg_demand_trend | New | day, variant_id/segment key, actual_qty, forecast_mean, forecast_low, forecast_high | Actual from ERP only; estimates labelled separately |
| agg_abc_xyz | New | day, abc, xyz, variant_count, value | Distribution chart |
| filter_options | New (view) | kind (warehouse/category), id, label | No hard-coded options |

## Relationships and state transitions

- `seed_datasets`: uploaded → validated → approved → active → superseded; active → rolled_back (restores `supersedes_id` as active); any → rejected. Activation and rollback are single transactions that also enqueue a versioned forecast run (outbox).
- `scenarios`: computing → ready → promoted | failed. Promotion creates a draft `proposal` through the existing path; it then follows draft → submitted → approved with separation of duties.
- Terms/policies: new version closes the previous `valid_to` only if it overlaps; future-dated versions become effective on `valid_from`.

## Validation rules (examples)

Negative amounts, thresholds below minimum, impossible weekdays/windows, service level outside 0–100, `max < min`, unknown variant, negative or non-numeric quantity, date outside plausible range (default: not before 2015 and not more than 18 months ahead), duplicate (variant, day, kind) within a file, mixed origin.
