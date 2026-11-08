# Research: Executive Dashboard & Analytics

Audit baseline: worktree of `main` at the start of this feature. Evidence is by file; the audit task re-verifies line numbers before implementation (FR-024).

## Part 1 - Audit of the current dashboard

Status values: **complete**, **partial**, **broken**, **missing**, **unverified**.

| # | Capability | Status | Evidence | Note |
|---|------------|--------|----------|------|
| A1 | Stock value card with basis, estimated and unvalued counts | complete | `apps/web/src/features/dashboard/DashboardScreen.tsx` (value card); `services/inventory-service/src/dashboard/kpis.py` `compute_summary`, `valued_lots` | Reuse |
| A2 | Coverage card (days) with basis and "no demand" count | complete | `DashboardScreen.tsx` coverage card; `kpis.py` `coverage_by_variant` | Reuse |
| A3 | Expiring value and expiry count | partial | `DashboardScreen.tsx` expiring card; `kpis.py` | One bucket only; no time bands |
| A4 | Stockout severity ruler with drill-down | complete | `ui/SeverityRuler`, `stockoutSeverityCounts` in `dashboardModel.ts` | Reuse |
| A5 | Purchasing spend card (latest proposal, budget, over-budget, by supplier) | partial | `DashboardScreen.tsx` spend card; BFF call to procurement `GET /summary/spend` | Shows only when a proposal exists; no period budget view |
| A6 | Demand card | missing | no card; trend chart only | |
| A7 | Forecast card | missing | forecast only inside trend chart | |
| A8 | Capital tied up | missing | no definition anywhere | See R3 |
| A9 | WAPE and bias | partial | accuracy table in `DashboardScreen.tsx` (forecast-service `GET /accuracy`) | Table, not a card or a chart over time |
| A10 | Demand trend plus forecast chart with table view | complete | `ChartWithTable.tsx`; `kpis.py` `demand_trend`, `forecast_series` | Reuse |
| A11 | ABC/XYZ chart with table view | partial | `abc_xyz_distribution(conn)` takes no filters | Ignores every filter |
| A12 | Filters: warehouse, category (A/B/C/critical), family, supplier, days | partial | `services/api-bff/src/routes/dashboard.py` `overview` | See A14 |
| A13 | Date range filter | missing | only a "last N days" selector (7-365) | |
| A14 | Filters apply to all figures | broken | risks get warehouse only; ABC/XYZ and accuracy get none; supplier filter affects only spend; warehouse is shown as "informational" for some cards | Contradicts the spec |
| A15 | Filters in the link | partial | only `?almacen=` is bound to the address | |
| A16 | Per-card refresh time and origin | partial | single freshness line from `summary.day`; stale threshold constant `STALE_AFTER_DAYS = 2` in `dashboardModel.ts` | |
| A17 | Drill-down by figure | partial | `DrillDownPanel.tsx`; `services/inventory-service/src/dashboard/drilldown.py` kinds: inventory_value, coverage, stockout_risk, expiry_risk, abc_xyz, trend_day | `limit` 1-200 with a `truncated` flag, no pagination |
| A18 | Drill-down identifies product by SKU | broken | `DrillDownPanel.tsx` shows `#${variant_id}` first; risk table in `DashboardScreen.tsx` shows `#${variant_id}` | Violates repository rule 5 |
| A19 | SKU detail | complete | `ProductDetail.tsx` | Expiry-lot content unverified |
| A20 | Supplier panel | complete | `SupplierPanel.tsx` | Reuse |
| A21 | Charts have a table alternative and text summary | complete | `ChartWithTable.tsx` | Reuse for all new charts |
| A22 | At least five API-backed charts | missing | two charts today (trend, ABC/XYZ) | |
| A23 | Export | missing | no export in dashboard code | |
| A24 | Role-based hiding of cost figures | unverified | BFF `READ = viewer, buyer, approver, admin` for all dashboard routes | Check whether viewer receives money values |
| A25 | Local-load data labelled, not mixed with ERP data | unverified | | Check origin flag in inventory |
| A26 | Count of quarantined records on the dashboard | missing | | |
| A27 | Playwright tests are API-backed | broken (for the criterion) | `apps/web/tests/e2e/dashboard.spec.ts` uses `dashboard-mock.ts` route mocks | Good for states; does not prove API-backed |
| A28 | Performance test | unverified | `dashboard-perf.spec.ts`, `services/api-bff/tests/perf` exist | Re-run on the reference dataset |
| A29 | Accessibility scans | complete | `a11y*.spec.ts` | Extend to new elements |
| A30 | Spanish only, no hard-coded strings | partial | baseline `hardcoded-strings.baseline.json` exists | Keep the baseline from growing |

## Part 2 - Decisions

### R1 Where the figures are computed
- **Decision**: in inventory-service (`src/dashboard`), extending `compute_summary` and the aggregate refresh. The BFF forwards filters and combines card-level results; the web app only formats.
- **Rationale**: matches the existing split and the rule that the BFF holds no business rule; reuses valued lots, demand and forecast access.
- **Alternatives**: compute in the BFF (rejected: business rules in the BFF); a new analytics service (rejected: cost and an always-on component).

### R2 One filter model for every figure
- **Decision**: one `FilterSet` (date_from, date_to, warehouse_id, supplier_id, category, family) accepted by every dashboard route and by export. Where a source cannot honour a filter (for example accuracy by supplier), the card says so in text and is excluded from that filter's reconciliation; it never ignores the filter silently.
- **Rationale**: audit A14.
- **Alternatives**: per-card filters (rejected: confusing and inconsistent).

### R3 Definitions of the new indicators
- **Decision**:
  - *Demand*: units sold (real ERP sales, uncensored) in the period, with daily average; local-load data labelled separately.
  - *Forecast*: forecast units for the next 28 days for forecast-eligible variants, with the upper band; variants without forecast counted in an "incomplete" bucket.
  - *Capital tied up*: stock value at lot acquisition cost plus the value of confirmed supplier orders not yet received. **Assumption to confirm with the owner** (stock value alone is already card A1).
  - *Purchasing budget*: budget for the period (budget cap) against proposed and confirmed spend.
  - *WAPE and bias*: existing forecast-service definitions, shown as cards with a time series.
- **Rationale**: the spec asks for each; definitions are stored with the indicator (FR-005).
- **Alternatives**: capital equal to stock value (rejected: duplicate card).

### R4 Supplier filter on stock figures
- **Decision**: inventory-service keeps a `supplier_variant_link` read-model populated from procurement events (supplier link and terms changed). The supplier filter joins this table inside the inventory schema.
- **Rationale**: no cross-schema SQL; no business logic in the BFF; bounded query size.
- **Alternatives**: BFF fetches the supplier's variant ids and passes them (rejected); procurement computes stock figures (rejected: it does not own stock).
- **To verify** in the first task: which existing event carries supplier links and whether it includes the current set or only deltas.

### R5 Freshness, origin and staleness
- **Decision**: each source (inventory snapshot, movements, forecast, accuracy, budget/spend) reports `refreshed_at` (UTC, with the original string), origin (`erp_sync`, `local_load`, `forecast`, `proposal`) and a state (`ok`, `no_data`, `stale`, `error`). The stale threshold comes from the server (single source), replacing the constant in the web app. Figures from local load carry the local label and are never summed with ERP-origin data.
- **Rationale**: FR-003, FR-018, audit A16, A25.
- **Alternatives**: keep the client-side threshold (rejected: two sources of truth).

### R6 History for "over time" charts
- **Decision**: a daily `dashboard_snapshot` table (one row per day and warehouse/category slice) written by the existing aggregate refresh. The chart shows data from the first snapshot onward and says so; it does not back-fill invented history.
- **Rationale**: no fabricated data; past costs stay reproducible. **Risk**: stock value over time is short at first. Mitigation: the chart states the available range; the "five charts" gate is met without it (R7).
- **Alternatives**: rebuild history from movements (rejected: past costs not reproducible); reuse the existing inventory snapshot event if it already stores values (to verify in the first task).

### R7 Visualizations (at least five, each with a table view)
1. Demand trend with forecast and band (exists).
2. ABC/XYZ distribution (exists, made filter-aware).
3. Expiry exposure by time band (new).
4. Coverage distribution in buckets (new).
5. Capital tied up by category and by supplier (new).
6. Forecast error (WAPE) and bias over time (new, from accuracy history).
7. Stock value over time (new, depends on R6).

Charts 1-6 satisfy the "five or more" gate; chart 7 is added when snapshots exist. All reuse `ChartWithTable` and the chart colour hook.

### R8 Drill-down
- **Decision**: keep the six existing kinds; add kinds for demand, forecast, capital, budget and expiry band. Rows identify the product by SKU first and name second; `variant_id` is used only to open the detail and is never displayed. Add offset pagination and server-side sort; a test asserts that row totals equal the figure.
- **Rationale**: audit A17, A18; repository rule 5.
- **Alternatives**: raise the limit (rejected: does not scale).

### R9 Export
- **Decision**: server-generated CSV (UTF-8 with BOM, semicolon separator, decimal comma, Spanish headers) for cards, chart tables and drill-down, built from the same query as the screen plus a header block (filters, period, freshness, generated at in UTC and local). Row cap with a clear refusal above the cap. Roles buyer, approver and admin; the BFF writes an audit entry (who, what, filters, row count, when). The export row type has no notes, tax-id or Siweb-id fields, so they cannot leak.
- **Rationale**: opens correctly in a Spanish-locale spreadsheet; one query for screen and file avoids drift.
- **Alternatives**: client-side CSV (rejected: audit and role control); XLSX/PDF (rejected for now: extra dependency).

### R10 Roles and cost hiding
- **Decision**: viewer receives counts and quantities but no money fields (the server omits them; the card is hidden, not blank). Buyer, approver and admin see money. Check against audit item A24 before changing behaviour for existing users.
- **Alternatives**: hide in the web app only (rejected: data is still sent).

### R11 Shareable filters
- **Decision**: filters live in the page address (`desde`, `hasta`, `almacen`, `proveedor`, `categoria`, `familia`), read on load, validated, unknown values ignored with a notice. Supplier is referenced by its public id, warehouse by id; never a Siweb internal id for a product.
- **Alternatives**: local storage (rejected: not shareable).

### R12 Tests
- **Decision**: keep the mocked Playwright specs for states; add a live-stack project that runs against the real BFF, services and a seeded PostgreSQL with synthetic data from `packages/testing`, asserting card values against independently computed expectations, drill-down reconciliation, filters, export content and the axe scan. Add PostgreSQL integration tests for the figures and security-abuse tests for filters and export (injection, oversized ranges, role refusal).
- **Rationale**: acceptance requires API-backed visualizations and API plus Playwright tests.

### R13 Cost and operations
- **Decision**: no new container, job or schedule; snapshot and aggregate writes ride on the existing refresh. Export is synchronous with a row cap. Emit counters for refresh duration, export size and refusals.
- **Rationale**: shared budget and scale-to-zero.

### R14 Parallel work
- **Decision**: additive-only edits in shared files (`es-ES.json` under `dashboard.*`, a new `api/dashboard.ts`, `v2` schema beside `v1`). Anything that changes a shared contract is raised with Agent 00 first. Feature 005 runs in parallel; a conflict in `.specify/feature.json` is resolved at merge by keeping each branch's own value.

## Open assumptions (carry into tasks)

1. Capital tied up includes confirmed, unreceived orders (R3) - confirm with the owner.
2. Supplier links reach inventory by an existing event (R4) - verify first.
3. Historical snapshots start at deployment (R6) - accepted.
4. Viewer role may currently receive money fields (R10) - verify before changing.
