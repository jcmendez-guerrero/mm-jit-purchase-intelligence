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


## R12 - Where the browser still sees `variant_id` (FR-008a)

Decision: the starting list, from a search of the web app and the gateway, is: drill-down rows (`dashboard_drilldown.v1`), the product overlay (`/dashboard/variants/{id}/forecast-basis`, `/inventory/variants/{id}`), supplier terms (`/product-suppliers/{variant_id}/{supplier}/terms`), costs (lot costs, opening and corrected cost bodies), the quality and admin status screens (shown as "variante N"), proposal review notes, scenario lines and changes (shown as `#id`), and the matching generated types. Policies already strip it (`_without_variant_ids`). The implement step re-runs the search and ticks each one.

Rationale: the user wants humans and the browser on the SKU only; showing `#id` or "variante N" breaks AGENTS rule 5.

Alternatives considered: only the dashboard (rejected by the clarification, option A); an optional `variant_id` field kept for machine clients on the gateway (rejected, option C).

## R13 - Who resolves SKU to id

Decision (as built): the catalogue owner resolves it. Inventory-service answers `GET /skus/{sku}/variant` (internal id and product id) and `GET /skus/{sku}` (the product page without any internal id); the gateway asks it once per request for the routes whose services still work by id (supplier terms, lot costs, cost updates, forecast basis) and forwards nothing else, with no cache and no arithmetic. The services keep their machine routes by `variant_id`; where a row names a product they add `sku` next to it (`procurement-service/src/sku_labels.py`, inventory risk and review rows), and the gateway removes the key `variant_id` from every JSON answer (`api-bff/src/scrub.py`, a transport filter). Unknown SKU is 404 `sku_not_found`; a SKU that matches more than one variant is 409 `sku_ambiguous`, never guessed. Local-load surrogate ids (from 9,000,000) resolve like any other but stay refused for Siweb requests (pending link).

Rationale: keeps the gateway free of business logic (ADR-023) and avoids a second catalogue copy.

Alternatives considered: a SKU-to-id table in the gateway (rejected: business data and staleness); one new "resolve" service (rejected: new always-on resource); SKU-keyed routes in every service (rejected for now: about 290 uses of the id inside procurement and forecast, and machine-to-machine callers need the id).

## R14 - What keeps `variant_id`

Decision: events, queues, service-to-service routes, the cost writer, the connector and the database keep `variant_id`; so do the service-level contracts a machine consumes. Only payloads, paths, query strings and page addresses that the browser sees change. Because nothing is in production, the old gateway routes are removed in the same change, not deprecated.

Rationale: matches the clarification (machine-to-machine may need the id).
