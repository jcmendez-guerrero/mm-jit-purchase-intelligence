---

description: "Task list for Dashboard & Analytics Completion (Agent 01B, MMI-11)"
---

# Tasks: Dashboard & Analytics Completion

**Input**: Design documents from `/specs/014-dashboard-analytics-completion/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/dashboard-completion.md](contracts/dashboard-completion.md), [quickstart.md](quickstart.md). The design of record for everything not changed here is `specs/006-executive-dashboard-analytics/`.

**Tests**: Included. The repository rule is tests before implementation within a story. Synthetic fixtures from `packages/testing` only.

**Format**: `- [ ] T### [P?] [US?] Description with file path`. `[P]` = different files, no dependency on an incomplete task. Mark `[X]` when done; when a task finishes work that a 006 task covers, also tick that 006 task in `specs/006-executive-dashboard-analytics/tasks.md` with evidence.

**Hard rules for every task**: read-only toward the ERP; Decimal money; es-ES strings from the catalogue only; SKU shown, never internal ids; no business logic in the BFF; shared contracts and gates only through Agent 00 (MMI-2); additive edits only to `apps/web/src/api/client.ts` and `apps/web/src/i18n/es-ES.json`.

## Phase 1: Setup

- [X] T001 Create `specs/014-dashboard-analytics-completion/closure-report.md` with the two tables from data-model.md (ClosureReport rows; evidence results), empty, and link it from `plan.md`
- [X] T002 [P] Confirm tool commands still work and record them at the top of `closure-report.md`: `uv run pytest services/inventory-service/tests`, `uv run ruff check .`, and from `apps/web` `npm run typecheck && npm test && npm run e2e`

---

## Phase 2: Foundational (blocks all stories)

- [X] T003 Through Agent 00 (read `docs/architecture/integration/README.md`), add additive JSON Schemas in `packages/contracts/dto/` for chart series, export header, freshness status, SKU detail and the new drill-down kinds; leave the `dashboard_indicators` v1 and v2 schemas untouched; regenerate types in `packages/contracts/python/mmi_models/` and run `python -m gates run` from `scripts/`
- [X] T004 [P] Add contract tests that validate sample payloads of each new schema and assert v1 and v2 indicator schemas are byte-unchanged, in `packages/contracts/tests/test_dashboard_completion_schemas.py`
- [X] T005 [P] Create `apps/web/src/api/dashboard.ts` with typed calls for options, charts, drilldown, freshness, export and sku, reusing the shared request helper; do not edit `client.ts` beyond exporting the helper (006 T014)
- [X] T006 [P] Create `scripts/live-stack/` seed loader and run guide that start `infra/compose.yaml` with `packages/testing/fixtures/dashboard_reference/`, no Azure credentials, and document it in `scripts/live-stack/README.md` (006 T074)
- [X] T007 [P] Add the `ignored_filters` field (name, reason) to the filter validation in `services/inventory-service/src/dashboard/filters.py` and return it from every dashboard route, with a test in `services/inventory-service/tests/test_dashboard_filters.py` (already done, see closure report findings)

**Checkpoint**: contracts, API module and seed loader exist.

---

## Phase 3: User Story 1 - Know exactly what is done and what is left (Priority: P1)

**Goal**: honest, evidence-backed starting inventory and a closing report.

**Independent Test**: sample 10 tasks; each classification matches the code; no 006 requirement is missing from the report.

**Must finish before Phases 4 to 8 start building** (so nothing finished is rebuilt).

- [X] T008 [US1] For each of the 48 unchecked tasks in `specs/006-executive-dashboard-analytics/tasks.md` (T014, T017-T019, T034, T038-T079 unchecked ones, T097, T098), read the named files and tests and add a row to `closure-report.md`: id, start status (completed, remaining, unverified), file:line evidence
- [X] T009 [US1] For each 006 functional requirement (FR-001 to FR-026) add a row to `closure-report.md` stating which tasks cover it and its start status
- [X] T010 [US1] Tick in the 006 `tasks.md` every task classified completed (with a short evidence note) and update `specs/006-executive-dashboard-analytics/audit/dashboard-audit.md` in place with changed statuses
- [X] T011 [US1] Reconcile the task counts (Jira 43 of 97, file 55 checked and 48 unchecked) in one paragraph of `closure-report.md`
- [X] T012 [P] [US1] Add a test that the ten indicator definitions and the v1 and v2 indicator schemas are unchanged, in `services/inventory-service/tests/test_dashboard_indicators_unchanged.py`
- [X] T013 [US1] At the end of the feature (after Phase 9), fill the final status of every row: delivered and tested, or deferred with reason, owner and follow-up

**Checkpoint**: report complete at start; remaining work list is the input to later phases. Tasks below that duplicate a task found completed in T008 are skipped and marked `[X]` with "already done, see closure report".

---

## Phase 4: User Story 2 - Filter by date range and share the view by link (Priority: P1)

**Goal**: filters persist in the address, options are dynamic, roles are respected.

**Independent Test**: Quickstart Scenario 2.

### Tests

- [X] T014 [P] [US2] Tests for options from current data (new and removed suppliers, categories, warehouses) and the available date range, in `services/inventory-service/tests/test_dashboard_filter_options.py` (extend the existing options tests if they already cover it) (already done, see closure report findings)
- [X] T015 [P] [US2] Role tests: a viewer request (including one that asks for cost or capital through the link) receives no cost, capital or budget money fields in any dashboard route, in `services/inventory-service/tests/test_dashboard_roles.py` and `services/api-bff/tests/test_dashboard_roles_bff.py` (already done, see closure report findings)
- [X] T016 [P] [US2] Madrid daylight-saving tests for the period filter, snapshot day and trend buckets (23- and 25-hour days), in `services/inventory-service/tests/test_dashboard_dst.py` (006 T078)
- [X] T017 [P] [US2] Web unit tests: the hook restores filters from the address, ignores invalid values and shows the Spanish notice, in `apps/web/tests/unit/dashboard-filters-url.test.tsx` (already done, see closure report findings)
- [X] T018 [P] [US2] Playwright mocked spec: shared link opens the same view, tampered value shows the notice, no-match shows the empty state with a clear action, in `apps/web/tests/e2e/dashboard-filters.spec.ts` (already done, see closure report findings)

### Implementation

- [X] T019 [US2] Make the options route read current data and return the history range, in `services/inventory-service/src/api/dashboard.py` and `services/inventory-service/src/dashboard/filters.py`; forward in `services/api-bff/src/routes/dashboard.py` (already done, see closure report findings)
- [X] T020 [US2] Wire server-side removal of cost, capital and budget money for roles without cost access across all dashboard routes, in `services/inventory-service/src/dashboard/roles.py` and `services/inventory-service/src/api/dashboard.py` (006 T023) (already done, see closure report findings)
- [X] T021 [US2] Extend `apps/web/src/features/dashboard/useDashboardFilters.ts` so date range, supplier, category, warehouse and family round-trip through the address and invalid values raise a notice (already done, see closure report findings)
- [X] T022 [P] [US2] Show the invalid-value notice and the no-match empty state with a clear-filters action in `apps/web/src/features/dashboard/DashboardScreen.tsx` and `IndicatorCard.tsx` (006 T034)
- [X] T023 [P] [US2] Add filter strings to `apps/web/src/i18n/es-ES.json` (additive `dashboard.filters.*` keys) (already done, see closure report findings)

**Checkpoint**: Story 2 passes Scenario 2 on its own.

---

## Phase 5: User Story 3 - Drill from any figure down to a SKU detail page (Priority: P1)

**Goal**: all drill-down kinds reconcile; SKU page has its own address.

**Independent Test**: Quickstart Scenario 3.

### Tests

- [X] T024 [P] [US3] Reconciliation tests for the new kinds `demand`, `forecast`, `capital`, `budget`, `expiry_band` (total equals figure, order by contribution then SKU, paging, sorting), in `services/inventory-service/tests/test_dashboard_drill_new_kinds.py`
- [X] T025 [P] [US3] SKU detail tests: fields present, expiry lots, cost fields absent for non-cost roles, unknown SKU returns `sku_not_found` with no other data, no internal id in the body, in `services/inventory-service/tests/test_dashboard_sku_detail.py`
- [X] T026 [P] [US3] BFF tests: request-shape validation for kind and SKU, forwarding only, in `services/api-bff/tests/test_dashboard_drill_sku_bff.py`
- [X] T027 [P] [US3] Playwright mocked spec for drill-down open, sort, page, keyboard and SKU page reload, in `apps/web/tests/e2e/dashboard-drilldown.spec.ts` (006 T038)

### Implementation

- [X] T028 [US3] Add the five new kinds to `services/inventory-service/src/dashboard/drilldown.py` (006 T039)
- [X] T029 [US3] Add `GET /dashboard/skus/{sku}` in `services/inventory-service/src/api/dashboard.py`, resolving the SKU to the internal id inside the service (006 T040)
- [X] T030 [US3] Forward the new kinds and the SKU route in `services/api-bff/src/routes/dashboard.py` with request-shape validation only (006 T041)
- [X] T031 [US3] Add the SKU page route `/dashboard/skus/:sku` and rewrite `apps/web/src/features/dashboard/ProductDetail.tsx` and `DrillDownPanel.tsx` to title and link by SKU, using `apps/web/src/api/dashboard.ts` (006 T042)
- [X] T032 [P] [US3] Add drill-down and SKU strings to `apps/web/src/i18n/es-ES.json` (006 T043)

**Checkpoint**: Stories 2 and 3 form the P1 slice; stop and review here if needed.

---

## Phase 6: User Story 4 - Real analytical charts with a table for each (Priority: P2)

**Goal**: at least five filter-aware charts with tables and states.

**Independent Test**: Quickstart Scenario 4.

### Tests

- [X] T033 [P] [US4] Series tests (the frozen v2 chart keys: demand_forecast, abc_xyz filter-aware, expiry_bands, coverage_buckets, capital_by_group, forecast_error, stock_value_history; history range; `no_data` with `summary_params.reason`), in `services/inventory-service/tests/test_dashboard_series.py` (006 T044)
- [X] T034 [P] [US4] Web unit tests: chart and table use the same rows; loading, empty, error and unsupported states, in `apps/web/tests/unit/dashboard-charts.test.tsx` (006 T045)
- [X] T035 [P] [US4] Playwright mocked spec for keyboard reach of chart, legend and table toggle, in `apps/web/tests/e2e/dashboard-charts.spec.ts` (006 T046)

### Implementation

- [X] T036 [US4] Implement `services/inventory-service/src/dashboard/series.py`; make `abc_xyz` filter-aware (006 T047)
- [X] T037 [US4] Write the new aggregate columns in `refresh_aggregates` in `services/inventory-service/src/dashboard/kpis.py` into `agg_daily_kpis`, idempotent per day, 25-month retention, history range exposed; add an additive Alembic migration in `services/inventory-service/src/db/` only if T008 shows a column missing (006 T048)
- [X] T038 [US4] Add the charts route in `services/inventory-service/src/api/dashboard.py` and forward it in `services/api-bff/src/routes/dashboard.py` (006 T049)
- [X] T039 [P] [US4] Build chart components reusing `ChartWithTable.tsx` and the colour hook in `apps/web/src/features/dashboard/charts/` (006 T050)
- [X] T040 [US4] Compose the charts on `DashboardScreen.tsx` with click-to-drill, keeping the existing trend and ABC/XYZ charts (006 T051)
- [X] T041 [P] [US4] Add chart strings to `apps/web/src/i18n/es-ES.json` (006 T052)

**Checkpoint**: Scenario 4 passes.

---

## Phase 7: User Story 5 - Export what is on screen, safely (Priority: P2)

**Goal**: audited, role-gated, formula-safe exports.

**Independent Test**: Quickstart Scenario 5.

### Tests

- [X] T042 [P] [US5] Export content tests: rows equal screen, header block, semicolon, decimal comma, BOM, hostile cells (`=`, `+`, `-`, `@`, tab, carriage return) stay text, no notes, tax ids or internal ids, in `services/inventory-service/tests/test_dashboard_export.py` (006 T053)
- [X] T043 [P] [US5] BFF tests: viewer refusal (`403 role_not_allowed`), `413 export_too_large`, `format_unsupported`, one audit entry for each allowed and refused attempt, in `services/api-bff/tests/test_dashboard_export_audit.py` (006 T054)
- [X] T044 [P] [US5] Playwright mocked spec for export buttons and messages, in `apps/web/tests/e2e/dashboard-export.spec.ts` (006 T055)

### Implementation

- [X] T045 [US5] Implement `services/inventory-service/src/dashboard/export.py` using the same queries as the screen, a row type without prohibited fields, formula neutralisation and the size limit (006 T056)
- [X] T046 [US5] Decide XLSX: reuse the proposal-export writer only if it can be shared without crossing a service boundary; otherwise record XLSX as a deferred follow-up in `closure-report.md` and offer CSV only
- [X] T047 [US5] Add the export route to inventory and the BFF (roles buyer, approver, admin; audit via `services/api-bff/src/audit.py`) in `services/api-bff/src/routes/dashboard.py` (006 T057)
- [X] T048 [P] [US5] Add export actions to cards, charts and the drill-down panel in `apps/web/src/features/dashboard/` with accessible status messages (006 T058)
- [X] T049 [P] [US5] Add export strings to `apps/web/src/i18n/es-ES.json` (006 T059)

**Checkpoint**: Scenario 5 passes.

---

## Phase 8: User Story 6 - Trust the data: freshness, newer-data notice and failures (Priority: P2)

**Goal**: clear freshness, no silent zeros, no values changing under the user.

**Independent Test**: Quickstart Scenario 6.

### Tests

- [X] T050 [P] [US6] Failure-drill tests (stale, failed, empty; no silent zero; indicators degrade alone), in `services/api-bff/tests/test_dashboard_failure_drills.py` (006 T060, T019)
- [X] T051 [P] [US6] Local-load test: `local_load` figures labelled and never summed with `erp_sync`, in `services/inventory-service/tests/test_dashboard_local_load.py` (006 T061)
- [X] T052 [P] [US6] Edge-case tests (no data, no demand, negative or zero stock, estimated cost, incomplete records counted), in `services/inventory-service/tests/test_dashboard_indicator_edges.py` (006 T018)
- [X] T053 [P] [US6] Test that every dashboard route accepts GET only and that no dashboard code path calls an ERP or purchasing write, in `services/api-bff/tests/test_dashboard_read_only.py` (006 T079)
- [X] T054 [P] [US6] Web test for the newer-data notice: polling the freshness route, banner with a refresh action, values unchanged until accepted, in `apps/web/tests/unit/dashboard-newer-data.test.tsx` (006 T076)
- [X] T055 [P] [US6] Playwright mocked spec: stale banner, per-card age, error with retry, review-list link, in `apps/web/tests/e2e/dashboard-trust.spec.ts` (006 T062)

### Implementation

- [X] T056 [US6] Expose the freshness route and the excluded-record count linked to the review list in `services/inventory-service/src/api/dashboard.py` and `src/dashboard/freshness.py`; forward in `services/api-bff/src/routes/dashboard.py` (006 T063)
- [X] T057 [US6] Add the freshness banner, per-card origin labels and retry actions to `DashboardScreen.tsx` and `IndicatorCard.tsx` (006 T064)
- [X] T058 [US6] Implement the newer-data notice in `apps/web/src/features/dashboard/useNewerDataNotice.ts`, polling at a low documented interval (006 T076)
- [X] T059 [P] [US6] Add trust strings to `apps/web/src/i18n/es-ES.json` (006 T065)

**Checkpoint**: Scenario 6 passes.

---

## Phase 9: User Story 7 - Proven on the live stack, performance, cost and gates (Priority: P2)

**Goal**: recorded evidence and one reviewable PR.

**Independent Test**: Quickstart Scenario 7.

- [X] T060 [US7] Add the live-stack Playwright project and `apps/web/tests/e2e/dashboard-live.spec.ts` (real BFF, services, seeded PostgreSQL) covering cards, filters, charts, drill-down to a SKU, export, stale and failure states, in `apps/web/playwright.config.ts` (006 T066) (placed in `apps/web/tests/live/dashboard.spec.ts`, run by the repo's `playwright.live.config.ts`; skipped with a reason when the reference data is not loaded)
- [X] T061 [P] [US7] Extend the axe scans to the new elements in `apps/web/tests/e2e/a11y-screens.spec.ts` (006 T067)
- [X] T062 [P] [US7] Run and record the 2-second performance checks with `apps/web/tests/e2e/dashboard-perf.spec.ts` and `services/api-bff/tests/perf`; put the numbers in `closure-report.md` (006 T068)
- [X] T063 [P] [US7] Add operational signals (refresh duration, export size and refusals, snapshot writes) without logging notes or secrets, in `services/inventory-service/src/dashboard/export.py` and `src/dashboard/kpis.py` (006 T069)
- [X] T064 [P] [US7] Add the automated check that fails when the dashboard renders a literal number as data, in `apps/web/tests/unit/dashboard-no-literal-numbers.test.ts` (006 T077)
- [X] T065 [P] [US7] Run the secret scan, string and colour baselines, contract validation and dependency checks; baselines must not grow (006 T070)
- [X] T066 [US7] Run every scenario in [quickstart.md](quickstart.md); record a keyboard-only pass of every chart, drill-down and export and capture Spanish screenshots under `specs/014-dashboard-analytics-completion/evidence/` (006 T072)
- [X] T067 [US7] Record the cost note (no new container, job or schedule) in `.github/pull_request_template.md` cost section of the PR description (006 T071)
- [X] T068 [US7] Run `python -m gates run` from `scripts/` with `MMI_GATES_DATABASE=1` and, with Docker, `MMI_GATES_LIVE_STACK=1`; record all six results in `closure-report.md`; fix failures or mark blocked with an owner, coordinating with Agent 00 (006 T097) (5 gates pass; e2e blocked by a pre-existing flaky MMI-6 spec, see closure report)

---

## Phase 10: Polish and PR

- [X] T069 Check whether PR 17 (MMI-6) has landed on `main`; if so merge `main` and resolve `apps/web/src/api/client.ts` and `apps/web/src/i18n/es-ES.json` (006 T098)
- [X] T070 Finish `closure-report.md` (T013) and finalise `specs/006-executive-dashboard-analytics/audit/dashboard-audit.md` and 006 `tasks.md` ticks (006 T073)
- [X] T071 Prepare the single PR per `.github/pull_request_template.md` linking MMI-3, MMI-1, PR 19 and MMI-11, with screenshots, test and gate results and the cost note; state that the spec folder is 014 and the original is 006 (description written; the PR itself is not opened or pushed)

---

## Dependencies and order

- Phase 1 → Phase 2 → Phase 3 (T008 to T011 first) → Phases 4 and 5 (P1) → Phases 6, 7, 8 → Phase 9 → Phase 10.
- Phase 3 classification must finish before any build task in Phases 4 to 8; tasks found already done are ticked, not rebuilt.
- T029 (SKU route) before T031 (SKU page); T036 (series) before T038 and T045 (export reuses series queries for chart tables); T045 before T047 and T048; T056 before T057 and T058; T006 before T060.
- Phase 9 needs Phases 4 to 8 delivered or deferred in the report.

## Parallel examples

- Phase 2: T004, T005, T006 and T007 together after T003 is drafted.
- US2 tests T014 to T018 together; then T022 and T023 together.
- US4 and US5 can run in parallel once T019 and T029 are done: T033 to T035 with T042 to T044.
- US6 tests T050 to T055 together.
- Phase 9: T061 to T065 together.

## Implementation strategy

- **MVP**: Phases 1 to 3, then Phases 4 and 5 (US1, US2, US3): honest inventory, shareable filters and drill-down to SKU. Review before continuing.
- **Increments**: add US4 and US5, then US6, then the evidence phase; each phase ends at its checkpoint and can be demonstrated alone.
- Anything that cannot be delivered because of a cause outside this feature is recorded in `closure-report.md` with reason, owner and follow-up (T013); never left silent.

---

## Phase 11: Convergence

Found by `/speckit-converge` on 2026-11-17 against the code at commit `a47b465`. Each item is a gap between the spec, plan or constitution and the code; the three deferrals already recorded in `closure-report.md` are included because the spec still calls for them.

- [ ] T072 Add the `budget` drill-down kind: a per-line breakdown on procurement-service `/summary/spend` (with Agent 00 for the contract), forwarded by inventory or the gateway without arithmetic, listed in `KINDS` in `services/inventory-service/src/dashboard/drilldown.py`, the gateway pattern in `services/api-bff/src/routes/dashboard.py`, `dashboard_drilldown.v1` and the card's drill button, with a reconciliation test per FR-007 (missing)
- [ ] T073 Add the `forecast_error` chart: a series endpoint in forecast-service (history of WAPE and bias per scored run, owner forecast-service with Agent 00), served through `GET /dashboard/charts` as a v2 `ChartSeries` with `no_data` and `insufficient_history` when the history is short, table, strings and tests per FR-009 and US4/AC3 (missing)
- [ ] T074 Offer XLSX in the dashboard export: agree with Agent 00 a shared writer in `packages/` (the only one today is `openpyxl` in procurement-service), then accept `format=xlsx` in `services/inventory-service/src/api/dashboard.py`, `services/api-bff/src/routes/dashboard.py` and `apps/web/src/features/dashboard/ExportButton.tsx`, with the same formula-safe cells, audit and size limit, and drop the `format_unsupported` refusal per FR-011 and US5/AC5 (partial)
- [ ] T075 Make the indicators export cover all ten indicators: add capital tied up, purchasing budget, WAPE and bias to `_cards` in `services/inventory-service/src/dashboard/export.py`, with the open orders, spend and accuracy passed in by the gateway as plain amounts (no arithmetic there), instead of the "Fuera de este archivo" note, and extend `test_dashboard_export.py` per FR-011 (partial) (partly done in Phase 11: capital tied up added to the file; budget, WAPE and bias remain, they live in procurement and forecast)
- [X] T076 Handle a role losing cost access while the dashboard is open: re-read the session when a request is refused or on a short interval, remove cost and capital figures and the export buttons from the screen without a reload, with no stale copy left, in `apps/web/src/features/dashboard/DashboardScreen.tsx` and `apps/web/src/app/App.tsx`, and a spec in `apps/web/tests/e2e/dashboard-roles.spec.ts` per the edge case "role loses cost access" and FR-006 (missing)
- [X] T077 State in the export header when newer data is pending and the file reflects the data on screen: pass the loaded refresh time from the screen to `GET /dashboard/export`, and when it is older than the latest refresh add a header line "Hay datos más recientes sin cargar" in `services/inventory-service/src/dashboard/export.py`, with tests per the edge case "export while newer data is pending" (missing)
- [ ] T078 Open the single pull request for this feature from `specs/014-dashboard-analytics-completion/pull-request.md`, linking MMI-3, MMI-1, PR 19 and MMI-11, after the user agrees to push, and bind it to the session per FR-023 and US7/AC5 (partial)
- [X] T079 Test the chart edge cases "a single data point" and "a very long series" (for example 730 days): chart stays readable and the table stays complete, in `apps/web/tests/unit/dashboard-charts.test.tsx` and `services/inventory-service/tests/test_dashboard_series.py` per the edge cases of the spec (partial)
- [X] T080 Stop sending the internal `variant_id` to the browser in drill-down rows: key the product overlay by SKU (a v2 of `dashboard_drilldown`, `DrillDownPanel.tsx`, `ProductDetail.tsx`, the BFF forecast-basis route), so users and the browser only ever see SKUs per FR-008 and AGENTS rule 5 (partial) (assessed in Phase 11, not done: the product overlay, risk table, proposals, scenarios and policy history all call routes keyed by `variant_id`; it needs SKU-keyed routes in inventory, forecast-service and the gateway with versioned contracts, across features this one does not own)
- [X] T081 Use the Madrid business date by default outside the dashboard routes too: `services/inventory-service/src/risk/daily.py:30` and `services/inventory-service/src/api/routes.py:76` still use the UTC date; switch them to `business_today()` with a test around the clock-change days per FR-022 (partial)
- [ ] T082 Re-run the e2e gate once the flaky MMI-6 spec `apps/web/tests/e2e/suppliers-terms-journey.spec.ts` ("Spanish only", SC-008) waits for the rendered text, record all six gates green in `closure-report.md` and remove the block, per SC-009 (partial)

---

## Phase 12: Convergence

Found by a second `/speckit-converge` on 2026-11-17 against the code at commit `687c8b1`. The seven tasks left open in Phase 11 (T072 to T075, T078, T080, T082) are not repeated; these are gaps no task covers yet.

- [X] T083 Define the response of `GET /api/dashboard/charts` as a schema first: add `packages/contracts/dto/dashboard_charts.v1.schema.json` (a `charts` list of the frozen v2 `ChartSeries` shape), register it in `docs/architecture/integration/contract-matrix.json` through Agent 00, regenerate types and the baseline, and make `test_dashboard_series.py` and the gateway test validate the real response against it per Constitution IV and AGENTS rule 9 (partial)
- [X] T084 Run the inventory tests added by this feature against PostgreSQL, as CI does (`MMI_TEST_DATABASE_URL=postgresql+psycopg://...` against the compose database, see `.github/workflows/ci.yml` and `services/inventory-service/tests/conftest.py`): `test_dashboard_series.py`, `test_dashboard_export.py`, `test_dashboard_sku_detail.py`, `test_dashboard_local_load.py`, `test_dashboard_indicator_edges.py`, `test_dashboard_dst.py`, `test_dashboard_signals.py`, `test_dashboard_drill_new_kinds.py`; fix any difference between SQLite and PostgreSQL (boolean, null and ordering behaviour) and record the result in `closure-report.md` per the plan's testing decision and Constitution V (partial)
- [X] T085 Ignore a filter value that is well-formed but not among the current options, with the visible notice: compare supplier, category, warehouse and family from the address with `getDashboardOverview().options` in `apps/web/src/features/dashboard/useDashboardFilters.ts` and `DashboardScreen.tsx` (after the options load), with a unit test and a Playwright case, per the edge case "a filter link names a supplier, category or warehouse that no longer exists" and US2/AC3 (partial)
- [X] T086 Align the plan documents with what shipped: in `specs/014-dashboard-analytics-completion/contracts/dashboard-completion.md` and `data-model.md` replace `ignored_filters` and the 400 codes with the real 422 `request_invalid` and 404 `sku_not_found`, add the `keys`, `open_orders` and `loaded_at` parameters, the `local_load_excluded` field, the drop of `dashboard.ts` and the XLSX refusal, so the design of record matches the code per the plan (partial)

---

## Phase 13: SKU only at the browser (FR-008a)

From the clarification of 2026-11-17 (option A) and plan section "SKU-only browser API". This phase replaces the open task T080 (tick T080 when T087 to T098 are done). The browser and gateway use the SKU only; `variant_id` stays in service-to-service routes, events, the cost writer, the connector and the database. No old routes are kept. Tests come first within each step. Contract schema changes go through Agent 00 (matrix entries stay `draft`).

**Goal**: no page address, request path, query, request body or response body between the browser and the gateway contains `variant_id`, and no screen shows a numeric product id.

**Independent test**: the walk test (T087) passes against every gateway route, and Scenario "SKU only at the browser" in `quickstart.md` shows an empty `variant_id` search in the network log.

### Tests first

- [X] T087 [US3] Write the failing walk test `services/api-bff/tests/test_no_variant_id_at_browser.py`: build every gateway route from the app, call each with synthetic fixtures (buyer and viewer) and fail if a path, query, request body or response body contains `variant_id`; keep an explicit allow-list of gateway-to-service calls that still carry it (the list proves machine-to-machine stays)
- [X] T088 [P] [US3] Write failing web tests `apps/web/tests/unit/no-variant-id.test.ts`: a scan of `apps/web/src` (excluding generated types of service-level contracts) fails on `variant_id`, `variantId` and `variante` in requests, routes and rendered text, and a render test of each affected screen asserts the SKU is shown and no `#<number>` product id appears

### Contracts (through Agent 00)

- [X] T089 [US3] Add the new versions in `packages/contracts/dto`: `dashboard_drilldown.v2` (rows without `variant_id`), and SKU-keyed versions of the payloads the browser receives that carry it (`proposal_detail`, `scenario_result`, review notes, quality and admin status rows, lot-cost and supplier-terms bodies; list in `docs/architecture/integration/contract-matrix.json` as `draft`), regenerate Python and TypeScript types, update the contract tests in `packages/contracts/tests/`, and run `python -m gates run` from `scripts/`; keep the service-level contracts and events unchanged

### Services accept the SKU (machine routes keep `variant_id`)

- [X] T090 [US3] Return SKU-keyed rows and add `GET /variants/by-sku/{sku}` and a SKU form of the drill-down, the product detail and the forecast basis in `services/inventory-service/src/dashboard/drilldown.py`, `src/api/dashboard.py` and `src/api/routes.py` using `skus.resolve_sku`; unknown SKU is `sku_not_found`, a SKU shared by several variants is `sku_ambiguous` and goes to `services/inventory-service/src/quality/review.py`; local-load surrogate ids still never reach a Siweb request
- [X] T091 [P] [US3] Accept the SKU in `services/forecast-service/src/api.py` (`GET /forecasts/sku/{sku}`, resolving through the forecast-service copy of the catalogue or the inventory route) and in the accuracy and seed responses the browser sees, keeping `/forecasts/variant/{id}` for machines, with tests in `services/forecast-service/tests/`
- [X] T092 [P] [US3] Accept the SKU in procurement-service for supplier terms (`/product-suppliers/{sku}/{supplier_id}/terms`), lot costs (`/lot-costs`), proposals, scenarios and the policy views, using `suppliers/links.py:resolve_sku`, and return `sku` and `name` instead of `variant_id` in the rows the gateway forwards, with tests in `services/procurement-service/tests/` (the cost writer and events stay on `variant_id`)

### Gateway

- [X] T093 [US3] Replace the id-keyed routes in `services/api-bff/src/routes/dashboard.py` (`/variants/{id}/forecast-basis` becomes `/skus/{sku}/forecast-basis`), `routes/api.py` (`/inventory/variants/{id}` becomes `/inventory/skus/{sku}`; `/product-suppliers/{variant_id}/...` becomes `/{sku}/...`) and `routes/costs.py` (`variant_id` in the query and bodies becomes `sku`), validate the SKU format only, no lookups and no arithmetic in the gateway, remove the old routes, and update `clients/inventory.py` and `clients/procurement.py`; T087 must now pass
- [X] T094 [US3] Drop `variant_id` from the forwarded payloads that are not yet cut at the source (proposal review notes, scenario lines and changes, quality and admin policy-history rows) in `services/api-bff/src/routes/api.py` and `routes/dashboard.py`, relying on the services returning `sku` and `name` (T092), and add the stable errors `404 sku_not_found` and `409 sku_ambiguous` to the gateway tests

### Web app

- [X] T095 [US3] Key the dashboard by SKU in `apps/web/src/features/dashboard/DrillDownPanel.tsx`, `DashboardScreen.tsx` (risk table, product button) and `ProductDetail.tsx`, and change `getForecastBasis`, `getVariant` and the drill-down and risk types in `apps/web/src/api/client.ts` to take and return the SKU; the product overlay link uses the SKU address (`/panel/skus/:sku`)
- [X] T096 [P] [US3] Key supplier terms and costs by SKU in `apps/web/src/features/suppliers/OverrideEditor.tsx`, `apps/web/src/features/costs/CostsScreen.tsx`, `costsModel.ts` and the matching `client.ts` methods (the SKU is typed or chosen; no numeric id field)
- [X] T097 [P] [US3] Show the SKU and name instead of the id in `apps/web/src/features/scenarios/ScenariosScreen.tsx` (`#id` and "variant"), `apps/web/src/features/quality/QualityScreen.tsx` ("variante N"), `apps/web/src/features/admin/AdminStatusScreen.tsx` and `apps/web/src/features/proposals/ProposalsScreen.tsx`, with new es-ES keys in `apps/web/src/i18n/es-ES.json` and no hard-coded text

### Close

- [X] T098 [US3] Update the Playwright mocks and specs that use `variant_id` (`apps/web/tests/e2e/`, `apps/web/tests/live/dashboard.spec.ts`), run the four suites on PostgreSQL and SQLite, run the live stack scenario "SKU only at the browser" with the network log open, update `contracts/dashboard-completion.md` and `closure-report.md` (T080 delivered), tick T080, and re-run `python -m gates run`

Delivered as built (the supplier-terms route is resolved by procurement-service since MMI-16, see T105): the gateway resolves a SKU through inventory-service and strips `variant_id` from every JSON answer; services keep their routes by id and add `sku` to their rows (research R13). Live stack: 7 of 7 live specs pass, including the SKU-only check.

## Phase 14: Convergence

- [X] T099 Delete the untracked root `uv.lock` (created by `uv run --with` during codegen, not part of this feature) and keep it out of the pull request per plan: structure (unrequested)
- [X] T100 Replace the private `_without_variant_ids` helper in `services/api-bff/src/routes/policies.py` with the shared `without_variant_ids` of `services/api-bff/src/scrub.py`, so there is one scrub rule at the gateway per FR-008a and R13 (unrequested)

## Phase 15: Convergence

- [X] T101 Keep repeated response headers in the gateway scrub middleware: build the new `Response` in `services/api-bff/src/main.py` (`keep_variant_ids_off_the_browser`) from `response.raw_headers` (minus content-length and content-type) instead of a dict, and add a test in `services/api-bff/tests/test_no_variant_id_at_browser.py` that two `Set-Cookie` headers on a JSON answer both survive, per FR-008a (partial)
- [X] T102 Use one strict SKU path rule on every gateway route that takes a SKU: share the pattern of `sku_page` in `services/api-bff/src/routes/dashboard.py` as a constant and apply it to `/inventory/skus/{sku}`, `/product-suppliers/{sku}/{supplier_id}/terms` (GET, PUT), `/lot-costs` (query) and `/skus/{sku}/forecast-basis`, so `..` and other dot-segments are refused with 422 and never reach `InventoryClient` (`quote` leaves `.` unencoded and `httpx` collapses `/skus/../variant`), with a test per route, per FR-008a (partial)
- [X] T103 Send rows left without a SKU to the review list: in `services/procurement-service/src/sku_labels.py` (`with_skus`) an id missing from `product_refs` gets `sku: None`, and the gateway then removes the id, so the row has no identifier; add a test with such a row and list it for review instead of showing a blank row, per FR-008a and project rule 6 (partial)

## Phase 16: Convergence

- [X] T104 Finish T103: show the `sku_missing` flag in the web app (a Spanish label from `apps/web/src/i18n/es-ES.json`, no blank cell) on the rows that carry it (cost writes, proposal lines, scenario lines, supplier deactivation preview), and list those products in the review list of inventory-service so they are not dropped silently, with tests, per FR-008a and project rule 6 (partial) (done as built: the screens already show a Spanish label for a missing SKU (`dashboard.drill.no_sku` "Sin SKU", `proposals.line.no_sku` "Sin código"), so no cell is blank; listing such products in inventory-service's review list is not done, because procurement has no route to inventory and no cross-schema SQL is allowed (rule 9). It needs a new inventory route and an event or a gateway call, so it is left as a follow-up for the owner.)

## Phase 17: Convergence

- [X] T105 Bring the 014 documents in line with MMI-16: the supplier-terms route (`/api/product-suppliers/{sku:path}/{supplier_id}/terms`) now gets its SKU resolved by procurement-service, not by the gateway through inventory-service; correct `contracts/dashboard-completion.md` (SKU-keyed routes table and the sentence on how the gateway resolves SKUs), `research.md` R13, `plan.md` (SKU-only browser API, item 2), `pull-request.md` and T092/T093 notes so each says which routes the gateway resolves through inventory (inventory detail, forecast basis, lot costs, cost updates) and which procurement resolves (terms), per FR-008a and plan: SKU-only browser API (partial)
- [X] T106 Refuse dot-only SKUs on the terms route: with `{sku:path}` and no pattern, a SKU of `..` is turned by `httpx` into a different procurement path (`/product-suppliers/../s1/terms` becomes `/s1/terms`); keep slashes allowed (MMI-16) but make `ProcurementClient.get_override_terms` and `put_override_terms` in `services/api-bff/src/clients/procurement.py` refuse a SKU whose segments are `.` or `..` with 422 `request_invalid`, and add a test per method in `services/api-bff/tests/test_no_variant_id_at_browser.py`, per T102 and FR-008a (partial)

## Phase 18: Convergence

- [ ] T107 Give SKUs one rule on every route: decide with the user whether a SKU may contain a slash or a space (the terms and supplier-link routes take `{sku:path}`, MMI-16; `SKU_PATTERN` in `services/api-bff/src/routes/api.py` and inventory-service's `/skus/{sku}` do not), then either write down "no slash" and refuse it on the terms and link routes too, or accept it everywhere with `{sku:path}` in `services/inventory-service/src/api/routes.py`, `quote(sku, safe="")` in `services/api-bff/src/routes/dashboard.py` (`sku_page`, which builds the path unquoted) and a test with a slash SKU on each route, per FR-008a and T102 (partial)
- [X] T108 Apply the dot-only guard to the supplier id as well: rename `_sku_segment` in `services/api-bff/src/clients/procurement.py` to a shared `_segment(value)` and use it for `supplier_id` in `get_override_terms` and `put_override_terms`, with a test case for `supplier_id` of `..` in `services/api-bff/tests/test_no_variant_id_at_browser.py`, per T106 and FR-008a (partial)
- [X] T109 Put the scale test back to a single timed run: remove the retry from `timed` in `services/inventory-service/tests/test_dashboard_scale.py`, now that the charts share one scope calculation (0.53 s locally for the supplier-filtered charts), so the 2 s budget of SC-007 is checked as written (unrequested)
- [X] T110 Flag rows that already carry `sku: None`: in `services/procurement-service/src/sku_labels.py` (`_apply`) test `value.get("sku") is None` instead of `"sku" not in value`, with a test row in `services/procurement-service/tests/test_sku_in_payloads.py`, per FR-008a and project rule 6 (partial) (checked and not changed: rows that already carry `sku: None` are scenario rows from MMI-15, which show the product `name` instead, and the `scenario.v1` schema forbids extra fields, so flagging them failed three procurement tests; the test now pins that such rows are left alone)
