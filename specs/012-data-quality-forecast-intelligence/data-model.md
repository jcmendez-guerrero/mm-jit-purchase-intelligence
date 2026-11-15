# Data Model: Data Quality and Forecast Intelligence

All keys use the Siweb `variant_id` (or the reserved SKU-derived surrogate range for feature 004 data, never mixed). Timestamps are UTC with the original text kept where received. Amounts are `Decimal`. Tables belong to the owning service's schema; no cross-schema references.

## inventory-service

### data_quality_snapshot (new)
One row per variant, period and build.

| Field | Notes |
|---|---|
| id, variant_id, period_start, period_end | period in days, UTC dates |
| days_in_period, days_with_data, coverage_ratio | coverage = days_with_data / days_in_period |
| gap_days | list of date ranges (compact) |
| rejected_count, quarantined_count, ambiguous_count | counts with `reason_counts` (reason code -> count) |
| excluded_count | by movement type (`excluded_by_type`) |
| anomaly_count, censored_days | |
| origin | `erp` or `local_export`; never mixed in one row |
| config_version_id, dataset_version_id | versions that built it |
| built_at | UTC |

Unique on (variant_id, period_start, period_end, config_version_id, input_hash). Rebuilding with identical inputs is a no-op.

### anomaly_flags (new)
| Field | Notes |
|---|---|
| id, variant_id, day | |
| rule_id | enumerated rule (e.g. `mad_outlier`, `p95_cap`, `negative_qty`) |
| original_value | exact decimal, never edited |
| decision | `pending` (default), `accepted`, `excluded` |
| decided_by, decided_at | actor id and UTC time; no free text |
| reason_code | optional, from a short enumerated list |

State: pending -> accepted | excluded; accepted <-> excluded allowed, each change audited; an `excluded` decision produces a new demand-series version.

### portfolio_aggregate (new)
Precomputed per variant so the portfolio view needs no cross-service query.

| Field | Notes |
|---|---|
| variant_id, origin | `erp` or `local_export`; never mixed |
| abc, xyz, pattern, intermittent | from `product_segments` |
| coverage_ratio, rejected_share, anomaly_share | from the latest `data_quality_snapshot`; used for the worst-quality list |
| eligibility, confidence | pulled from forecast-service (`GET /forecasts/eligibility`) when the portfolio is rebuilt; `pending` until a run for the variant exists |
| received_run_id, received_at | latest run applied; older runs are ignored |
| category, supplier | filter keys already held by inventory-service |

Counts by any bucket always sum to the number of active products because `pending` is a bucket.


### product_segments (existing, extended additively)
Add `config_version_id` and `method` (method name mapped to the class) so the class is reproducible and shown with its method (FR-007, FR-008).

## forecast-service

### forecast_explanations (new)
One row per (run_id, variant_id).

| Field | Notes |
|---|---|
| run_id, variant_id | FK to `forecast_runs`, `forecast_values` key |
| model_version, dataset_version_id, config_version_id | copied from the run for direct lookup (FR-009) |
| history_start, history_end | window used |
| abc, xyz, pattern, intermittent | class snapshot at run time |
| method, method_reason_code | why this method for this class |
| censored_days, anomaly_days_excluded, provenance_mix | mix = counts by observed / estimated / manual |
| low, expected, high | from stored quantiles; NULL when not eligible |
| confidence | `alta`, `media`, `baja`, or NULL when not eligible |
| confidence_reason_codes | list of reason codes |
| eligibility | `eligible`, `manual_review_only`, `not_eligible` |
| eligibility_reason_codes | list |

Immutable once the run is completed. A new input version yields a new run and new rows (FR-011).

### product_backtest (new)
| Field | Notes |
|---|---|
| id, backtest_run_id, variant_id | |
| periods | windows evaluated (count and bounds) |
| wape, bias | method error on realised demand, excluding censored windows |
| baseline_wape, baseline_bias | simple baseline |
| beats_baseline | boolean |
| model_version, dataset_version_id, config_version_id | |
| created_at | UTC |

Unique on (backtest_run_id, variant_id). Never updates stored forecasts or proposals (FR-017).

### forecast_runs / forecast_values (existing)
Unchanged; `forecast_runs` already holds `model_versions`, `input_hash`, `config`, `dataset_version_id`, `parameter_version_ids`.

## Retention

`data_quality_snapshot`, `anomaly_flags`, `forecast_explanations` and `product_backtest` rows are kept for 5 years in full detail and are never updated in place or deleted earlier (spec FR-025). A retention job may remove rows older than 5 years and writes an audit event with the counts removed.

## Enumerations

- Provenance: `observed` (ERP movements only), `estimated`, `manual`.
- Eligibility: `eligible`, `manual_review_only`, `not_eligible`.
- Confidence: `alta`, `media`, `baja`.
- Anomaly decision: `pending`, `accepted`, `excluded`.

## Validation rules

- Provenance `observed` is rejected for any row whose origin is seed, local export or imputed (FR-014).
- `low <= expected <= high`; all three NULL when `eligibility = not_eligible`.
- `manual_review_only` rows are never auto-suggested.
- `coverage_ratio` in [0, 1]; counts non-negative.
- Free-text fields are not accepted anywhere in these tables.

## Audit events (existing mechanism, new types)
`quality.anomaly_decided`, `quality.classes_recomputed`, `forecast.backtest_started`, `forecast.backtest_completed`: actor, time, versions; no free text.
