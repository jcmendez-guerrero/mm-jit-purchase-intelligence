# Research: Data Quality and Forecast Intelligence

## R1. Audit of existing capability (FR-001)

Status per spec capability on this branch. "Evidence" is the file; line-level evidence is recorded when the task touches it. Statuses marked *unverified* must be confirmed by running the existing tests before reuse.

| Capability | Status | Evidence |
|---|---|---|
| ABC / XYZ / Syntetos-Boylan pattern, eligibility reason codes | Complete (thresholds hard-coded defaults in a dataclass; not yet read from feature 011 policy) | `services/inventory-service/src/classification/segments.py`, `run.py`, table `product_segments`, `segment_history` |
| Stockout censoring (7-day blocks excluded) | Complete in classification; *unverified* that forecast training treats censored days as lost demand, not zero | `classification/segments.py`, `demand/losses.py`, tables `censoring_rules`, `stock_history`; `forecast-service/src/policies/base.py`, `runs/runner.py` (censored arrays) |
| Quality metrics and review/quarantine list | Partial: aggregate metrics and review decisions exist; no per-product coverage/gap days, no anomaly flags | `inventory-service/src/quality/metrics.py`, `review.py`, tables `data_quality_metrics`, `review_decisions`; web `apps/web/src/features/quality` |
| Excluded movement types | Partial: `demand_exclusions` table exists; counts not surfaced per product | `inventory-service/src/db/tables.py` (`demand_exclusions`), `demand/common.py` |
| Versioned forecast runs (model versions, input hash, config, dataset version, parameter versions) | Complete | `forecast-service/src/runs/runner.py` (`model_versions`, `input_hash`), table `forecast_runs`; test `test_reproducibility.py` |
| Eligibility decision and fallback min/max | Complete, no per-product confidence label | `forecast-service/src/runs/eligibility.py`, `policies/fallback.py` |
| Forecast quantiles (range) | Partial: `quantiles` stored per value; not exposed as low/expected/high plus confidence label | table `forecast_values`, `policies/estimators.py` |
| Backtest | Partial: segment-level cost metrics per policy; no per-product error/bias vs. baseline | `forecast-service/src/backtest/runner.py`, table `backtest_metrics`; tests `test_backtest.py`, `test_dryrun_backtest.py` |
| Realised accuracy (WAPE, bias, stockout share) | Complete at segment level (ABC) and overall; not per product | `forecast-service/src/runs/accuracy.py`, table `forecast_accuracy` |
| Provenance labels | Partial: seed rows carry observed/estimated/manual; ERP demand and local-export origin not uniformly labelled on every value shown | `forecast-service/src/runs/seeds.py`, `seed_rows`; feature 004 origin flags |
| Spanish explanation text | Partial: per-line explanation exists in proposals; lacks class/method rationale, censored/anomalous counts | `apps/web/src/features/proposals`, `forecast-service/src/locale/es-ES.json` |
| Portfolio view | Partial: ABC/XYZ aggregate exists (`agg_abc_xyz`); no eligibility/quality distribution or supplier filter | `inventory-service/src/dashboard/`, table `agg_abc_xyz` |
| Audit of decisions | Complete mechanism (hash-chained), new event types needed | `*/src/audit.py`, tables `audit_events` |

### R1 baseline (T001, run 2026-11-15, Python 3.12 venv, synthetic data)

- forecast-service: 215 passed, 3 skipped.
- inventory-service: 263 passed, 1 skipped, 1 failed: `tests/test_dashboard_indicators.py::test_the_route_takes_the_open_orders_and_refuses_a_bad_amount` (expects state `error`, gets `stale`). It looks like a date-dependent dashboard indicator test, unrelated to this feature; cause not investigated. It stays a known baseline failure.
- Python 3.12 is confirmed as the services' required version (`requires-python = ">=3.12,<3.13"`).

## R2. Anomaly rules

- **Decision**: Deterministic, documented rules on the daily (or 7-day block) series per product: robust z-score on the median/MAD of non-zero days over a trailing window, a hard cap relative to the product's 95th percentile, and negative or non-integer quantity checks. Each flag stores the rule id and the original value.
- **Default parameters (proposed, validated by the T016 tests and recorded in the configuration version)**: `mad_outlier` flags a day when `|x - median| > 5 * 1.4826 * MAD` computed on the non-zero days of the trailing 90 days, and only when at least 20 non-zero days exist; `p95_cap` flags a day above 3 times the 95th percentile of non-zero days over the same window; `negative_qty` flags any negative or non-integer quantity. The values are fixed defaults for now; if the business policy console later exposes them, they are read from it (T010).
- **As built (T016, T021)**: the robust deviation is `1.4826 * MAD` floored at one unit, so a flat series (MAD zero) does not flag a one-unit step; the 95th percentile is nearest-rank; the window is the preceding 90 days and stockout-censored days are skipped entirely (never flagged, never part of the window); `negative_qty` is flagged for any negative day regardless of history. Constants live in `services/inventory-service/src/quality/anomalies.py`.
- **Rationale**: Median/MAD is robust to the very outliers being sought; deterministic rules are reproducible (FR-011) and explainable in Spanish.
- **Alternatives**: Model-based detectors (isolation forest) — less explainable, adds dependencies; fixed absolute thresholds — wrong across products of different volume.

## R3. Anomaly decisions do not change source data

- **Decision**: A buyer decision (accepted / excluded) is stored in `anomaly_flags`; "excluded" is applied as an overlay when demand series are exported, never by editing movements. Changing a decision creates a new series version and so a new input hash and a new forecast run.
- **Rationale**: Keeps ERP-derived data untouched (FR-004, FR-015) and reproducible.
- **Alternatives**: Editing `demand_observations` in place — destroys evidence, breaks idempotency.

## R4. Censored days

- **Decision**: Keep the existing rule (day with stock at or below zero is censored; 7-day block excluded when at least 4 censored days). The explanation reports censored day count. The first task verifies the forecast side excludes censored blocks from fitting rather than reading them as zero; if not, fix there.
- **Verified (T002)**: the forecast side already excludes censored days. `prepare_history` in `services/forecast-service/src/policies/base.py:42-46` drops every day whose censored flag is set, and `src/runs/runner.py:122` builds each product's history with it. Censored days are not read as zero, so T035 needs no code change.
- **Rationale**: Reuses working logic; closes the one unverified link.
- **Alternatives**: Imputing lost sales — creates estimated values that must be labelled; deferred, and if added must be `estimated` and stored apart (FR-015).

## R5. Range and confidence label

- **Decision**: Expose low/expected/high from the stored quantiles (e.g. 10th/50th/90th). Confidence label = rule over three inputs: history sufficiency (non-zero blocks, density), data quality (anomaly share, rejected share, censored share) and, when available, the latest per-product backtest result vs. baseline. Labels: alta, media, baja. Thresholds come from policy (feature 011) with defaults recorded in the configuration version.
- **Rationale**: Simple, testable (FR-012), uses signals already computed.
- **Alternatives**: Statistical prediction-interval coverage only — needs long histories most products lack.

## R6. Baseline and per-product backtest

- **Decision**: Rolling-origin backtest per product using the existing runner's windows; baseline is the simple `BASELINE` policy already in `policies/estimators.py`. Metrics: WAPE and bias per product, plus the cost metrics already stored. Results are written to a new `product_backtest` table keyed by backtest run id and variant, immutable.
- **Rationale**: Reuses the runner and baseline; per-product keys enable the flag and the portfolio drill-down.
- **Alternatives**: Recompute on read — too slow for 5,000 products; violates idempotency.

## R7. Where records live (Principle IV)

- **Decision**: Inventory-service owns quality snapshots, anomaly flags and class (data about history). Forecast-service owns explanations, confidence, per-product backtest (data about models). The BFF composes them for screens with no business rules and no cross-schema SQL; the forecast explanation embeds the class snapshot it used.
- **Rationale**: Matches existing ownership of `product_segments` vs `forecast_runs`.
- **Alternatives**: One new analytics service — extra cost, breaks scale-to-zero budget.

## R8. Thresholds source

- **Decision**: Read ABC/XYZ cut-offs, minimum history, confidence and eligibility thresholds from the business policy configuration (the policy console already on main in `services/procurement-service/src/policies`; feature 011 is not on main yet); T010 first checks which of these thresholds that console stores. Keep current dataclass defaults as the fallback and record the configuration version on each result.
- **Verified (T010)**: the policy console in `services/procurement-service/src/policies` and its API store none of the ABC/XYZ cut-offs, minimum history or confidence thresholds (a word search for abc, xyz, adi and confidence found only `collections.abc` imports). So today the source is the `ClassificationConfig` defaults, with a hash-based version id from `services/inventory-service/src/classification/policy_source.py` (T010a); the policy fields are requested through Agent 00 (T004). The BFF's fresh-MFA mechanism is on main (`services/api-bff/src/routes/rbac.py:106`, error `auth_mfa_stale`), so T024 and T026 can rely on it.
- **Rationale**: Consistent with spec assumption; avoids duplicating configuration.
- **Alternatives**: Separate settings screen — duplicates 011.

## R9. Provenance enforcement

- **Decision**: A single provenance value on every demand row exported to the forecast and to screens (`observed` only for ERP-collected movements; seed, local-export and imputed values get `estimated` or `manual`). Automated check across all sources asserts zero mislabelled rows (SC-002).
- **Rationale**: Closes the audit gap; testable.
- **Alternatives**: Labelling at display only — can drift from stored data.

## R10. Contract coordination

- **Decision**: All schema changes are additive (new optional fields, new endpoints) and registered in `docs/architecture/integration/contract-matrix.json` through Agent 00; `python -m gates run` before the PR.
- **Rationale**: Project rule; shared interfaces are frozen and versioned.
- **Alternatives**: None permitted by project rules.

## Open items

None blocking. Unverified statuses in R1 are resolved by the first tasks (run existing tests, read the censored handling in the forecast fit) rather than by user input.
