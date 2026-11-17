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
