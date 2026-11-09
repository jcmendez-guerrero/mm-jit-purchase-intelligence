# Research: Executive Dashboard & Analytics

Audit baseline: worktree of `main` at the start of this feature. **The verified audit, with line numbers, is in [audit/dashboard-audit.md](audit/dashboard-audit.md); where it differs from this draft table, the audit file wins.** Decisions R4 and R6 below were revised by it.

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
  - *Capital tied up* (confirmed by the owner 2026-11-09, FR-025): stock at lot acquisition cost plus the amount of confirmed supplier orders not yet received, the two parts shown separately; a partly received order counts only its unreceived part, and an order line with no known cost goes to the incomplete bucket.
  - *Where each part is computed* (checked in code): inventory-service holds the stock at lot cost, but its `inbound_lines` keep only quantities, with no prices and no receipts. The amount of confirmed orders not yet received therefore comes from procurement-service (the approved additive change to `GET /summary/spend`). The gateway passes that amount to inventory-service (`GET /dashboard/indicators?open_orders=`), which makes `capital_tied_up = stock_at_cost + open_orders` and returns both parts; the gateway does no money arithmetic (ADR-023, `test_routes_do_no_money_arithmetic`, added by feature 005 after this was first decided).
  - *Purchasing budget* (FR-026): the budget caps in force within the selected date range against the proposed and confirmed spend in that range; see R15.
  - *WAPE and bias*: existing forecast-service definitions, shown as cards with a time series.
- **Rationale**: the spec asks for each; definitions are stored with the indicator (FR-005).
- **Alternatives**: capital equal to stock value (rejected: duplicate card).

### R4 Supplier filter on stock figures (revised by the audit)
- **Decision**: no new table and no new event. The supplier of a stock lot is the supplier of the cost that values it (the lot's own cost, or the labelled fallback), read from inventory's `lot_cost_projection`. Every figure (value, expiry, coverage, risk scope) uses the same rule (`_supplier_variants` and `valued_lots` in `kpis.py`).
- **Rationale**: stock lives in lots and lots already carry the supplier through `ProcurementLotCostChanged`; no cross-schema SQL and no business rule in the BFF.
- **Limits**: products with no costed lot have no supplier for this filter; an unknown supplier gives empty figures, not an error. The supplier ids in the dropdown must be the same ids stored on lot costs: verify with a real procurement id before the BFF forwards the filter to stock figures (T033).
- **Alternatives**: a supplier-variant link table fed by events (rejected: unnecessary); the BFF passing variant ids (rejected).

### R5 Freshness, origin and staleness
- **Decision**: each source (inventory snapshot, movements, forecast, accuracy, budget/spend) reports `refreshed_at` (UTC, with the original string), origin (`erp_sync`, `local_load`, `forecast`, `proposal`) and a state (`ok`, `no_data`, `stale`, `error`). The stale threshold comes from the server (single source), replacing the constant in the web app. Figures from local load carry the local label and are never summed with ERP-origin data.
- **Rationale**: FR-003, FR-018, audit A16, A25.
- **Alternatives**: keep the client-side threshold (rejected: two sources of truth).

### R6 History for "over time" charts (revised by the audit)
- **Decision**: no new snapshot table. `agg_daily_kpis` already stores one row per day, warehouse and category and is written by `refresh_aggregates` after each sync. Migration 0007 adds `capital_tied_up`, `demand_units`, `forecast_units` and `origin` to it. Charts show the range available and say so; no history is invented.
- **Rationale**: audit evidence `tables.py:223-236`, `kpis.py:183-200`; less code and one history to keep.
- **Alternatives**: a separate `dashboard_snapshot` table (rejected: duplicates it); rebuilding history from movements (rejected: past costs not reproducible).

### R7 Visualizations (at least five, each with a table view)
1. Demand trend with forecast and band (exists).
2. ABC/XYZ distribution (exists, made filter-aware).
3. Expiry exposure by time band (new).
4. Coverage distribution in buckets (new).
5. Capital tied up by category and by supplier (new).
6. Forecast error (WAPE) and bias over time (new, from accuracy history).
7. Stock value over time (new, depends on R6).

Charts 1-6 satisfy the "five or more" gate; chart 7 uses the `agg_daily_kpis` history that already exists. All reuse `ChartWithTable` and the chart colour hook.

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
- **Decision**: no new container, job or schedule; the extra columns are written by the existing aggregate refresh. Export is synchronous with a row cap. Emit counters for refresh duration, export size and refusals.
- **Rationale**: shared budget and scale-to-zero.

### R14 Parallel work
- **Decision**: additive-only edits in shared files (`es-ES.json` under `dashboard.*`, a new `api/dashboard.ts`, `v2` schema beside `v1`). Anything that changes a shared contract is raised with Agent 00 first. Feature 005 runs in parallel; a conflict in `.specify/feature.json` is resolved at merge by keeping each branch's own value.

### R15 Purchasing budget over a date range (decided in planning, FR-026)
- **Decision**: reuse the rule the procurement service already applies to one week (`effective_weekly_budget`: the global weekly cap in force, a monthly cap split over 4.33 weeks, the stricter of the two). For a range, take every ISO week whose Monday falls inside the range, apply that rule as of each Monday and add the results. List each cap row used with its period. Weeks without any cap add nothing; if no week has a cap the card says "sin presupuesto" and still shows the spend. Spend in the range is the total of the newest non-superseded proposal of each week, which already covers proposed and confirmed amounts, so confirmed orders are not added a second time.
- **Rationale**: one rule for one week and for many; explainable (the caps and weeks are listed); no new budget logic in the BFF.
- **Alternatives**: summing weekly and monthly caps together (rejected: double counts); prorating by calendar days (rejected: unlike the rule already in use).
- **To verify** in T022 with a test: a range spanning a week with a weekly cap, a week covered only by a monthly cap, and a week with none.

## Open assumptions and how they were resolved

1. Capital tied up (R3): **decided by the owner on 2026-11-09**, FR-025.
2. Supplier links (R4): **resolved, not needed** (lot cost projection); the dropdown ids match the lot cost ids (T081).
3. History (R6): **resolved**, `agg_daily_kpis` already holds it.
4. Viewer role and money (R10): **fixed** (T012); supplier-term amounts stay visible by the owner's decision (T089).
5. Cross-service changes (T075) and the v2 schema in `packages/contracts` (T003): **approved by the owner on 2026-11-09**, Agent 00 to be informed.
6. Open: the spend counted per week (R15) is verified by the T022 tests.
