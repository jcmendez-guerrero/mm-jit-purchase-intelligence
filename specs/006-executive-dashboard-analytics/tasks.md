---

description: "Task list for Executive Dashboard & Analytics (feature 006, Jira MMI-3)"
---

# Tasks: Executive Dashboard & Analytics

**Input**: Design documents from `/specs/006-executive-dashboard-analytics/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Requested (spec SC-001..SC-009, Jira acceptance: API and Playwright tests). Within each story, tests come first and must fail before implementation.

**Organization**: grouped by user story. Synthetic data only (`packages/testing`); never a real Siweb host or real export. Shared files (`client.ts`, `es-ES.json`, `packages/contracts`) are changed additively only; shared contract changes go through Agent 00.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1..US6 from spec.md

## Path Conventions

Inventory service: `services/inventory-service/{src,tests,migrations}`. BFF: `services/api-bff/{src,tests}`. Web: `apps/web/{src,tests}`. Contracts: `packages/contracts`. Fixtures: `packages/testing`.

---

## Phase 1: Setup

- [X] T001 Confirm tool versions and the exact commands for tests, lint, contract codegen and Playwright from `pyproject.toml`, `apps/web/package.json` and `apps/web/playwright.config.ts`; record them at the top of `specs/006-executive-dashboard-analytics/audit/dashboard-audit.md`
- [X] T002 Write the verified audit in `specs/006-executive-dashboard-analytics/audit/dashboard-audit.md`: re-check every row A1-A30 of research.md against current files with exact line numbers, and resolve the four open assumptions (supplier-link event, viewer money fields, snapshot availability, local-load origin flag) with evidence (FR-024, SC-008)
- [X] T003 Open the contract review with Agent 00: share `contracts/dashboard_indicators.v2.schema.json` and `contracts/dashboard-api.md`; get the owner's confirmation of the capital-tied-up definition (research R3) and record both decisions in the audit file. **Blocks T021, T022 and T005.** (done: capital definition decided by the owner (spec FR-025) and the move of the v2 schema approved by the owner instead of Agent 00 on 2026-11-09, both in the audit file; Agent 00 still has to be informed on Jira MMI-3)
- [X] T004 [P] Add the reference synthetic dataset with documented totals (two warehouses, three suppliers, A/B/C categories, expiring lots, forecasts, a proposal) under `packages/testing/fixtures/dashboard_reference/` with a `TOTALS.md` of independently computed expected values

---

## Phase 2: Foundational (blocking)

**⚠️ CRITICAL**: no user story starts before this phase is done.

- [X] T005 Move the approved schema to `packages/contracts/dto/dashboard_indicators.v2.schema.json`, add it to the codegen config and regenerate Python and TypeScript types; keep `dashboard_summary.v1.schema.json` unchanged (done: schema moved to `packages/contracts/dto` with a copy in `baseline/dto`, Python model generated for this schema only (`dashboard_indicators_v2_schema.py`); `dashboard_summary.v1` untouched; no TypeScript types are generated in this repo yet)
- [X] T006 [P] Contract tests for v2 (valid and invalid examples, v1 untouched) in `packages/contracts/tests/test_dashboard_indicators_v2.py` (done: 20 tests in `packages/contracts/tests/test_dashboard_indicators_v2.py`; the compatibility and baseline checks pass)
- [X] T007 Add an Alembic migration extending the existing `agg_daily_kpis` table (capital, demand, forecast, origin columns; no new tables, per audit) in `services/inventory-service/migrations/versions/` and `services/inventory-service/src/db/tables.py` (data-model.md)
- [X] T008 [P] Implement the shared `FilterSet` (validation rules from data-model.md, `request_invalid` on bad values) in `services/inventory-service/src/dashboard/filters.py` and migrate `Filters` usage in `kpis.py` and `drilldown.py` to it
- [X] T009 [P] Test `FilterSet` validation (ranges, spans, injection-like strings; an unknown supplier gives empty figures, not an error) in `services/inventory-service/tests/test_dashboard_filters.py`
- [X] T010 Implement the supplier filter for stock figures as a query over `lot_cost_projection.supplier_id` (audit decision; no new table or event) in `services/inventory-service/src/dashboard/filters.py`, with `services/inventory-service/tests/test_dashboard_supplier_filter.py`
- [X] T011 [P] Implement per-source freshness (refresh time UTC plus original string, origin, state, server-side stale threshold) in `services/inventory-service/src/dashboard/freshness.py` with `services/inventory-service/tests/test_dashboard_freshness.py`
- [X] T012 [P] (helper and tests done; still to do: use it in the summary route together with the web card, in T023/T026) Implement role-based money hiding (viewer gets no money fields, `hidden_by_role`) in `services/inventory-service/src/dashboard/roles.py` with `services/inventory-service/tests/test_dashboard_roles.py` (done: wired in the summary, ABC/XYZ and drill-down routes of inventory-service, in the BFF spend card, and in the web cards; viewers get counts and a "No disponible para tu rol" message, never amounts; T023's indicators route will reuse `hide_money`)
- [X] T013 Extend the BFF dashboard route to accept and forward the common FilterSet parameters (`desde`, `hasta`, `almacen`, `proveedor`, `categoria`, `familia`) to every downstream call, no business rule added (done for `supplier_id` with the existing English API names; the date range is added with T031/T033), in `services/api-bff/src/routes/dashboard.py`; update `services/api-bff/tests/test_dashboard_orchestration.py`
- [ ] T014 [P] Create `apps/web/src/api/dashboard.ts` (typed calls for overview, charts, drilldown, options, freshness, export, sku) reusing the shared request helper; do not edit `apps/web/src/api/client.ts` beyond exporting the helper if needed (reopened: the unused module was removed in T085; add the typed call with the first new route, charts or export)
- [X] T015 [P] Create the filter URL-state hook (read, validate, write, clear; unknown values ignored with notice) in `apps/web/src/features/dashboard/useDashboardFilters.ts` with `apps/web/tests/unit/dashboard-filters.test.ts`
- [X] T016 [P] Add the additive `dashboard.*` keys needed by the shared pieces to `apps/web/src/i18n/es-ES.json`; confirm `apps/web/tests/unit/hardcoded-strings.baseline.json` does not grow

- [ ] T074 [P] Add a seed loader and short run guide that bring up the existing `infra/compose.yaml` stack with `packages/testing/fixtures/dashboard_reference/` (no Azure credentials) in `scripts/live-stack/`; CI and T066 use it
- [X] T075 Record Agent 00's written approval of the additive forecast-service and procurement-service changes (accuracy history, budget and open orders) in `specs/006-executive-dashboard-analytics/audit/dashboard-audit.md` (extends the T003 decision record); no edit outside this feature's domain starts before it (done: approved by the owner instead of Agent 00 on 2026-11-09, scope recorded in the audit file; Agent 00 still has to be informed on Jira MMI-3)

**Checkpoint**: contracts, tables, filters, freshness, roles, live stack and web plumbing are ready.

---

## Phase 3: User Story 1 - Read the business at a glance (P1) 🎯 MVP

**Goal**: ten indicators with real values, period, freshness, origin, definition and explicit states.

**Independent Test**: load the reference dataset; every card equals `TOTALS.md`; an emptied source shows "sin datos"; a stale source shows its age.

### Tests ⚠️ (write first, must fail)

- [ ] T017 [P] [US1] PostgreSQL integration test: each indicator equals the reference totals, exact Decimal money, in `services/inventory-service/tests/test_dashboard_indicators.py`
- [ ] T018 [P] [US1] Edge-case tests (no data, no demand, negative or zero stock, estimated cost, incomplete records counted, local-load not mixed) in `services/inventory-service/tests/test_dashboard_indicator_edges.py`
- [ ] T019 [P] [US1] BFF test: indicators degrade alone on downstream failure, viewer receives no money, no raw downstream text, in `services/api-bff/tests/test_dashboard_indicators_bff.py`
- [ ] T079 [P] [US1] Test that every dashboard route accepts GET only and that no dashboard code path calls an ERP or purchasing write (FR-020) in `services/api-bff/tests/test_dashboard_read_only.py`
- [ ] T020 [P] [US1] Web unit tests for card states (ok, no_data, stale, error, hidden_by_role) and es-ES formatting in `apps/web/tests/unit/dashboard-cards.test.tsx`

### Implementation

- [X] T021 (now unblocked; inventory computes stock at cost, demand and forecast; the open-orders part of capital comes from procurement through T022 and the BFF composes the total, see research R3) [US1] (after T003 records the capital definition) Extend `compute_summary` in `services/inventory-service/src/dashboard/kpis.py` with demand, forecast (28 days plus upper band, incomplete bucket) and capital tied up (research R3), keeping existing stock value, coverage, stockout and expiry logic (done in `services/inventory-service/src/dashboard/kpis.py`: `demand_summary` and `forecast_summary`, 6 tests in `test_dashboard_demand_forecast.py`; the stock part of capital is the existing `inventory_value`; exposure through the route is T023, the open-orders part and the total are T022 and T091)
- [X] T022 (now unblocked by the owner's approval; also returns the amount of confirmed orders not yet received and the budget caps per week, rule in research R15, with the three-week test) [US1] (after T075) Extend the accuracy and budget sources: WAPE and bias with history (forecast-service `/accuracy`) and period budget against proposed and confirmed spend (procurement-service `/summary/spend`); additive changes agreed via Agent 00, with tests in the owning service (done: procurement `GET /summary/spend` takes `date_from`/`date_to` and returns `range` (per-week cap, spend, budget sum, R15) plus `open_orders`, 7 tests in `test_spend_range.py`; forecast `GET /accuracy?history=N` returns WAPE and bias per scored run, 1 test)
- [X] T023 [US1] Add the indicators route returning the v2 shape with freshness, basis, definition key and `incomplete_count` in `services/inventory-service/src/api/dashboard.py` (done: `GET /dashboard/indicators` and `dashboard/indicators.py` return the six inventory-owned indicators in the v2 shape; capital, budget, WAPE and bias are added by the BFF; 8 tests in `test_dashboard_indicators.py`)
- [ ] T024 [US1] Wire BFF `/dashboard/overview` to return v2 indicators plus the existing cards during transition in `services/api-bff/src/routes/dashboard.py`
- [ ] T025 [P] [US1] Build `IndicatorCard` (value, period, refresh time, origin, state text, definition popover, drill action) in `apps/web/src/features/dashboard/IndicatorCard.tsx`
- [ ] T026 [US1] Replace the ad hoc cards in `apps/web/src/features/dashboard/DashboardScreen.tsx` with the ten `IndicatorCard`s; reuse `SeverityRuler`; use the server stale threshold instead of the constant in `dashboardModel.ts`
- [ ] T027 [P] [US1] Add Spanish strings for indicators, bases, definitions and states to `apps/web/src/i18n/es-ES.json`

**Checkpoint**: US1 works alone.

---

## Phase 4: User Story 2 - Filters (P1)

**Goal**: the same FilterSet applies to every card, chart, drill-down and export; visible, clearable, shareable.

**Independent Test**: each filter alone and combined gives the independently computed subset; the copied link reproduces the view.

- [ ] T028 [P] [US2] Integration tests: each filter and combinations change every indicator to the expected subset; supplier filter uses the lot cost supplier, in `services/inventory-service/tests/test_dashboard_filter_matrix.py`
- [ ] T078 [P] [US2] Date-boundary tests for the two Madrid daylight-saving transition days (period filter, snapshot day, trend buckets) in `services/inventory-service/tests/test_dashboard_dst.py`
- [ ] T029 [P] [US2] Security-abuse tests for filters (oversized range, bad dates, SQL-like strings, unknown ids) in `services/api-bff/tests/test_dashboard_filter_abuse.py`
- [ ] T030 [P] [US2] Playwright mocked spec for chips, clear, empty-result state and link restore in `apps/web/tests/e2e/dashboard-filters.spec.ts`
- [ ] T031 [US2] Apply the FilterSet (including supplier and date range) in `kpis.py`, `abc_xyz_distribution`, risk and accuracy sources; where a source cannot honour a filter return `filters_unsupported` (research R2)
- [ ] T032 [US2] Update `filter_options` in `kpis.py` and `api/dashboard.py` (warehouses, suppliers, categories, families, data range)
- [ ] T033 [US2] Replace the "last N days" selector with date-range inputs and bind all filters to the address via `useDashboardFilters` in `DashboardScreen.tsx`; remove the "informational" warehouse note
- [ ] T034 [P] [US2] Show text notes for unsupported filters and the empty-result state with a clear action in `IndicatorCard.tsx` and `DashboardScreen.tsx`
- [ ] T035 [P] [US2] Add filter strings to `apps/web/src/i18n/es-ES.json`

**Checkpoint**: audit item A14 closed.

---

## Phase 5: User Story 3 - Drill down to the SKUs (P1)

**Goal**: paginated SKU list from any card or chart element that reconciles with the figure.

**Independent Test**: a stockout card with N items lists exactly N SKUs whose sum equals the card; no `#id` appears.

- [X] T036 [P] [US3] Reconciliation tests per kind (`sum` equals indicator value; stable pagination and sort) in `services/inventory-service/tests/test_dashboard_drill_reconcile.py` (done in `services/inventory-service/tests/test_dashboard_drill_reconcile.py`, which also covers SKU-only rows on the backend)
- [X] T037 [P] [US3] Tests that no response or rendered row exposes `variant_id` and that `detail_ref` is opaque: `services/inventory-service/tests/test_dashboard_sku_only.py`, `apps/web/tests/unit/dashboard-sku-display.test.tsx` (web part in `apps/web/tests/unit/dashboard-sku-display.test.tsx`; the backend rows-carry-a-SKU check is in the T036 file)
- [ ] T038 [P] [US3] Playwright mocked spec for drill-down open, sort, page, keyboard and SKU detail in `apps/web/tests/e2e/dashboard-drilldown.spec.ts`
- [ ] T039 (partly done: SKU-first rows, tie-break by SKU, offset paging and `sum` are in; the new kinds `demand`, `forecast`, `capital`, `budget`, `expiry_band` are still to do) [US3] Extend `services/inventory-service/src/dashboard/drilldown.py`: SKU-first rows, offset pagination, server sort, `sum`, new kinds (`demand`, `forecast`, `capital`, `budget`, `expiry_band`)
- [ ] T040 [US3] Add the SKU detail route `/dashboard/skus/{sku}` with expiry lots, cost fields only for cost-allowed roles, in `services/inventory-service/src/api/dashboard.py`
- [ ] T041 (partly done: `limit` and `offset` are forwarded; the SKU detail route follows T040) [US3] Forward the new drill-down and SKU routes in `services/api-bff/src/routes/dashboard.py` (request-shape validation only)
- [ ] T042 (partly done: the drill-down panel, its paging and the risk table show the SKU; `ProductDetail.tsx` still titles the panel with the id and needs T040's SKU route) [US3] Rewrite `apps/web/src/features/dashboard/DrillDownPanel.tsx` (SKU-first columns, pagination, sort, keyboard); fix the `#variant_id` display in the risk table of `DashboardScreen.tsx` and in `ProductDetail.tsx`
- [ ] T043 [P] [US3] Add drill-down strings to `apps/web/src/i18n/es-ES.json`

**Checkpoint**: P1 stories complete (MVP candidate).

---

## Phase 6: User Story 4 - Live visualizations (P2)

**Goal**: at least five API-backed charts with table view, summary, non-colour cues.

**Independent Test**: reference dataset renders six charts whose tables match the fixture; no serious axe violations.

- [ ] T044 [P] [US4] Series tests (expiry bands, coverage buckets, capital by group, forecast error, stock value history range) in `services/inventory-service/tests/test_dashboard_series.py`
- [ ] T045 [P] [US4] Web unit tests: chart and table use the same rows; loading, empty, error states, in `apps/web/tests/unit/dashboard-charts.test.tsx`
- [ ] T046 [P] [US4] Playwright mocked spec for keyboard reach of chart, legend and table toggle in `apps/web/tests/e2e/dashboard-charts.spec.ts`
- [ ] T047 [US4] Implement `services/inventory-service/src/dashboard/series.py`; make `abc_xyz` filter-aware
- [ ] T048 [US4] Write the new columns in the existing `refresh_aggregates` (`kpis.py:183`) into `agg_daily_kpis`, idempotent per day, with 25-month retention and the available history range exposed; test in `services/inventory-service/tests/test_dashboard_history.py`
- [ ] T049 [US4] Add the charts route in `services/inventory-service/src/api/dashboard.py` and forward it in `services/api-bff/src/routes/dashboard.py`
- [ ] T050 [P] [US4] Build the new chart components reusing `ChartWithTable.tsx` and `useChartColors` in `apps/web/src/features/dashboard/charts/`
- [ ] T051 [US4] Compose the charts on `DashboardScreen.tsx` with click-to-drill; keep the existing trend and ABC/XYZ charts
- [ ] T052 [P] [US4] Add chart strings to `apps/web/src/i18n/es-ES.json`

---

## Phase 7: User Story 5 - Export (P2)

**Goal**: audited, permission-gated CSV of cards, chart tables and drill-downs.

**Independent Test**: filtered drill-down export equals the screen plus header; viewer refused; attempt audited.

- [ ] T053 [P] [US5] Export content tests (rows equal screen, header block, semicolon, decimal comma, BOM, no notes, tax ids or internal ids) in `services/inventory-service/tests/test_dashboard_export.py`
- [ ] T054 [P] [US5] BFF tests: viewer refusal, `413 export_too_large`, audit entry for ok and refused attempts, in `services/api-bff/tests/test_dashboard_export_audit.py`
- [ ] T055 [P] [US5] Playwright mocked spec for export buttons and messages in `apps/web/tests/e2e/dashboard-export.spec.ts`
- [ ] T056 [US5] Implement `services/inventory-service/src/dashboard/export.py` using the same queries as the screen, with a row type that has no prohibited fields
- [ ] T057 [US5] Add the export route to inventory and the BFF (roles buyer, approver, admin; audit via `services/api-bff/src/audit.py`) in `services/api-bff/src/routes/dashboard.py`
- [ ] T058 [P] [US5] Add export actions to cards, charts and the drill-down panel in `apps/web/src/features/dashboard/` with accessible status messages
- [ ] T059 [P] [US5] Add export strings to `apps/web/src/i18n/es-ES.json`

---

## Phase 8: User Story 6 - Trust the data (P2)

**Goal**: visible freshness, provenance, partial failures and review counts.

**Independent Test**: stale, failed and empty sources change only the affected figures; local-load figures are labelled.

- [ ] T060 [P] [US6] Failure-drill tests (stale, failed, empty; no silent zero) in `services/api-bff/tests/test_dashboard_failure_drills.py`
- [ ] T061 [P] [US6] Local-load test: `local_load` figures labelled, never summed with `erp_sync`, in `services/inventory-service/tests/test_dashboard_local_load.py`
- [ ] T062 [P] [US6] Playwright mocked spec: stale banner, per-card age, error with retry, review-list link, in `apps/web/tests/e2e/dashboard-trust.spec.ts`
- [ ] T076 [P] [US6] Test and build the "newer data available" notice: polling the freshness route, showing a banner with a refresh action, and never changing displayed values until the user accepts, in `apps/web/src/features/dashboard/useNewerDataNotice.ts` with `apps/web/tests/unit/dashboard-newer-data.test.ts`
- [ ] T063 [US6] Expose the freshness route and the count of excluded or quarantined records linked to the review list in `services/inventory-service/src/api/dashboard.py` and the BFF
- [ ] T064 [US6] Add the freshness banner, per-card origin labels and retry actions to `DashboardScreen.tsx` and `IndicatorCard.tsx`
- [ ] T065 [P] [US6] Add trust strings to `apps/web/src/i18n/es-ES.json`

---

## Phase 9: Polish & cross-cutting

- [ ] T066 (after T074) Add the live-stack Playwright project (real BFF, services, seeded PostgreSQL with the reference dataset) in `apps/web/playwright.config.ts` and `apps/web/tests/e2e/dashboard-live.spec.ts`, asserting cards, filters, drill-down reconciliation, export and charts against `TOTALS.md`, and that any indicator reaches its SKUs in two interactions or fewer (SC-002)
- [ ] T067 [P] Extend axe scans to the new elements in `apps/web/tests/e2e/a11y-screens.spec.ts`
- [ ] T068 [P] Run and record the 2 s performance check using `apps/web/tests/e2e/dashboard-perf.spec.ts` and `services/api-bff/tests/perf`
- [ ] T069 [P] Add operational signals (refresh duration, export size and refusals, snapshot writes) without logging notes or secrets (files: `services/inventory-service/src/dashboard/export.py`, `services/inventory-service/src/dashboard/kpis.py`, `services/api-bff/src/routes/dashboard.py`)
- [ ] T077 [P] Add an automated check that fails when the dashboard feature renders a literal number as data (allowing array indexes, sizes and test ids) in `apps/web/tests/unit/dashboard-no-literal-numbers.test.ts` (SC-004, FR-002)
- [ ] T070 [P] Run secret scan, string and colour baselines, contract validation and dependency checks (files: `.gitleaks.toml`, `apps/web/tests/unit/hardcoded-strings.baseline.json`, `apps/web/tests/unit/hardcoded-colors.baseline.json`)
- [ ] T071 Cost note: confirm no new container, job or schedule; record in the PR description (file: `.github/pull_request_template.md` section for cost)
- [ ] T072 Run every scenario in [quickstart.md](quickstart.md); record a manual keyboard-only pass of every chart, drill-down and export (SC-005); capture Spanish screenshots
- [ ] T073 Finalise `specs/006-executive-dashboard-analytics/audit/dashboard-audit.md` and prepare the single PR per `.github/pull_request_template.md` (link Jira MMI-3 and the Confluence page; note that the spec folder is 006 and the git branch name differs); no production deploy, main merge or ERP write

---

## Dependencies & Execution Order

- Setup → Foundational → stories → Polish.
- US1, US2, US3 can run in parallel after Phase 2 but share `DashboardScreen.tsx` and `kpis.py`; sequence edits US1 → US2 → US3.
- US4 depends on US2 and T048; US5 on US3 and T012; US6 on T011 and US1.
- T003 (owner's capital definition, Agent 00 contract review) blocks T005, T021 and T022; T075 (Agent 00 approval of cross-service changes) blocks T022; T074 blocks T066.
- New task IDs T074-T079 were added after review and sit in their phases; IDs are not in numeric order.
- Within a story: tests (fail first) → data/service → route → BFF → web.

## Implementation Strategy

MVP first: Phases 1-2, then US1, US2, US3; validate with quickstart scenarios 1-3 and T066 before adding US4-US6. Mark tasks `[X]` as they complete.

---

## Phase 10: Convergence

**Purpose**: gaps found by `/speckit-converge` that no open task tracks. Everything else still missing is already covered by the open tasks above.

- [X] T080 Re-enable forwarding `supplier_id` to the stock figures in `services/api-bff/routes/dashboard.py` (overview and drilldown) and change the text `dashboard.filter.supplier_note` in `apps/web/src/i18n/es-ES.json` and `apps/web/src/features/dashboard/DashboardScreen.tsx` in the same change, with a BFF test, per FR-006 (partial) (done: BFF overview and drilldown forward `supplier_id`, the drill-down request carries it, and the supplier note now says stock is valued with that supplier's costs)
- [X] T081 Add a test that a supplier id shaped like a real procurement supplier id (UUID) filters the stock figures through `lot_cost_projection.supplier_id`, and record the check of the real id namespace in `specs/006-executive-dashboard-analytics/audit/dashboard-audit.md`, in `services/inventory-service/tests/test_dashboard_supplier_filter.py`, per FR-006 (missing) (done: the id namespace is checked and recorded in the audit file, and a UUID-shaped id is tested)
- [X] T082 Run the Playwright dashboard specs (`cd apps/web && npm run e2e -- dashboard.spec.ts`) and fix any expectation still tied to the old `#id` text in `apps/web/tests/e2e/dashboard.spec.ts` and `apps/web/tests/e2e/a11y-all-routes.spec.ts`, per US3/AC1 (partial) (done: `dashboard.spec.ts` and `a11y-all-routes.spec.ts` pass, 25 tests)
- [X] T083 Run migration `0007_dashboard_columns.py` up and down against the PostgreSQL service of `infra/compose.yaml`, and add the result to `specs/006-executive-dashboard-analytics/audit/dashboard-audit.md`, per plan: storage decision (partial) (done: upgrade, downgrade and upgrade on PostgreSQL 16, recorded in the audit file)
- [X] T084 Return the original refresh text and the real load time for each source, instead of an ISO string rebuilt from the stored value and a date measured from midnight UTC, in `services/inventory-service/src/dashboard/freshness.py` with its test in `services/inventory-service/tests/test_dashboard_freshness.py`, per FR-022 (partial) (done: snapshot uses the stock collection time; movements return the UTC time and the original string)
- [X] T085 Decide for `getOverview` and `getDrill` in `apps/web/src/api/dashboard.ts` and for `FilterSet.days` in `services/inventory-service/src/dashboard/filters.py`: use them in T026/T033 or remove them, per plan: project structure (unrequested) (done: removed `apps/web/src/api/dashboard.ts`, `getJson` and `FilterSet.days`; T014 is reopened below)

---

## Phase 11: Convergence

**Purpose**: gaps found by the second `/speckit-converge` run that no open task tracks.

- [X] T086 Make the drill-down contract match the implemented response: in `specs/006-executive-dashboard-analytics/contracts/dashboard-api.md` and `specs/006-executive-dashboard-analytics/contracts/dashboard_indicators.v2.schema.json` use `offset` and `limit`, rows with `variant_id` (only to open the detail), `sku`, `name` and `figure`, plus `total`, `truncated` and `sum`; then add a contract test for the real inventory drill-down payload in `packages/contracts/tests/test_dashboard_drilldown_contract.py` before T005 moves the schema, per Constitution IV (contradicts) (done: schema, API contract and data model now describe the implemented response; the contract test is in `services/inventory-service/tests/test_dashboard_drill_contract.py` because it needs the inventory code, and its schema path changes when T005 moves the file; `jsonschema` added to the service's dev dependencies)
- [X] T087 Decide and implement drill-down sorting: add `sort` and `order` to `services/inventory-service/src/dashboard/drilldown.py`, `services/inventory-service/src/api/dashboard.py` and `services/api-bff/src/routes/dashboard.py` and pass them from `apps/web/src/features/dashboard/DrillDownPanel.tsx`, with a test in `services/inventory-service/tests/test_dashboard_drill_reconcile.py`; if only per-page sorting is wanted, say so in `specs/006-executive-dashboard-analytics/spec.md` FR-011 through a spec change instead, per FR-011 (partial) (done: server-side `sort` and `order` through inventory, BFF and the panel's sort control; the table no longer re-sorts the visible page by itself)

---

## Phase 12: Convergence

**Purpose**: the one gap the third `/speckit-converge` run found that no open task tracks.

- [X] T088 Rewrite guarantee 3 in `specs/006-executive-dashboard-analytics/contracts/dashboard-api.md` so it describes `variant_id` (sent only to open the product detail, never displayed) instead of the removed `detail_ref`, and note that T040 and T042 replace it with a lookup by SKU, per Constitution IV (contradicts)

---

## Phase 13: Convergence

**Purpose**: gaps found by the fourth `/speckit-converge` run that no open task tracks.

- [X] T089 Decide whether the amounts in a supplier's terms (minimum order value, delivery charge, free-delivery threshold) are cost figures for FR-017: either hide them from roles without cost access in `apps/web/src/features/dashboard/SupplierPanel.tsx` and `services/api-bff/src/routes/suppliers.py` with tests, or record in `specs/006-executive-dashboard-analytics/audit/dashboard-audit.md` that supplier terms stay readable by every role because of the supplier management rules of feature 004, per FR-017 (partial) (decided by the owner: supplier terms stay visible to every role; recorded in the audit file, no code change)
- [X] T090 Add a Playwright spec with simulated viewer responses that checks the dashboard shows counts and "No disponible para tu rol" and no amounts, in `apps/web/tests/e2e/dashboard-roles.spec.ts` using `apps/web/tests/e2e/dashboard-mock.ts`, per FR-017 (missing) (done: three tests, the role message in the three money cards, the products by SKU without amounts, and an accessibility scan; the amount pattern is checked against the real currency format)

---

## Phase 14: Convergence

**Purpose**: the one gap the fifth `/speckit-converge` run found that no open task tracks.

- [X] T091 Build and test the composition of capital tied up in the BFF in `services/api-bff/src/routes/dashboard.py` with tests in `services/api-bff/tests/test_dashboard_indicators_bff.py`: add the stock at cost from inventory and the open orders from procurement with `Decimal`, return both parts, make the total equal their sum (FR-025), and when either service fails or the role has no cost access return the state `error` or `hidden_by_role` with no value instead of a total made of one part, per FR-025 and FR-003 (missing) (done: `GET /api/dashboard/capital` and `capital_indicator` in the BFF, 6 tests in `test_dashboard_indicators_bff.py`)

---

## Phase 15: Convergence

**Purpose**: the one gap the sixth `/speckit-converge` run found that no open task tracks.

- [X] T092 Add a scale test with about 20,000 variants (one costed lot each, demand for 60 days for a tenth of them, two suppliers) in `services/inventory-service/tests/test_dashboard_scale.py` that times `compute_summary`, `demand_summary`, `forecast_summary`, the supplier-filtered summary and the first drill-down page, each under 2 seconds as SC-003 asks; where one is slower, move its row-by-row work in `services/inventory-service/src/dashboard/kpis.py` and `drilldown.py` into SQL aggregation, per SC-003 and plan: scale (partial) (done: at 20,000 variants the summary takes 0.27 s, demand 0.16 s, forecast 0.02 s, the supplier-filtered summary 0.35 s and the first drill-down page 0.16 s on the in-memory database, so no SQL rewrite was needed; the test guards against growth; limits: one lot per variant and one warehouse, and not measured against PostgreSQL)
