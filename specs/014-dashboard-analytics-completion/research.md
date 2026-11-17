# Research: Dashboard & Analytics Completion

No `NEEDS CLARIFICATION` remained in the spec. This file records the starting evidence and the decisions the plan relies on. The 006 research (`specs/006-executive-dashboard-analytics/research.md`) and audit (`audit/dashboard-audit.md`) stay valid and are not repeated.

## R1 - Starting evidence on this branch

Checked with a file listing and route search on 2026-11-16 (the verification task repeats it per task, with line evidence).

| Area | Present | Absent |
|------|---------|--------|
| Inventory service dashboard code | `kpis.py`, `filters.py`, `drilldown.py`, `freshness.py`, `indicators.py`, `roles.py`, `forecast_source.py` | `series.py`, `export.py` |
| Inventory routes (`src/api/dashboard.py`) | `/filters/options`, `/summary`, `/indicators`, `/demand-trend`, `/drilldown`, `/abc-xyz` | charts, export, freshness, SKU detail |
| BFF routes (`src/routes/dashboard.py`) | `/overview`, `/drilldown`, `/variants/{variant_id}/forecast-basis` | charts, export, freshness, SKU detail, options |
| Web | `DashboardScreen.tsx`, `ChartWithTable.tsx`, `dashboardModel.ts`, `useDashboardFilters.ts`; specs for filters, perf, roles | `api/dashboard.ts`, `charts/`, SKU page, export actions |
| Evidence tooling | perf spec | `scripts/live-stack/`, live Playwright project |
| Inventory tests | filters, freshness, indicators, drill reconcile, roles, supplier filter, reference dataset | series, export, DST, edges, local-load |

Decision: treat 006 tasks T014, T017-T019, T034, T038-T079 (the unchecked list) as the work list, but classify each by reading code and tests, not by this table alone. Some freshness and filter parts exist (tests present) and may already satisfy tasks.

Alternatives considered: trust the unchecked boxes as-is (rejected: risks rebuilding finished code, against spec FR-001).

## R2 - Task counts

Jira says 43 of 97 tasks delivered. 006 `tasks.md` shows 55 checked and 48 unchecked (103), because tasks were added later (T074-T079, T097, T098). Decision: the closure report uses the file as the count of record and states the Jira number as history.

## R3 - URL-persisted filters

Decision: `useDashboardFilters.ts` already exists (006). Verify it covers date range, supplier, category, warehouse and family, ignores invalid values with a visible notice, and restores on reload and shared link. Extend only if a gap shows. Validation of values stays in `filters.py` (server) and the hook (client); the server is the authority.

Rationale: reuses code; the notice requirement (spec US2.3) is the likely gap.

## R4 - Role boundaries

Decision: cost and capital figures are removed server-side for roles without cost access (`roles.py` helper exists; wiring was planned in 006 T023). A link asking for them from a viewer returns the data without those fields, never a client-side hide. Tests assert absence in the response body.

## R5 - Chart series and history

Decision: series are computed in inventory-service from `agg_daily_kpis` and live tables, reusing `ChartWithTable.tsx` and the colour hook; the available history range is returned so the UI states it (spec US4.5). Forecast accuracy comes from forecast-service through the existing approved additive endpoint; where history is too short the response carries a reason code, and the UI shows the Spanish note.

Alternatives considered: precompute everything in the refresh job (rejected for chart kinds that depend on filters, except the daily columns that already are).

## R6 - Export format and safety

Decision: CSV is the baseline (semicolon, decimal comma, BOM, filter header). XLSX reuses the writer already used by proposal export; if it cannot be shared without crossing service boundaries, XLSX is documented as a follow-up (acceptance criterion 1 allows this). Formula neutralisation prefixes any cell starting with `=`, `+`, `-`, `@`, tab or carriage return, except real numeric columns, which are written as numbers. Size limit enforced before building the file (`413 export_too_large`). Rows come from the same query code as the screen so totals match.

## R7 - Freshness and newer-data notice

Decision: one freshness route returns, per source, last refresh (UTC plus original string), origin (`erp_sync` or `local_load`), state (fresh, stale, failed, empty) and the count of excluded records. The web app polls it at a low rate (document the interval in the task) and shows a notice; values change only on user acceptance. No push channel, so no new always-on resource.

## R8 - SKU detail route

Decision: `/dashboard/skus/{sku}` in inventory-service, forwarded by the BFF with SKU format validation only. The SKU is resolved to the internal id inside inventory-service; the id never appears in the response. Cost fields are omitted for non-cost roles (R4). Unknown SKU returns the standard not-found error with no data from other products.

## R9 - Gates and live stack

Decision: seed loader in `scripts/live-stack/` brings up `infra/compose.yaml` with `packages/testing/fixtures/dashboard_reference/`; no Azure credentials. The gate runner is executed from `scripts/` with `MMI_GATES_DATABASE=1` and, where Docker exists, `MMI_GATES_LIVE_STACK=1`. Failures are fixed or recorded as blocked with an owner; changes to gate configuration go through Agent 00 (MMI-2).

## R10 - Performance and cost evidence

Decision: reuse `apps/web/tests/e2e/dashboard-perf.spec.ts` and `services/api-bff/tests/perf`; record numbers in the closure report. Cost note: no new container, job or schedule; recorded in the PR cost section.

## R11 - Merge risk with PR 17

Decision: shared files (`apps/web/src/api/client.ts`, `apps/web/src/i18n/es-ES.json`) are touched additively; if PR 17 lands first, merge `main` again before the PR and resolve conflicts (006 T098).
