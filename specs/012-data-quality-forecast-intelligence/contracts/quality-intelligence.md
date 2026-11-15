# Contract: Quality and Forecast Intelligence (additive)

Delta over existing BFF/service contracts. JSON Schemas live in `packages/contracts` (written first); this file lists the surface. All paths are behind the BFF with the existing session, CSRF and role checks. Products are addressed by SKU in the UI and API surface; `variant_id` is resolved server-side from the synced catalogue. All user-facing text and error keys are Spanish (es-ES) through the shared catalogue; money and quantities are decimal strings.

## Read endpoints (viewer, buyer, admin)

| Method and path | Purpose | Response (summary) |
|---|---|---|
| `GET /quality/products/{sku}` | Per-product quality summary (FR-002..006) | coverage, gap_days, rejected/quarantined/ambiguous counts with reasons and review link, excluded counts, anomalies, censored_days, versions, built_at |
| `GET /quality/products/{sku}/anomalies` | Flags with decisions | day, rule_id, original_value, decision, decided_by, decided_at |
| `GET /forecast/products/{sku}/explanation` | Explanation for the latest (or given `run_id`) forecast (FR-009..013) | versions (model, dataset, configuration), window, class (abc, xyz, pattern, intermittent), method and reason, censored and anomalous day counts, provenance mix, low/expected/high, confidence and reasons, eligibility and reasons |
| `GET /forecast/products/{sku}/backtest` | Per-product backtest (FR-016, FR-018) | periods, wape, bias, baseline_wape, baseline_bias, beats_baseline, versions |
| `GET /quality/portfolio` | Portfolio counts (FR-019) | counts by abc/xyz/pattern/eligibility/confidence; worst-quality list; filters `category`, `supplier`; each count carries a `drilldown` query |
| `GET /quality/portfolio/products` | Drill-down list | paged SKU list for a chosen bucket and filters |

Every provenance-bearing value in responses carries `provenance` in {`observed`,`estimated`,`manual`}. `observed` is returned only for ERP-collected movements.

## Write endpoints (buyer, admin)

| Method and path | Purpose | Rules |
|---|---|---|
| `PUT /quality/products/{sku}/anomalies/{day}` | Set decision `accepted` or `excluded` | Idempotent; body `{decision, reason_code?}` (enumerated, no free text); audited `quality.anomaly_decided`; `excluded` (and reversing it) requires a recent second-factor check, `accepted` does not; triggers a new series version |
| `POST /quality/recompute` | Rebuild snapshots and classes | Returns a job id; idempotent per input hash; audited `quality.classes_recomputed` |
| `POST /forecast/backtests` | Start a backtest (product, category or catalogue) | Returns a job id; no stored forecast, proposal, stock or ERP data changes; audited `forecast.backtest_started` / `forecast.backtest_completed`; identical inputs return the existing result; a second full-catalogue request while one runs is refused with `forecast_backtest_conflict` (409) naming the running job |
| `GET /jobs/{id}` | Status of the above | Existing job status shape; failure reason in Spanish and retry offered; no partial results |

Viewers receive `403` with the shared Spanish error key on write endpoints. Sensitive configuration (thresholds) is changed only through the business policy configuration, with its fresh-MFA rule.

## Errors (shared catalogue, new keys to register)

`quality_product_not_found`, `quality_anomaly_not_found`, `quality_decision_invalid`, `forecast_explanation_not_available`, `forecast_backtest_conflict`, `quality_job_failed`. Each has an es-ES message; registered in `packages/contracts/errors/error_codes.json` and the console error-key list.

## Events (additive, optional)

- `quality.snapshot.built` (inventory-service): variant count, config and dataset versions; consumers must tolerate absence.
- No event is needed for the portfolio. Inventory-service pulls eligibility and confidence per SKU from forecast-service's read-only `GET /forecasts/eligibility` (latest completed run) when it recomputes; a product with no value there, or no forecast run at all, is counted as `pending`. `forecast.completed` is left exactly as it is.
- Service-to-service reads added by this feature (not gateway endpoints): `GET /forecasts/eligibility`, and the series export's additive `provenance`, `anomaly_excluded_days` and `segment.config_version_id` fields.

## Compatibility and governance

- All changes are additive; no field removed or retyped.
- Registered in `docs/architecture/integration/contract-matrix.json` through Agent 00 before implementation; `python -m gates run` from `scripts/` passes before the PR.
- Idempotency: repeated POST with the same inputs returns the same job/result.
- No endpoint accepts or returns free-text notes, tax identifiers or Siweb internal ids.
