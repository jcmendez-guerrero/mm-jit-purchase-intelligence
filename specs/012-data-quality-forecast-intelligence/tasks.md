---

description: "Task list for Data Quality and Forecast Intelligence (Agent 02)"
---

# Tasks: Data Quality and Forecast Intelligence (Agent 02)

**Input**: Design documents from `specs/012-data-quality-forecast-intelligence/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/quality-intelligence.md](contracts/quality-intelligence.md), [quickstart.md](quickstart.md)

**Tests**: Included. The constitution (principle V) and the Jira brief require unit, API contract, PostgreSQL integration, security-abuse and Playwright tests; within each story tests come before implementation. Synthetic fixtures from `packages/testing` only.

**Organization**: Grouped by user story so each can be built and tested alone. Mark tasks `[X]` when done.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallel (different files, no unfinished dependency)
- **[Story]**: US1 to US5, as in spec.md
- Migration numbers are the next free revision in each service at implementation time (inventory-service: main is at 0007 and feature 011's branch adds 0008, so expect 0008 or 0009 depending on merge order, and recheck when you start; forecast-service: 0006).

## Path Conventions

Multi-service layout from plan.md: `services/inventory-service`, `services/forecast-service`, `services/api-bff`, `apps/web`, `packages/contracts`, `packages/testing`.

---

## Phase 1: Setup

- [X] T001 Run the existing suites for inventory-service and forecast-service and record the baseline pass/fail in `specs/012-data-quality-forecast-intelligence/research.md` (R1, resolves the "unverified" statuses); also confirm the Python version and frameworks in each service's project file against plan.md Technical Context
- [X] T002 Read how `services/forecast-service/src/runs/runner.py` and `src/policies/base.py` use the `censored` arrays when fitting; record in research.md R4 whether censored blocks are excluded or read as zero, with file and line evidence (FR-001, FR-005)
- [X] T003 [P] Add synthetic fixtures to `packages/testing`: smooth, intermittent, stockout-period, outlier-day, rejected-movements, seed-data and too-little-history products (done in `packages/testing/src/quality_fixtures/`, 7 tests pass); viewer and buyer users are not added here because each service's tests already provide `auth("buyer")` and `auth("viewer")` helpers
- [ ] T004 [P] Register the feature in `docs/architecture/integration/contract-matrix.json` through Agent 00 (additive entries only) and confirm `python -m gates run` from `scripts/` passes before any schema change. STATUS: request drafted in `contracts/matrix-request.md` with an open event-design decision for Agent 00; baseline gates recorded there (contracts, isolation, cost pass). Mark done when Agent 00 answers.

---

## Phase 2: Foundational (blocks all stories)

- [ ] T005 [P] Write JSON Schemas first in `packages/contracts`: quality summary, anomaly flag and decision, forecast explanation, product backtest result, portfolio response, the optional per-variant eligibility and confidence addition to the `forecast.completed` payload, and the portfolio aggregate; regenerate Python and TypeScript types (principle IV)
- [X] T006 [P] Add the new error keys (`quality_product_not_found`, `quality_anomaly_not_found`, `quality_decision_invalid`, `forecast_explanation_not_available`, `forecast_backtest_conflict`, `quality_job_failed`) to `packages/contracts/errors/error_codes.json`, `specs/002-mmi-operational-console/contracts/error-keys.md` and `apps/web/src/i18n/es-ES.json`
- [X] T007 Inventory-service migration `services/inventory-service/migrations/versions/0008_quality_intelligence.py` (written on top of main's 0007; renumber to 0009 if feature 011's 0008 merges first) and tables in `services/inventory-service/src/db/tables.py`: `data_quality_snapshot`, `anomaly_flags`, `forecast_inbox` (used by T060b), the portfolio aggregate table (used by T061, defined here so the migration is not edited later), and additive `config_version_id` and `method` columns on `product_segments`
- [X] T008 Forecast-service migration `services/forecast-service/migrations/versions/0006_explanations_backtest.py` and tables in `services/forecast-service/src/db/tables.py`: `forecast_explanations`, `product_backtest`
- [X] T009 [P] Migration tests for both new revisions (upgrade, downgrade, no change to existing columns) in `services/inventory-service/tests/test_migration_quality.py` and `services/forecast-service/tests/test_migration_explanations.py`
- [X] T010 First check whether the business policy console already on main (`services/procurement-service/src/policies`, feature 002; feature 011 is not on main) stores ABC/XYZ cut-offs, minimum history and confidence/eligibility thresholds, and record the answer in research.md R8. If it does, read them through its API; if not, keep the current `ClassificationConfig` defaults and request the policy fields through Agent 00 (T004). Also confirm that the BFF's fresh-MFA mechanism used by existing admin actions is on main, and record it in research.md R8 (T024 and T026 rely on it).
- [X] T010a [P] Implement the threshold source chosen in T010 with the current dataclass values as fallback; return the configuration version id, in `services/inventory-service/src/classification/segments.py` (uses `ClassificationConfig`) and a new `services/inventory-service/src/classification/policy_source.py`
- [X] T011 [P] Add audit event types `quality.anomaly_decided`, `quality.classes_recomputed`, `forecast.backtest_started`, `forecast.backtest_completed` (actor, time, versions, no free text) in `services/inventory-service/src/audit.py` and `services/forecast-service/src/audit.py`
- [X] T012 [P] Add the shared Spanish strings and the provenance label type (`observed`, `estimated`, `manual`) in `apps/web/src/i18n/es-ES.json` and `services/forecast-service/src/locale/es-ES.json`
- [X] T013 Provenance guard: one function that assigns the label to every demand row exported from inventory-service to the forecast; `observed` only for ERP-collected movements, never for seed, local-export or imputed values, in `services/inventory-service/src/demand/provider.py`
- [X] T014 [P] Security-abuse test for the provenance guard across all sources (SC-002, FR-014) in `services/inventory-service/tests/test_provenance_labels.py`
- [ ] T014a [P] Conventions test (FR-023): timestamps stored in UTC with the original text kept, amounts as decimal strings never floats, user-facing identifiers are SKUs and no Siweb ids appear in responses, in `services/inventory-service/tests/test_conventions.py` and `services/forecast-service/tests/test_conventions.py`
- [ ] T014b [P] Origin-mixing test: a catalogue with ERP products and feature 004 local-export products (surrogate ids from 9,000,000) never combines the two origins in snapshots, classes, backtests or portfolio counts, in `services/inventory-service/tests/test_origin_not_mixed.py`

**Checkpoint**: schemas, tables, thresholds, audit and provenance in place; stories can start.

---

## Phase 3: User Story 1 - Know how trustworthy a product's history is (Priority: P1) MVP

**Goal**: per-product quality summary with coverage, gap days, rejected/quarantined reasons, anomalies, stockout days and excluded movements.

**Independent Test**: quickstart scenarios 1 and 2 on the synthetic fixtures.

### Tests for US1 (write first, expect failure)

- [ ] T015 [P] [US1] Unit tests for coverage and gap-day calculation in `services/inventory-service/tests/test_quality_coverage.py`
- [ ] T016 [P] [US1] Unit tests for the anomaly rules (median/MAD outlier, p95 cap, negative quantity) using the default parameters fixed in research.md R2: deterministic, original value kept in `services/inventory-service/tests/test_anomaly_rules.py`
- [ ] T017 [P] [US1] API contract tests for `GET /quality/products/{sku}`, `GET /quality/products/{sku}/anomalies` and `PUT .../anomalies/{day}` (viewer 403, idempotent, enumerated reason only, second factor required for `excluded` and its reversal, not for `accepted`) in `services/inventory-service/tests/test_quality_api.py`
- [ ] T018 [P] [US1] PostgreSQL integration test: rejected movements never reach demand and every one appears in the review list with a Spanish reason (SC-004) in `services/inventory-service/tests/test_rejected_not_demand.py`
- [ ] T019 [P] [US1] Integration test: an `excluded` decision creates a new series version and leaves ERP-derived rows untouched in `services/inventory-service/tests/test_anomaly_overlay.py`
- [ ] T019a [P] [US1] Failure test for the recompute job: a failed or interrupted run leaves no partial snapshots, shows a Spanish failure reason, and a retry is idempotent (FR-022) in `services/inventory-service/tests/test_recompute_failure.py`

### Implementation for US1

- [ ] T020 [US1] Coverage and gap-day builder in `services/inventory-service/src/quality/coverage.py`
- [ ] T021 [US1] Anomaly rule engine in `services/inventory-service/src/quality/anomalies.py` (flags stored in `anomaly_flags`, never editing movements)
- [ ] T022 [US1] Snapshot builder combining coverage, rejected/quarantined/ambiguous counts with reasons, excluded movement counts by type (the exclusion rules come from the existing `demand_exclusions` table), anomaly count and censored days; idempotent per input hash, in `services/inventory-service/src/quality/snapshot.py` (extends `metrics.py` and `review.py`)
- [ ] T023 [US1] Exclusion overlay applied when the demand series is exported (excluded days dropped, version bumped) in `services/inventory-service/src/demand/provider.py`
- [ ] T024 [US1] Endpoints and decision handler (buyer/admin only; the BFF enforces the fresh second-factor check for `excluded` and its reversal and inventory-service trusts that claim; audit event) in `services/inventory-service/src/api/quality.py`, registered in `src/api/__init__.py`
- [ ] T025 [US1] Background job and endpoint `POST /quality/recompute` with job status in `services/inventory-service/src/worker.py` and `src/api/quality.py`
- [ ] T026 [P] [US1] BFF routes (orchestration and role checks only) in `services/api-bff/src/routes/quality.py` and tests in `services/api-bff/tests/test_quality_routes.py`, including that `excluded` without a recent second factor is refused with the shared error while `accepted` is not
- [ ] T027 [US1] Quality summary and anomaly decision panel in Spanish in `apps/web/src/features/quality/QualitySummary.tsx` and `QualityScreen.tsx`, with its strings in `es-ES.json`
- [ ] T028 [US1] Playwright E2E for quickstart scenarios 1 and 2 in `apps/web/tests/e2e/quality-summary.spec.ts`

**Checkpoint**: US1 works alone and is demonstrable.

---

## Phase 4: User Story 2 - See which model a forecast used and why (Priority: P1)

**Goal**: every forecast explains its class, method, confidence, eligibility and the model, dataset and configuration versions.

**Independent Test**: quickstart scenarios 3 and 4.

### Tests for US2

- [ ] T029 [P] [US2] Unit tests: class-to-method mapping and its reason codes, eligibility values (`eligible`, `manual_review_only`, `not_eligible`) in `services/forecast-service/tests/test_explanation_method.py`
- [ ] T030 [P] [US2] Reproducibility test: unchanged inputs and versions give identical results and explanations; a changed input version gives a new run and keeps the old one (FR-011, SC-005) in `services/forecast-service/tests/test_explanation_reproducibility.py`
- [ ] T031 [P] [US2] API contract tests for `GET /forecast/products/{sku}/explanation` (versions present, SKU only, no Siweb ids, no free text) in `services/forecast-service/tests/test_explanation_api.py`
- [ ] T032 [P] [US2] Test that a not-eligible or low-confidence product has no stored forecast figure and its proposal line shows the conservative min/max labelled "not a forecast" with the reason, in `services/forecast-service/tests/test_not_a_forecast_line.py`
- [ ] T032a [P] [US2] Consistency test (FR-008): the class-to-method mapping and its reason are identical in the explanation, the proposal line and the proposal export for the same product, in `services/forecast-service/tests/test_method_mapping_consistent.py`

### Implementation for US2

- [ ] T033 [US2] Persist class (ABC, XYZ, pattern, intermittent), thresholds' configuration version and mapped method in `services/inventory-service/src/classification/run.py` (additive columns from T007)
- [ ] T034 [US2] Explanation builder: history window, class snapshot, method and reason, censored and anomaly-excluded day counts, provenance mix, eligibility with reasons, written at the end of each run in `services/forecast-service/src/runs/explanation.py`, called from `runs/runner.py`
- [X] T035 [US2] (T002 verified: no change needed, see research.md R4) If T002 found censored blocks read as zero, make the forecast fit leave them out (no estimation) in `services/forecast-service/src/policies/base.py` and `runs/runner.py`; otherwise record "verified, no change" in research.md
- [ ] T036 [US2] Endpoint `GET /forecast/products/{sku}/explanation` in `services/forecast-service/src/api.py`; SKU resolved through the synced catalogue
- [ ] T037 [US2] Proposal line shows the conservative min/max labelled "not a forecast" with the reason for not-eligible, manual-review-only and low-confidence products, in `services/forecast-service/src/runs/eligibility.py` and `apps/web/src/features/proposals/ProposalLineExplanation.tsx`
- [ ] T038 [P] [US2] BFF route and test for the explanation in `services/api-bff/src/routes/quality.py` and `services/api-bff/tests/test_explanation_routes.py`
- [ ] T039 [US2] Explanation panel in Spanish, reachable from the proposal line in under a minute (SC-003), in `apps/web/src/features/quality/ExplanationPanel.tsx`
- [ ] T040 [US2] Playwright E2E for quickstart scenarios 3 and 4 in `apps/web/tests/e2e/forecast-explanation.spec.ts`, including that from a proposal line the explanation is reachable within three clicks and under one minute (SC-003)

**Checkpoint**: US1 and US2 both work alone.

---

## Phase 5: User Story 3 - See uncertainty, not just a point forecast (Priority: P1)

**Goal**: range and confidence label on every forecast; provenance visible; nothing but ERP movements labelled observed.

**Independent Test**: quickstart scenario 5.

### Tests for US3

- [ ] T041 [P] [US3] Unit tests for the confidence rule (history sufficiency, data quality shares, backtest result when present) and thresholds from policy in `services/forecast-service/tests/test_confidence_rule.py`
- [ ] T042 [P] [US3] Contract test that every eligible forecast, in screens and exports, carries low, expected, high with `low <= expected <= high`, a confidence label and the three versions, in the screens and in the existing proposal export (SC-001) in `services/forecast-service/tests/test_range_confidence_contract.py`
- [ ] T043 [P] [US3] Test that estimated seed values appear as `estimated` and no value from seed, local-export or imputed sources is `observed` in any response or export in `services/forecast-service/tests/test_provenance_in_forecast.py`

### Implementation for US3

- [ ] T044 [US3] Confidence rule and range (from stored quantiles) in `services/forecast-service/src/runs/confidence.py`, written into `forecast_explanations`; also publish eligibility and confidence per variant on the existing `forecast.completed` event (optional field, additive) so inventory-service can build the portfolio without cross-service queries
- [ ] T045 [US3] Low-confidence handling: warning flag, no auto-suggestion, consistent with T037, in `services/forecast-service/src/runs/eligibility.py`
- [ ] T046 [US3] Provenance label on every demand value in the history table and in the existing proposal export, which also carries range, confidence and versions (formula-safe; no new export is added) in `services/forecast-service/src/runs/seeds.py` and the web history table in `apps/web/src/features/quality/`
- [ ] T047 [US3] Range and confidence display with warning in Spanish in `apps/web/src/features/quality/ExplanationPanel.tsx` and the proposal line
- [ ] T048 [US3] Playwright E2E for quickstart scenario 5 in `apps/web/tests/e2e/forecast-uncertainty.spec.ts`

**Checkpoint**: all three P1 stories done; MVP complete.

---

## Phase 6: User Story 4 - Judge forecast accuracy with a backtest (Priority: P2)

**Goal**: per-product error, bias and baseline comparison, flagged when the method does not beat the baseline.

**Independent Test**: quickstart scenario 6.

### Tests for US4

- [ ] T049 [P] [US4] Unit tests on synthetic history with known error and bias, including the baseline-wins case, censored windows excluded, in `services/forecast-service/tests/test_product_backtest.py`
- [ ] T050 [P] [US4] Test that a backtest leaves stored forecasts, proposals, stock and ERP data unchanged (hash before and after, SC-008) in `services/forecast-service/tests/test_backtest_no_side_effects.py`
- [ ] T051 [P] [US4] API tests for `POST /forecast/backtests` and `GET /forecast/products/{sku}/backtest`: viewer 403, identical inputs reuse the result, a second full-catalogue request while one runs returns `forecast_backtest_conflict` (409) naming the running job, no partial results after failure in `services/forecast-service/tests/test_backtest_api.py`
- [ ] T052 [P] [US4] Scale test: 5,000 synthetic products complete in the background within 15 minutes with visible status (SC-006) in `services/forecast-service/tests/test_backtest_scale.py`

### Implementation for US4

- [ ] T053 [US4] Per-product backtest (rolling origin, WAPE and bias, baseline from `policies/estimators.py`) in `services/forecast-service/src/backtest/product.py`, extending `backtest/runner.py`
- [ ] T054 [US4] Persist immutable results in `product_backtest`; flag `beats_baseline` false and feed it into confidence and eligibility (T044) in `services/forecast-service/src/backtest/product.py`
- [ ] T055 [US4] Endpoints, one-full-catalogue-at-a-time lock, idempotency per input hash, job status and audit events in `services/forecast-service/src/api.py` and `src/worker.py`
- [ ] T056 [P] [US4] BFF routes in `services/api-bff/src/routes/quality.py` with tests in `services/api-bff/tests/test_backtest_routes.py`
- [ ] T057 [US4] Backtest view in Spanish (start, status, per-product table, flag) in `apps/web/src/features/quality/BacktestView.tsx`
- [ ] T058 [US4] Playwright E2E for quickstart scenario 6 in `apps/web/tests/e2e/forecast-backtest.spec.ts`

---

## Phase 7: User Story 5 - Portfolio view (Priority: P2)

**Goal**: distribution by class, eligibility and confidence, worst-quality list, filters by category and supplier, drill-down.

**Independent Test**: quickstart scenario 7.

### Tests for US5

- [ ] T059 [P] [US5] Reconciliation test: counts by class and eligibility sum to the active product count and each opens the matching list, including a product whose forecast run has not arrived yet, which counts as "pending" and is not missing from the sums (SC-007) in `services/inventory-service/tests/test_portfolio_reconcile.py`
- [ ] T060 [P] [US5] Filter-matrix test for category and supplier, and a load test for 5,000 products under 3 seconds (SC-006) in `services/inventory-service/tests/test_portfolio_filters.py`
- [ ] T060a [P] [US5] Consumer test: a duplicate `forecast.completed` event changes nothing, an out-of-order older event never overwrites newer eligibility and confidence, and a malformed payload is rejected and recorded, in `services/inventory-service/tests/test_forecast_completed_consumer.py`

### Implementation for US5

- [ ] T060b [US5] Idempotent consumer of `forecast.completed` in inventory-service (inbox table and handler reusing the outbox and inbox helpers in `mmi_common`; validates the schema; stores eligibility and confidence per variant with the run id and ignores older runs) in `services/inventory-service/src/` (new `consumers/forecast_completed.py`) and its inbox table in the T007 migration
- [ ] T061 [US5] Build the precomputed portfolio aggregates (table defined in T007) in `services/inventory-service/src/dashboard/`, filling eligibility and confidence from the values received on `forecast.completed` (T044); products without a received value are counted as "pending"; also build the worst-quality list (lowest coverage, highest rejected and anomaly shares)
- [ ] T062 [US5] Endpoints `GET /quality/portfolio` and `/quality/portfolio/products` in `services/inventory-service/src/api/quality.py`; counts, category and supplier filters and paged drill-down all come from this one service, so the sums match the active product count by construction
- [ ] T063 [P] [US5] BFF composition in `services/api-bff/src/routes/quality.py` with tests in `services/api-bff/tests/test_portfolio_routes.py`
- [ ] T064 [US5] Portfolio screen in Spanish with filters and drill-down in `apps/web/src/features/quality/PortfolioView.tsx`
- [ ] T065 [US5] Playwright E2E for quickstart scenario 7 in `apps/web/tests/e2e/quality-portfolio.spec.ts`

---

## Phase 8: Polish and cross-cutting

- [ ] T066 [P] Retention (FR-025): retention job that removes the four new tables' rows only after 5 years, audited with counts, plus a test that nothing is deleted or overwritten earlier, in `services/inventory-service/src/worker.py`, `services/forecast-service/src/worker.py` and `tests/test_retention_quality.py` in each service
- [ ] T067 [P] Observability: job duration, failure and queue signals for snapshot, class and backtest jobs without secrets or personal data (principle V)
- [ ] T068 [P] Security-abuse tests: SKU injection, oversized and malformed bodies, formula-safe exports, no free-text or tax-id fields accepted, in each service's `tests/`
- [ ] T069 [P] Cost check: confirm no always-on resource added and scale-to-zero and job caps respected; note storage growth estimate under FR-024 in `plan.md`
- [ ] T070 Verify that `plan.md` and `research.md` still match the clarified decisions and the choices made during implementation (they were updated before implementation; record any drift)
- [ ] T071 Run `python -m gates run` from `scripts/`, the full test suites and the Playwright run; capture Spanish-UI screenshots for the PR
- [ ] T072 Walk through every scenario in [quickstart.md](quickstart.md) and record the result
- [ ] T073 Open one PR following `.github/pull_request_template.md` (data, security, cost, contract impact) linking MMI-4 and the Confluence page

---

## Dependencies and order

- Setup (T001-T004) first; T001 and T002 inform US2.
- Foundational (T005-T014) blocks every story.
- US1, US2 and US3 are P1. US1 is independent. US2 needs T033 and the T007/T008 tables. US3 needs the explanation record from US2 (T034), so build US2 before US3.
- US4 can start after Foundational; its flag feeds US3's confidence (T054 to T044), so wire that link when both exist.
- US5 needs US1 (snapshots), US2 (class and eligibility) and US3 (T044 publishes eligibility and confidence that T060b consumes).
- Polish last; T066 can start once the tables exist.
- T026, T038, T056 and T063 are all marked [P] but edit the same file (`services/api-bff/src/routes/quality.py`); they are parallel only because they sit in different phases. Do not run two of them at once.
- Task IDs with a letter suffix (T010a, T014a, T014b, T019a, T032a) were added after analysis to avoid renumbering; they run right after the task they follow.

## Parallel examples

- After Foundational: US1 tests T015-T019 together; US4 tests T049-T052 together.
- Within a story, backend and BFF tests marked [P] run in parallel; UI tasks wait for their endpoints.
- Different services (inventory-service, forecast-service, api-bff, apps/web) can be worked in parallel once the schemas (T005) are fixed.

## Implementation strategy

1. MVP: Setup, Foundational, US1, US2, US3 (all P1). Stop and validate quickstart scenarios 1 to 5.
2. Add US4, validate scenario 6.
3. Add US5, validate scenario 7, then Polish.
4. Nothing reaches production, main or the ERP from this feature; humans keep deciding purchases.

---

## Phase 9: Convergence

- [ ] T074 After Agent 00 answers the event-design decision in `contracts/matrix-request.md`, align `plan.md` (portfolio data flow), `contracts/quality-intelligence.md` (Events), `data-model.md` and the event names in T005, T044, T060a and T060b with the chosen option, per plan: portfolio data flow (partial)
- [ ] T075 Write T014a (conventions: UTC with original text, decimals, SKU-only) and T014b (no mixing of local-export and ERP origins) only after T022 to T024 exist, and move them to run right after those tasks, per FR-023 and the spec edge case on local exports (partial)
- [ ] T076 Install the web dependencies in `apps/web` and run `npm test` and `npm run lint` so the ten new `quality.*` es-ES strings added in T012 are checked by the existing web tests, per FR-019 (partial)
- [ ] T077 Before opening the PR, check whether feature 011's inventory migration `0008` has merged; if it has, renumber `services/inventory-service/migrations/versions/0008_quality_intelligence.py` to 0009, point `down_revision` at 0008, update `tests/test_migration_quality.py` and re-run the PostgreSQL migration test (`RUN_PG_MIGRATIONS=1 pytest infra/tests/test_migrations_postgres.py`), per T007 (partial)
- [ ] T078 Document the additive `provenance` field of `GET /export/series` in `contracts/quality-intelligence.md` and ask Agent 00 whether this service-to-service endpoint needs a contract-matrix entry, per FR-014 (partial)
- [ ] T079 Install Playwright and `ortools` in the verification environment so the `e2e` and `security` gates can run before the final `python -m gates run`, per T071 (partial)
