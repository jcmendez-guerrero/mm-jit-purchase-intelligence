## What and why

Completes feature 006 (Executive Dashboard & Analytics) after the first delivery in [PR 19](https://github.com/jcmendez-guerrero/mm-jit-purchase-intelligence/pull/19). Jira: [MMI-11](https://mundomascotix.atlassian.net/browse/MMI-11) (Agent 01B), continuing [MMI-3](https://mundomascotix.atlassian.net/browse/MMI-3), epic [MMI-1](https://mundomascotix.atlassian.net/browse/MMI-1); coordination with Agent 00 in [MMI-2](https://mundomascotix.atlassian.net/browse/MMI-2). Spec folder: `specs/014-dashboard-analytics-completion/` (the original is 006, which stays the spec of record).

Verify-then-close-gaps: the 48 unchecked 006 tasks were classified against the code first (none was already finished); every one now ends delivered and tested or deferred with a reason and an owner. The ten indicators and the v1 and v2 schemas are unchanged (hash-pinned by a test). The dashboard stays read-only: no ERP request, no purchasing write (tests prove it in both services).

**Delivered**

- **Filters and sharing:** filters in the address (already there), invalid values ignored with a notice, a no-match state with one action to clear.
- **Drill-down and SKU page:** new kinds `demand`, `forecast`, `capital`, `expiry_band`; every drill-down shows the total of all its rows and amounts in euros; `GET /dashboard/skus/{sku}` and a page at `/panel/skus/:sku` (SKU only, cost only for cost roles, reloadable and shareable).
- **Charts:** six filter-aware charts in the frozen v2 `ChartSeries` shape (demand and forecast, ABC/XYZ, expiry bands, coverage buckets, capital by group, stock-value history), each with a table with the same rows, no-data reasons, an error with retry, click to drill from an expiry band; 25 months of daily history kept.
- **Export:** indicators (with capital tied up), one chart, or the products behind a figure as CSV (UTF-8 with BOM, semicolon, decimal comma, a header block with filters, period, freshness and generation time); formula-safe text cells; refused above 5,000 rows, never cut; buyer, approver and admin only; every attempt audited without row content.
- **Trust:** `GET /dashboard/freshness`; a prominent alert when data is stale; the count of records left out linked to the review list; a retry on every failed card; a newer-data notice that never changes the figures by itself.
- **Local-load data is never added to ERP figures (FR-018):** surrogate ids from 9,000,000 up are excluded from every figure when ERP data exists and counted; with only local data the cards say "Origen: carga local". **This changes what the dashboard shows when a database holds both kinds.**
- **Evidence:** a live-stack spec against the real BFF, services and PostgreSQL (6 passed), performance, axe scans, keyboard-only pass, failure drill, Spanish screenshots, operational signals, a no-literal-numbers check.

- **Role loses cost access while the screen is open:** the server refuses, and the screen drops the export buttons, closes any open drill-down, reloads without cost figures and says why. An export file also says when newer data exists than the screen was showing.

**Defects found and fixed on the way**

- The dashboard's "today" was the UTC date while demand is keyed by the Madrid day: the first hours of each Madrid day, and the two clock-change days, read as the day before. Now the Madrid date everywhere on the dashboard and in the gateway's default range. (`risk/daily.py` and `api/routes.py` still use the UTC date: outside the dashboard, noted for the inventory risk owner.)
- The drill-down panel never showed its total and showed `capital`, `expiry_band` and `abc_xyz` amounts as bare numbers.
- The SKU page showed a raw internal code and had invalid list markup (found by the axe scan).

- **Convergence (Phase 11):** the spec was re-checked against the code and 11 gaps were recorded as T072 to T082. Closed here: the Madrid business date everywhere in the inventory service, chart edge-case tests, capital tied up in the indicators export, the newer-data note and the role-loss handling. Left open and named: the three deferrals below, opening the PR, a SKU-keyed refactor to drop `variant_id` from drill-down rows (a change across several features), and the flaky MMI-6 spec.

**Deferred (reason, owner, follow-up in the closure report)**

- `budget` drill-down: caps and spend belong to procurement-service (owner: procurement-service with Agent 00).
- `forecast_error` chart: the accuracy history belongs to forecast-service (owner: forecast-service with Agent 00).
- XLSX export: the only writer is in procurement-service (owner: Agent 00 with procurement-service). A request for it is refused with 400 `format_unsupported` and audited.

Full record: [closure-report.md](closure-report.md). Screenshots (synthetic data, Spanish): [evidence/](evidence/).

## Test results

- Inventory service 380 passed, 2 skipped; gateway 368 passed, 1 skipped; contracts 290 passed, 5 skipped; seed loader 4 passed.
- Web: 825 unit tests, typecheck and lint clean; Playwright 295 passed, 15 skipped against the dev server; live config 4 journey specs passed and the 6 dashboard specs passed on a seeded stack (they skip with a reason when the reference data is not loaded).
- Performance, 20,000 variants: slowest new operation 0.97 s (budget 2 s); browser first meaningful content about 0.3 s, filter change about 0.3 s.
- Gates (`python -m gates run`, database and live-stack modes): contracts, isolation, integration, security and cost pass; secret scan clean. **The e2e gate is blocked**: its mocked Playwright step is intermittently red only when pointed at the real built web app, because of a spec from MMI-6 (`suppliers-terms-journey.spec.ts`, "Spanish only", 4 failures in 12 isolated runs; the spec is untouched by this change). The pipeline test passes alone (2 passed in 54 s) and the live-config step passes. Owner: supplier commercial management.

## Checklist

**Data**

- [X] No real exports, raw API responses, SKUs, suppliers, prices, names or e-mails; fixtures, screenshots and the seed loader are synthetic
- [X] Fields not needed are discarded before storage: no change; exports and the SKU page carry no notes, tax ids or internal ids

**Security**

- [X] No secrets, tenant/subscription/app IDs or real `.bicepparam`/`.tfvars` values (secret scan clean)
- [X] Siweb access unchanged: no ERP request from any dashboard route; GET-only and no-write tests in both services
- [X] Authorisation rules unchanged or tested: money removed server-side for roles without cost access, exports for cost roles only and audited, a viewer refused

**Cost**

- [X] No new always-on resource, container, job or schedule. The only new file under `infra/` is a local-only compose override that publishes the database on the loopback address; nothing in Bicep or workflows references it. The one new recurring request is the newer-data check: one small read-only request a minute per open dashboard to an existing route.

**Contracts**

- [X] JSON Schemas first: `dashboard_sku.v1`, `dashboard_drilldown.v1`, `dashboard_freshness.v1` added (the v1 summary and v2 indicators are unchanged, hash-pinned); baseline, generated types and contract tests updated
- [ ] **Agent 00 review needed:** `contract-matrix.json` gained 3 `dto` entries and 4 `endpoint` entries (`/api/dashboard/` skus, charts, export, freshness; all status `draft`)
- [X] No breaking change

**Quality**

- [X] Tests added or updated, including failure, duplicate and hostile-input cases
- [X] User-facing text is in Spanish via translation keys (informal register kept)
- [X] Constitution checked
- [ ] **Full gate run green:** blocked on the e2e step described above
