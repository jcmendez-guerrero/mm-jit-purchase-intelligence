# Closure report: Dashboard & Analytics Completion

Starting inventory taken 2026-11-16 on branch `claude/speckit-jira-mmi-11-93e5e3` (tip: merge of PR 25). Evidence is a file-existence check plus the named test functions; line numbers are given where a function was read. Statuses: **completed**, **remaining**, **unverified**. "Final" columns are filled at the end (T013).

## Commands and baseline (T002)

| Check | Command | Result at start |
|-------|---------|-----------------|
| Python sync | `uv sync --all-packages` | ok (creates `.venv`) |
| Inventory dashboard tests | `uv run pytest services/inventory-service/tests -k dashboard -q` | 102 passed |
| Lint | `uv run ruff check .` | run before the PR |
| Web | from `apps/web`: `npm run typecheck && npm test && npm run e2e` | run before the PR |

## Task counts (T011)

Jira MMI-11 says PR 19 delivered 43 of 97 tasks. `specs/006-executive-dashboard-analytics/tasks.md` on this branch has 55 checked and 48 unchecked tasks (103), because T074 to T079, T097 and T098 were added after the ticket was written. This report uses the file as the count of record.

## 006 unchecked tasks (T008)

| 006 task | Topic | Start status | Evidence |
|----------|-------|--------------|----------|
| T014 | `apps/web/src/api/dashboard.ts` | remaining | file absent; `apps/web/src/api/` has no dashboard module |
| T074 | live-stack seed loader | remaining | `scripts/live-stack/` absent; `infra/compose.yaml` and `packages/testing/fixtures/dashboard_reference/` exist |
| T017 | indicators vs reference totals on PostgreSQL | unverified | `test_dashboard_indicators.py:51` checks reference totals but on the unit-test engine; PostgreSQL run not confirmed |
| T018 | indicator edge cases | remaining (partly covered) | `test_dashboard_indicators.py:91,96` cover no forecast and empty database; file `test_dashboard_indicator_edges.py` absent; negative stock and estimated cost not covered |
| T019 | BFF indicators degrade alone | unverified | `services/api-bff/tests/test_dashboard_indicators_bff.py:115,121` cover viewer money and downstream failure; "no raw downstream text" not asserted |
| T079 | GET-only and no ERP write | remaining | `test_dashboard_read_only.py` absent |
| T078 | Madrid DST tests | remaining | `test_dashboard_dst.py` absent |
| T034 | unsupported-filter notes and empty state | remaining | no `ignored_filters` in `src/dashboard/*.py` |
| T038 | drill-down Playwright spec | remaining | `dashboard-drilldown.spec.ts` absent |
| T039 | new drill-down kinds | remaining (partly done) | `drilldown.py:24` KINDS lists six kinds only |
| T040 | SKU detail route | remaining | no `/skus` route in `src/api/dashboard.py` |
| T041 | BFF forwarding of new kinds and SKU route | remaining (partly done) | BFF has `/overview`, `/drilldown`, forecast-basis only |
| T042 | drill-down panel by SKU | remaining (partly done) | `ProductDetail.tsx` exists, still keyed by id |
| T043 | drill-down strings | remaining | to add with T031 |
| T044 | series tests | remaining | `test_dashboard_series.py` absent |
| T045 | chart unit tests | remaining | `dashboard-charts.test.tsx` absent |
| T046 | chart Playwright spec | remaining | `dashboard-charts.spec.ts` absent |
| T047 | `series.py` | remaining | file absent |
| T048 | aggregate columns and retention | unverified | `test_dashboard_freshness.py:51,60` show new columns and migration 0007 exist; 25-month retention and range exposure not confirmed |
| T049 | charts route | remaining | no route |
| T050 | chart components | remaining | `charts/` folder absent |
| T051 | compose charts on screen | remaining | depends on T050 |
| T052 | chart strings | remaining | to add with T039 |
| T053 | export content tests | remaining | `test_dashboard_export.py` absent |
| T054 | export BFF tests | remaining | `test_dashboard_export_audit.py` absent |
| T055 | export Playwright spec | remaining | absent |
| T056 | `export.py` | remaining | absent |
| T057 | export routes | remaining | no route |
| T058 | export actions in UI | remaining | absent |
| T059 | export strings | remaining | absent |
| T060 | failure-drill tests | remaining | `test_dashboard_failure_drills.py` absent (partial coverage in `test_dashboard_orchestration.py`, to read when implementing) |
| T061 | local-load test | remaining | `test_dashboard_local_load.py` absent |
| T062 | trust Playwright spec | remaining | `dashboard-trust.spec.ts` absent |
| T076 | newer-data notice | remaining | `useNewerDataNotice.ts` absent |
| T063 | freshness route and excluded count | remaining (partly done) | `freshness.py` has `Freshness` and `inventory_freshness`; no route, no excluded count |
| T064 | banner, origin labels, retry | remaining | not in `DashboardScreen.tsx` |
| T065 | trust strings | remaining | absent |
| T066 | live-stack Playwright project | remaining | `dashboard-live.spec.ts` absent |
| T067 | axe scan of new elements | remaining | `a11y-screens.spec.ts` exists; new elements do not exist yet |
| T068 | 2 s performance record | unverified | `dashboard-perf.spec.ts` and `api-bff/tests/perf` exist; no recorded run |
| T069 | operational signals | remaining | depends on export and refresh code |
| T077 | no literal numbers check | remaining | `dashboard-no-literal-numbers.test.ts` absent |
| T070 | scans and baselines | unverified | run before the PR |
| T071 | cost note | remaining | PR text |
| T072 | quickstart run and keyboard pass | remaining | after build |
| T073 | final audit and PR | remaining | end of feature |
| T097 | full gate runner | remaining | after build |
| T098 | merge check for PR 17 | remaining | check before the PR |

Result: 0 found fully completed, 5 unverified (T017, T019, T048, T068, T070), 43 remaining. The ten indicators and the v2 contracts stay untouched.

## 006 requirements (T009)

| 006 FR | Start status | Tasks that close it |
|--------|--------------|---------------------|
| FR-001 to FR-005 (cards, computed figures, states, EUR, definitions) | completed by PR 19, per-card states partly open | T057 |
| FR-006 to FR-008 (filters, chips, URL, empty state) | partial: hook and server filters exist | T007, T014 to T023 |
| FR-009 to FR-011 (drill-down, SKU detail, paging) | partial: six kinds, offset paging | T024 to T032 |
| FR-012 to FR-014 (five charts, tables, states) | partial: trend and ABC/XYZ only | T033 to T041 |
| FR-015, FR-016 (export, audit, exclusions) | missing | T042 to T049 |
| FR-017 (roles) | partial: helper and indicator hiding tested (`test_dashboard_indicators.py:73`) | T015, T020 |
| FR-018 (local-load labelling) | unverified | T051 |
| FR-019 (excluded records counted and linked) | missing | T056, T057 |
| FR-020 (read-only) | unverified | T053 |
| FR-021 (Spanish catalogue) | partial | T023, T032, T041, T049, T059 |
| FR-022 (UTC plus original) | completed (`test_dashboard_freshness.py:85`) | none |
| FR-023 (cost) | unverified | T067 |
| FR-024 (audit) | completed (`audit/dashboard-audit.md`) | T070 (update in place) |
| FR-025, FR-026 (capital, budget) | completed (`test_dashboard_indicators.py:116`, `test_dashboard_indicators_bff.py:39`) | none |

## Evidence results (filled during Phase 9)

| Check | Result | Notes |
|-------|--------|-------|
| Live-stack journey (T060) | **6 passed** against the real BFF, services and PostgreSQL | `apps/web/tests/live/dashboard.spec.ts`, run with `playwright.live.config.ts`. Stack started from `infra/compose.yaml` plus `compose.live-stack.yaml`; the seed loader worked on a real PostgreSQL (5 variants, 7 lots, 18 aggregate rows). Checked: documented totals (stock value 100,00 EUR, expiring 60,00 EUR), origin, stale banner (the data is dated 2026-11-09), expiry-band and capital-by-group tables, drill-down total 100,00 then a SKU page with its cost, an indicators export by click with the right content, a viewer with no amounts and no export (and a server 403), an unknown SKU. The spec skips itself, with a reason, when the reference data is not loaded (as in the e2e gate's own stack). |
| Performance (T062) | within budget | Browser: first meaningful content 277 to 352 ms with 1,000 alerts, layout shift 0.001; a filter change updating cards and charts 271 to 333 ms (8 runs, services simulated at 150 ms each). Services at 20,000 variants (in-memory database, `test_dashboard_scale.py`): summary 0.26 s, demand 0.15, forecast 0.02, supplier filter 0.33, first drill page 0.15, indicators 0.43, all charts 0.51 (0.97 with a supplier filter), SKU page 0.15, cards export 0.45, one chart export 0.14. Budget 2 s. A whole-stock export of 20,000 products is refused (413), never cut. One earlier run of the filter-change check failed once and did not reproduce in 9 later runs (not explained). |
| Axe scan of the new elements (T061) | pass | `a11y-screens.spec.ts` now scans, in light and dark with contrast: the dashboard with charts, tables, export buttons and the stale banner; the drill-down panel with its export; the SKU page. It found one real defect (list items with `role="note"` on the SKU page), fixed. |
| Keyboard-only pass (T066) | pass | Against the live stack, Tab and Enter only: reach and open a chart's table (50 presses), run the indicators export (101), open a drill-down (2) and a SKU page (5). Observation: the export button is 101 presses in because the side navigation and the filters come first; a skip link or a closer position would help (not changed). |
| Quickstart scenarios (T066) | 1 to 7 run | 1 closure report: complete. 2 filters in the address: `/panel?proveedor=sup-a&categoria=A` restores the view (live); invalid values in mocked specs. 3 drill-down to SKU: live. 4 charts: live plus axe. 5 export: live (keyboard download, content, viewer refused); hostile cells, size limit and audit entries in unit tests. 6 trust: stale banner live; with the inventory service stopped, 14 figures show an error with a retry (14 retry buttons) and no inventory figure shows as zero (the only "0,00 EUR" is procurement's real "Gasto (pedidos confirmados)": the seed has no confirmed orders); the newer-data notice and local-load separation are covered by the fake-clock Playwright spec and unit tests, not live. 7 evidence: this table. |
| Spanish screenshots (T066) | 7 captured | `specs/014-dashboard-analytics-completion/evidence/` (buyer panel, export status, drill-down with total, SKU page, filters in the address, viewer panel, inventory down) and `notas.txt`. Synthetic data only. |
| Defects found by the live run and the scans, fixed in Phase 9 | 4 | The drill-down panel never showed the total the server sends (now "Total: ..."); money kinds `capital`, `expiry_band` and the older `abc_xyz` were shown as bare numbers instead of euros; the SKU page showed the raw code `actual_90d` as the coverage basis; invalid list markup on the SKU page. |
| Gates: contracts, isolation, integration, E2E, security, cost (T068) | **5 pass, e2e blocked by one pre-existing flaky spec** | `python -m gates run` with `MMI_GATES_DATABASE=1` and `MMI_GATES_LIVE_STACK=1`: contracts, isolation, integration, security and cost pass; secret scan clean (287 commits). The e2e gate's pipeline test (passes alone: 2 passed in 54 s) and its live-config step pass. Its mocked Playwright step exits 1 intermittently, only because the gate points it at the real built web app: a spec from MMI-6, `suppliers-terms-journey.spec.ts` "the supplier screen is Spanish only ... (SC-008)", fails 4 times in 12 runs in isolation against that build (it reads the page text at once and expects "2,10 €" before the value has rendered). The spec and the supplier screen are unmodified by this feature. **Blocked, owner: supplier commercial management (MMI-6)**; fix: wait for the text (`toContainText` or `expect.poll`) instead of matching at once. The same suite is 294 passed, 15 skipped, 0 failed against the dev server and in 3 of 4 runs against the real build. Along the way a fragile spec of this feature was fixed (the newer-data test counted polls, which differ between the dev and production builds). Earlier gate attempts also failed while another session was using Docker on the same machine. |
| Cost note (T067) | no new container, job or schedule | The only new file under `infra/` is `compose.live-stack.yaml`, a local-only override that publishes the database on the loopback address; nothing references it from Bicep or workflows. No change to `compose.yaml`, Bicep, workflows or schedules. The one new recurring request is the newer-data check: one small read-only request a minute per open dashboard, to an existing route. The cost gate passes. |

## Final status of every row (T013)

Every 006 task that was unchecked at the start ends **delivered and tested**, or **deferred** with reason, owner and follow-up. Evidence for each is in the findings table below and in the evidence table above.

| 006 tasks | Final status | Where |
|-----------|--------------|-------|
| T014 | delivered, differently | `getDashboardSku`, `getDashboardCharts`, `getDashboardFreshness`, `exportDashboard` and the new drill fields were added to `client.ts` (its request method is private) |
| T074 | delivered | `scripts/live-stack/` (seed loader tested on a real PostgreSQL), `infra/compose.live-stack.yaml` |
| T017 | delivered | documented totals shown on the live stack (100,00 and 60,00 EUR) |
| T018, T019, T060, T061, T079 | delivered | `test_dashboard_indicator_edges.py`, `test_dashboard_failure_drills.py`, `test_dashboard_local_load.py`, `test_dashboard_read_only.py` (both services) |
| T078 | delivered | `test_dashboard_dst.py`; a defect fixed (the dashboard's "today" is now the Madrid date) |
| T034, T022 | delivered | no-match state and invalid-value notice |
| T038 | delivered | `dashboard-drilldown.spec.ts` |
| T039, T041 | delivered except `budget` | **`budget` drill-down deferred**: owner procurement-service with Agent 00; follow-up: a per-line breakdown on `/summary/spend`, then forward it |
| T040, T042, T043 | delivered | SKU route, SKU page, drill-down by SKU with total, strings |
| T044 to T047, T049 to T052 | delivered | six charts, route, components, tests |
| T048 | delivered in part, by decision | retention and history range done; the extra aggregate columns are not written (no chart reads them; capital needs procurement's open orders) |
| `forecast_error` chart | **deferred** | owner forecast-service with Agent 00; follow-up: a series endpoint there, then forward it through `/charts` |
| T053 to T059 | delivered except XLSX | CSV export, audit, buttons, strings. **XLSX deferred**: owner Agent 00 with procurement-service (a shared writer in `packages/`) |
| T062, T063, T064, T065, T076 | delivered | freshness route, banner, per-card retry, newer-data notice, strings |
| T066, T067, T068, T072 | delivered | live journey, axe, performance, quickstart, screenshots |
| T069, T077, T070, T071 | delivered | operational signals, no-literal-numbers check, scans and baselines, cost note |
| T097 | delivered with one block | five gates pass; the e2e gate is blocked by a flaky MMI-6 spec (owner supplier commercial management); see the evidence table |
| T098 | delivered | `main` has not moved and the MMI-6 work (PR 17) is already in this branch; nothing to merge |
| T073 | delivered | audit updated in place (`audit/dashboard-audit.md`, section "Status after feature 014"); the single PR is prepared in T071 of this feature |

Not delivered here and owned elsewhere: the three deferrals above (`budget` drill-down, `forecast_error` chart, XLSX) and the flaky supplier-terms spec. Nothing else from the unchecked list is silent.

## Findings during implementation

| Date | Task | Finding |
|------|------|---------|
| 2026-11-16 | T007 | Decision: invalid filter values are refused by the server with 422 `request_invalid` and ignored with a Spanish notice by the web hook (`useDashboardFilters.ts` `ignored`, notice at `DashboardScreen.tsx:214`, string `dashboard.filter.ignored`). No `ignored_filters` field is added to responses; the contract note in `contracts/dashboard-completion.md` is corrected. |
| 2026-11-16 | T014, T019 | Options come from data and have tests: `test_filter_options.py`, `test_dashboard_distribution_options.py`. |
| 2026-11-16 | T015, T020 | Money hiding is wired for summary, indicators, drill-down and ABC/XYZ (`api/dashboard.py`, `roles.py`); tests in `test_dashboard_roles.py`, `test_dashboard_money_roles.py`, `test_dashboard_indicators.py:73`. |
| 2026-11-16 | T017, T018, T021, T023 | Web hook, unit tests (`dashboard-filters.test.ts`), e2e (`dashboard-filters.spec.ts`) and strings already exist. |
| 2026-11-16 | T022 | Still open: the no-match empty state with a clear action. |
| 2026-11-16 | T024, T028 | Added drill-down kinds `demand`, `forecast`, `capital`, `expiry_band` (tests in `test_dashboard_drill_new_kinds.py`). `capital` lists the stock part only: the open orders belong to procurement and have no SKU rows. `forecast` sum equals the card exactly (the card adds the same rounded daily point for each of the 28 days, so rows can differ by rounding of at most 0.14 units). |
| 2026-11-16 | T028 (`budget`) | **Deferred**: the `budget` drill-down kind. Caps and spend belong to procurement-service and have no per-SKU rows in inventory. Reason: data owner is outside inventory. Owner: procurement-service (feature 013 owner) with Agent 00 for the contract. Follow-up: a `/summary/spend` per-line breakdown, then a `budget` kind that forwards it. The card still opens the spend table that exists today. |
| 2026-11-16 | T025, T029 | Added `GET /dashboard/skus/{sku}` (`dashboard/sku.py`): SKU is the only identifier, 404 `sku_not_found` for none or ambiguous, 422 for a malformed SKU, `cost` key present only for cost roles. Supplier shows the public id only: inventory holds no supplier display name. |
| 2026-11-16 | T005 | Adjusted: `ApiClient.request` is private, so a separate `apps/web/src/api/dashboard.ts` cannot reuse it. `getDashboardSku` and the new drill-down fields were added to `client.ts` as small additive edits, the way the existing dashboard calls are. |
| 2026-11-16 | T026, T030 | BFF forwards the new kinds, `band`, `date_from`, `date_to` and `/api/dashboard/skus/{sku}`; `kind=budget` is refused at the gateway (`test_dashboard_drill_sku_bff.py`). |
| 2026-11-16 | T031, T032 | SKU page `/panel/skus/:sku` (`SkuDetailPage.tsx`), drill-down rows link to it, cards for demand, forecast and capital open their kinds; Spanish strings added (tú register). Tests: `dashboard-sku-page.test.tsx`. Web: 790 unit tests, typecheck and lint pass. |
| 2026-11-16 | T016 (006 T078) | **Defect found and fixed**: the dashboard used the UTC date as "today" while demand rows are keyed by the Madrid business day, so between 00:00 and 01:00 or 02:00 Madrid time the new day's sales fell outside the window, and the same happened around the two clock changes. Added `business_today()` (`kpis.py`), used by every dashboard route, the aggregate refresh default and the gateway's default range. Tests: `test_dashboard_dst.py` (13 cases for 2026-03-29 and 2026-10-25). Not changed (outside the dashboard): `risk/daily.py:30` and `api/routes.py:76` still use the UTC date; owner: inventory-service risk module. |
| 2026-11-16 | T022 (006 T034) | No-match state: `noFilterMatches` (`dashboardModel.ts`) and an `EmptyState` with a "Quitar todos los filtros" action in `DashboardScreen.tsx`; tests in `dashboard-model.test.ts` and `DashboardScreen.test.tsx`. The text notes for filters that a figure cannot follow already existed (`filters_unsupported` on the cards). |
| 2026-11-16 | T003 | Additive schemas `dashboard_sku.v1`, `dashboard_drilldown.v1` (adds the four new kinds that the frozen v2 `DrillPage` cannot carry) and `dashboard_freshness.v1`, with generated Python and TypeScript types, matrix entries (status draft) and baseline copies. **Not added**: a chart schema, because the frozen v2 already defines `ChartSeries` (keys `demand_forecast`, `abc_xyz`, `expiry_bands`, `coverage_buckets`, `capital_by_group`, `forecast_error`, `stock_value_history`; states `ok`, `no_data`, `error`); the plan documents were corrected to that vocabulary, and the freshness states to `ok`, `no_data`, `stale`, `error`. No export-header schema: the header is text inside the CSV. The generator was installed temporarily with `uv run --with` (it is not a repo dependency); the one existing generated file it renamed classes in (`dashboard_indicators_v2_schema.py`) was restored, so v2 is untouched. For Agent 00 review: three new `dto` entries and one `endpoint` entry in `contract-matrix.json`. |
| 2026-11-16 | T004 | `packages/contracts/tests/test_dashboard_completion_schemas.py` (valid and invalid payloads) and checks that the real SKU and drill-down responses of the inventory service validate against the schemas, for a buyer and a viewer. The v1 and v2 pins stay in `test_dashboard_indicators_unchanged.py`. |
| 2026-11-16 | T006 | `scripts/live-stack/seed.py`, `README.md` and `infra/compose.live-stack.yaml`. The seed logic is tested on SQLite (`scripts/tests/test_live_stack_seed.py`: totals 100.00 and 60.00, second run refused, non-local host refused). **Not verified**: starting the compose stack and seeding a real PostgreSQL, because another session was running the Docker pipeline test and the gate runner on this machine at the same time. Run the README steps once to confirm (needed for T060). |
| 2026-11-16 | Gate run (partial evidence for T068) | `python -m gates run` on this branch: contracts, isolation, integration, security and cost pass. `e2e` failed twice, for different reasons that point at the environment: first `npm run e2e` exited 1 after 232 passes, then `infra/tests/test_pipeline_e2e.py` timed out waiting for the database to fill. A standalone `npm run e2e` passed (269 passed, 15 skipped) and the pipeline test needs the Docker stack, which another session was building at the same time on the same machine. To re-run alone before the PR. |
| 2026-11-17 | T033, T036, T038 (006 T044, T047, T049) | `dashboard/series.py` and `GET /dashboard/charts` (gateway `GET /api/dashboard/charts`, matrix entry added, status draft). Six charts in the frozen v2 `ChartSeries` shape: `demand_forecast`, `abc_xyz`, `expiry_bands`, `coverage_buckets`, `capital_by_group`, `stock_value_history`; each adds up to a card (expiry bands to the expiring value 60.00, capital by group to the stock value 100.00). A chart with no data is `no_data` with `summary_params.reason`; a failing chart is `error` alone; a role without cost access gets no money column and no value history. Tests: `test_dashboard_series.py` (16) and two gateway tests. |
| 2026-11-17 | T037 (006 T048) | Done in part: 25-month retention (`HISTORY_DAYS = 760`, deleted when a day is stored) and the available history range returned with `stock_value_history`. **Not done, by decision**: writing `capital_tied_up`, `demand_units` and `forecast_units` into `agg_daily_kpis`. No chart reads them (the demand and forecast chart is live from the demand rows and the forecast), and the capital figure needs procurement's open orders, which inventory cannot write. Owner for a future capital history: procurement-service with Agent 00. |
| 2026-11-17 | `forecast_error` chart | **Deferred**: the accuracy history belongs to forecast-service (`/accuracy`, additive `history` parameter approved in 006) and inventory cannot serve it. The gateway would have to merge it from forecast-service, and the gateway does no domain logic. Owner: forecast-service with Agent 00; follow-up: a series endpoint in forecast-service, then forwarding through the charts route. Five other charts plus the existing trend and ABC/XYZ cover the "five or more" criterion. |
| 2026-11-17 | T034, T035, T039, T040, T041 (006 T045, T046, T050, T051, T052) | `charts/AnalyticChart.tsx` and `charts/ChartsSection.tsx` on `DashboardScreen.tsx` after the ABC/XYZ chart: expiry bands, coverage buckets, capital by group and stock-value history, each with a title, a text summary, a table with the same rows (keyboard toggle), no-data reasons, an error with retry, the history range, and click-to-drill from an expiry band. The existing trend and ABC/XYZ charts stay. With them the screen shows six charts. Unit tests `dashboard-charts.test.tsx` (9); Playwright `dashboard-charts.spec.ts` (7, with an axe scan for serious violations); the shared mock now answers the charts route. Web: 803 unit tests; Playwright: 276 passed, 15 skipped. Titles are looked up by chart key so the unused-key baseline did not grow. |
| 2026-11-17 | T042, T045 (006 T053, T056) | `dashboard/export.py` and `GET /dashboard/export`: three views (indicators, one chart, the products behind a figure) as CSV with a header block (report, filters, period, freshness, generated in UTC and Madrid), a total row where the screen has one, UTF-8 with BOM, semicolon, decimal comma. The rows come from `build_indicators`, `build_charts` and `drilldown`, so they equal the screen; the row type is SKU, name and figures only. Text cells that start with `=`, `+`, `-`, `@`, tab or carriage return get an apostrophe; numeric cells are never altered. Above 5000 rows the request is refused with 413 `export_too_large`. Tests: `test_dashboard_export.py` (15). The indicators file lists the six indicators inventory computes and names the four that are outside it (capital, budget, WAPE, bias) in the header, instead of showing an error for them. The role check is explicit (`can_see_money`), because the shared role dependency requires all listed roles, not any of them. |
| 2026-11-17 | T046 | **Decision: XLSX is not offered.** The only writer is in procurement-service (`openpyxl`); using it from inventory would cross a service boundary or add a dependency to a second service. A request for `format=xlsx` is refused with 400 `format_unsupported` and audited. Owner for a future XLSX: Agent 00 with procurement-service (a shared writer in `packages/`). The web app offers CSV only. |
| 2026-11-17 | T043, T047 (006 T054, T057) | Gateway `GET /api/dashboard/export` (matrix entry added, status draft): buyer, approver and admin; a viewer is refused by the role check, which writes an `access.refused` entry. Each allowed export writes `dashboard.exported`, each size or format refusal writes `dashboard.export.refused`, in the hash-chained log with who, view, filters and row count, never row content (`test_dashboard_export_audit.py`, 7). A downstream failure shows no downstream text (502). |
| 2026-11-17 | T044, T048, T049 (006 T055, T058, T059) | `ExportButton.tsx`: "Exportar indicadores" above the cards, "Exportar a CSV" under each chart (named after the chart for a screen reader), "Exportar productos" in the drill-down panel with the chosen sort; a status message says preparing, done with the row count, or the reason (no permission, too large, CSV only). Only roles that may see costs are offered the buttons (`userRoles` now reaches the screen). Tests: `dashboard-export.test.tsx` (7) and `dashboard-export.spec.ts` (5). Web: 810 unit tests; Playwright: 281 passed, 15 skipped on the clean run. One earlier full run had 2 failures (admin and supplier specs) that did not repeat on re-run; most likely load from another session's Docker run on the same machine; not investigated further. |
| 2026-11-17 | T051, T052 (006 T061, T018) | **Behaviour added**: local-load data is never added to ERP data (006 FR-018). `data_origin()` and `variant_scope()` in `kpis.py` use the surrogate-id range from 9,000,000 (`LOCAL_ID_BASE`, the loader's `SURROGATE_BASE`): with both kinds in one database every figure, drill-down, chart and export covers the ERP products only and the local ones are counted; with only local data the figures are those and every card says "Origen: carga local". The freshness source origin follows it. This closes audit A25's gap for the dashboard. Tests: `test_dashboard_local_load.py` (6) and `test_dashboard_indicator_edges.py` (7: zero and negative stock, no demand, estimated cost, lot without cost, censored days, warehouse without sales, filter matching nothing). |
| 2026-11-17 | T056 (006 T063) | `GET /dashboard/freshness` (gateway `GET /api/dashboard/freshness`, matrix entry added, status draft) returns `dashboard_freshness.v1`: each source with its refresh time, original timestamp, origin and state, the count of malformed or ambiguous movements held back for review, the count of local-load products left out, and the review-list path `/calidad`. The schema gained the required `local_load_excluded`; baseline and generated types refreshed (the generator's rename noise in the v2 file was restored). A failing source is a 502 `downstream_unavailable` with no downstream text. |
| 2026-11-17 | T050, T053 (006 T060, T079) | `test_dashboard_failure_drills.py` (21 cases: each of five cards failing three ways, inventory down, stale and empty passed through, no zero for empty or failed) and read-only guards in both services (`test_dashboard_read_only.py`: GET only on every dashboard route, a write verb refused, the route source names no ERP or purchasing write, and reading every view changes no row). |
| 2026-11-17 | T054, T055, T057, T058, T059 (006 T076, T062, T064, T065) | `TrustBanner.tsx` (prominent alert with the last refresh when a source is stale; the excluded count with a link to the review list; the local-load count; the newer-data notice), `useNewerDataNotice.ts` (one read a minute, `NEWER_DATA_POLL_MS`; the figures change only when the user accepts) and a retry on every failed card. Tests: `dashboard-newer-data.test.tsx` (7) and `dashboard-trust.spec.ts` (5, with a fake clock). Per-card age and origin already existed. **Fixed along the way**: the history chart title "Evolución del valor del stock" contained the card title "Valor del stock" and made an older spec's locator ambiguous; renamed "Evolución del inventario valorado". Totals now: inventory 369 passed, gateway 366, contracts 290, web 817, Playwright 286 passed and 15 skipped. |
| 2026-11-17 | T027 (006 T038) | `dashboard-drilldown.spec.ts` (4): a card opens its products by SKU with the total of every row and no internal id, sorting by SKU descending asks the server for the whole list in that order, paging asks for the next 50, and Escape closes the panel while a product page opens by keyboard and survives a reload. |
| 2026-11-17 | Phase 11 (`/speckit-converge`) | Convergence found 11 gaps (T072 to T082). Done here: T079, T081, T076, T077, and T075 in part. Not done: T072 to T074 (cross-service, Agent 00), T078 (needs the go-ahead to push), T080 (a refactor across features, scope written on the task), T082 (a spec owned by MMI-6). |
| 2026-11-17 | T081 | `businessday.py` is the one source of the Madrid business date; the dashboard, the risk evaluation, the variant history and the censoring-rule default use it, and a test fails if any inventory source asks for `datetime.now(UTC).date()` again. |
| 2026-11-17 | T079 | Tests for a single data point and a 730-day series on both sides (`test_dashboard_series.py`, `dashboard-charts.test.tsx`); no defect found. |
| 2026-11-17 | T075 (part) | The indicators export now has a capital tied up row when procurement's open orders are passed (the gateway forwards the amount as text, inventory sums it); budget, WAPE and bias stay outside the file and are named in the header. |
| 2026-11-17 | T077 | The screen sends the refresh time its data had (`loaded_at`); when newer data exists the export header adds "Aviso: El archivo contiene datos más recientes que los que se veían en pantalla al exportar". The file always holds the latest data. |
| 2026-11-17 | T076 | When the server refuses an export for the role (403), the screen drops the export buttons, closes any open drill-down, reloads the cards and charts without cost figures and says so in an alert; the same happens when the cards come back hidden by role. Playwright spec added. A first version removed the buttons together with their only explanation; the screen-level alert fixes it. |
| 2026-11-17 | Phase 12 (second `/speckit-converge`) | Four gaps no task covered: T083 to T086, all closed. |
| 2026-11-17 | T084 | The inventory suite on a real PostgreSQL (compose database, `MMI_TEST_DATABASE_URL`, as CI does): the 91 tests of this feature, then the whole suite, 381 passed and 1 skipped; the gateway suite 369 passed. **No SQL difference between SQLite and PostgreSQL showed up.** |
| 2026-11-17 | T083 | `dashboard_charts.v1` defines the response of `GET /api/dashboard/charts` (the list around the frozen v2 `ChartSeries`; its key and state vocabularies are tested equal to v2's). Registered in `contract-matrix.json` as `draft`, baseline and generated types refreshed, and the real response, for a buyer and a viewer, is validated against it. One of my own test cases assumed `format: "date"` is enforced; it is only an annotation without a format checker, so I used a case the schema does enforce. |
| 2026-11-17 | T085 | A well-formed filter value that is not among the current options (a supplier, category, family or warehouse that no longer exists) is dropped from the address with the existing "filtros no válidos" notice, and the figures are asked for again without it. Nothing is dropped when the option list failed to load. This also corrected an older test of mine that used a supplier id its own mock did not contain. |
| 2026-11-17 | T086 | `contracts/dashboard-completion.md` rewritten from what shipped (422 and 404 codes, `keys`, `loaded_at`, `open_orders`, `local_load_excluded`, the charts schema, XLSX refused, the Madrid date, the `variant_id` note); `data-model.md` and `plan.md` aligned (`dashboard.ts` was never created). |
| 2026-11-17 | Phase 13 (clarification, then `/speckit-plan`, `/speckit-tasks`, `/speckit-implement`) | FR-008a: the browser and gateway use the SKU only. T087 to T098 done and T080 delivered: the gateway walk test, the web scan, `dashboard_drilldown.v2`, SKU routes in inventory (`/skus/{sku}`, `/skus/{sku}/variant`), `sku` next to the id in procurement rows (`sku_labels.py`) and in inventory risk and review rows, SKU-keyed gateway routes (forecast basis, product page, supplier terms, lot costs, cost updates), and every screen. The gateway strips `variant_id` from every JSON answer; services and events keep it. |
| 2026-11-19 | Agent 00 review of PR 32 | Accepted, no blocking points. Done: `dashboard_drilldown.v1` now lists only `api-bff` as consumer (the browser reads v2) and `contract-matrix.md` is regenerated. Cost of the scrub middleware, asked for by Agent 00 (answers are buffered and parsed once, measured on this machine with synthetic pages): a 200-row drill-down page (25 KB) 0.3 ms, the largest allowed page of 5,000 rows is not served as JSON (the drill-down page is capped at 200 rows; the export is CSV and passes through untouched), six 730-row charts (150 KB) 2.8 ms; even a 633 KB JSON takes 9.4 ms. Negligible against the 2 s budget. |
| 2026-11-19 | Before real data (Agent 00) | **Not done here, needs a person with the real SKU list:** with the local-only loader, check the real SKUs for characters outside the pattern (1 to 60 characters; letters, digits, `.`, `_`, `-`; starting with a letter or digit). A product whose SKU is refused is unreachable at the browser. Real data stays out of this repository (project rule 1). |
| 2026-11-19 | T074, T072, T073 (Agent 00) | T074 (XLSX) stays deferred until a second feature needs XLSX; no shared writer for one consumer. T072 (`budget` drill-down) and T073 (`forecast_error` chart) are requests for procurement-service and forecast-service, each with its schema first; the Jira tasks for those owners are still to be opened (Agent 00 registers the matrix entries when the schemas exist). T075: budget, WAPE and bias may be passed to the gateway as plain amounts as long as it only forwards them (ADR-023). |
