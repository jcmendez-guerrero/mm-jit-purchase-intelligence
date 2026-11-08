# Dashboard audit (T001, T002, FR-024)

Audited on the worktree of `main` (feature 006). Evidence is `file:line` from this snapshot. Statuses: complete, partial, broken, missing, unverified. This file supersedes the unverified draft table in [../research.md](../research.md).

## T001 - Tools and commands

| Area | Fact | Source |
|------|------|--------|
| Python | `>=3.12,<3.13`; workspace via `uv` (`members = services/*, packages/contracts, packages/testing`) | `pyproject.toml:4,9` |
| Lint / types | ruff (line length 120, rules E F I B UP S DTZ RUF), mypy strict | `pyproject.toml` |
| Service tests | `pytest`, `testpaths = tests`, `pythonpath = src`; unit tests use in-memory SQLite (`StaticPool`), not PostgreSQL | `services/inventory-service/pyproject.toml`, `tests/conftest.py:1-25` |
| Web | Node `>=20`; scripts `lint`, `typecheck`, `test` (vitest), `e2e` (playwright), `check:bundle` | `apps/web/package.json:6-17` |
| Playwright | one `chromium` project, `testDir ./tests/e2e`, starts `vite` on 5173 unless `PLAYWRIGHT_BASE_URL` is set | `apps/web/playwright.config.ts` |
| Local full stack | `infra/compose.yaml` already defines postgres, azurite, siweb-mock, dev-issuer, siweb-connector, siweb-cost-writer, inventory-service/worker, forecast-service/worker, procurement-service/worker, api-bff, web | `infra/compose.yaml` |
| Contracts | `packages/contracts` (`dto/`, `events/`, generated `python/mmi_models`) | repo tree |

Commands to use (from repo root): `uv run pytest services/inventory-service/tests`, `uv run ruff check .`, `cd apps/web && npm run typecheck && npm test && npm run e2e`.

## T002 - Verified audit

| # | Capability | Status | Evidence |
|---|------------|--------|----------|
| A1 | Stock value card | complete | `DashboardScreen.tsx:229-242`; `kpis.py:129` `compute_summary`, `kpis.py:107` `valued_lots` |
| A2 | Coverage card | complete | `DashboardScreen.tsx:243-255`; `kpis.py:154` `coverage_by_variant` |
| A3 | Expiring value (single bucket) | partial | `DashboardScreen.tsx:256-267`; no time bands in `kpis.py` |
| A4 | Stockout severity ruler | complete | `DashboardScreen.tsx:217-226` |
| A5 | Spend card (needs a proposal) | partial | `DashboardScreen.tsx:268-297` |
| A6-A8 | Demand, forecast, capital cards | missing | no card in `DashboardScreen.tsx`; no field in `kpis.py` `Summary` (`:59`) |
| A9 | WAPE and bias | partial | table only, `DashboardScreen.tsx:300-325` |
| A10 | Demand trend + forecast chart with table | complete | `DashboardScreen.tsx:327-369`; `kpis.py:212,231` |
| A11 | ABC/XYZ ignores all filters | partial | `kpis.py:203` takes only `conn`; `api/dashboard.py` `/abc-xyz` has no filter parameters |
| A12-A14 | Filters not applied to every figure | broken | BFF `routes/dashboard.py:37-60`: risk gets warehouse only, ABC/XYZ and accuracy get none, supplier only reaches spend; warehouse note `DashboardScreen.tsx:204` |
| A13 | No date-range filter | missing | `days` 7-365 only, `routes/dashboard.py:42` |
| A15 | Only `?almacen=` in the address | partial | `DashboardScreen.tsx:43` |
| A16 | Freshness from one source, client constant | partial | `dashboardModel.ts:3,13`; `DashboardScreen.tsx:206-211` |
| A17 | Drill-down kinds, no pagination | partial | `drilldown.py:24` `KINDS`, `:26` `MAX_LIMIT = 200`, `:87` `truncated`; `routes/dashboard.py:63-77` |
| A18 | Product shown as `#variant_id` | broken | `DrillDownPanel.tsx:51,61,79`; risk table `DashboardScreen.tsx:118`; violates AGENTS.md rule 5 |
| A19 | SKU detail | complete | `ProductDetail.tsx` |
| A20 | Supplier panel | complete | `SupplierPanel.tsx` |
| A21 | Chart table alternative | complete | `ChartWithTable.tsx` |
| A22 | Fewer than five charts | missing | two `ChartWithTable` uses: `DashboardScreen.tsx:332,376` |
| A23 | Export | missing | no export in `apps/web/src/features/dashboard/` or `routes/dashboard.py` |
| A24 | Viewer receives money | **confirmed** | `READ` includes viewer, `routes/dashboard.py:19`; `Summary.as_json` returns `inventory_value` and `expiring_value` unconditionally, `kpis.py:72-75` |
| A25 | Local-load origin flag on dashboard data | missing | no `origin` or local marker in `services/inventory-service/src/dashboard/`; `lot_cost_projection.source` exists (`tables.py` near `:263`) but is a cost source, not a data origin |
| A26 | Quarantine count on dashboard | missing | no reference in dashboard code |
| A27 | Playwright dashboard specs use mocks | broken for the criterion | `apps/web/tests/e2e/dashboard.spec.ts` + `dashboard-mock.ts` |
| A28 | Performance specs exist | unverified | `dashboard-perf.spec.ts`, `services/api-bff/tests/perf`; not run |
| A29 | Accessibility specs exist | complete | `a11y*.spec.ts` |
| A30 | String baseline exists | partial | `apps/web/tests/unit/hardcoded-strings.baseline.json` |

## Open assumptions resolved

1. **Supplier links / event (R4) - design simplified.** No event carries supplier links to inventory. But `lot_cost_projection` (variant_id, supplier_id, lot, unit_cost) is already in the inventory schema and is fed by `ProcurementLotCostChanged` (carries `supplier_id`). Stock sits in lots, so the supplier filter on stock figures can use `lot_cost_projection.supplier_id` directly. **Decision: no `supplier_variant_link` table, no new event.** Limit: products with no lot (no stock) have no supplier for this filter; stated in the card note.
2. **History (R6) - design simplified.** `agg_daily_kpis` (`tables.py:223-236`) already stores one row per day, warehouse and category with `inventory_value`, `expiring_value`, `coverage_days_avg`, `stockout_risk_count`, written by `refresh_aggregates` (`kpis.py:183-200`) after each sync, and has a `supplier_id` column (currently NULL). **Decision: extend `agg_daily_kpis` with the extra columns (capital, demand, forecast, origin) instead of a new `dashboard_snapshot` table.** Stock-value history exists from the first sync that wrote this table.
3. **Viewer money (R10):** confirmed exposed (A24); change needed, with the compatibility note that viewers lose money fields on the dashboard.
4. **Local-load origin (A25):** not tracked on dashboard data; needs an `origin` marker on the aggregates and a check of how the local loader tags its rows (surrogate ids from 9,000,000 per AGENTS.md rule 5) before T061.
5. **Capital tied up (R3):** still needs the owner's answer (T003).
6. **Live stack:** `infra/compose.yaml` already runs every service, so T074 reuses it with the synthetic seed instead of writing a new script.

## Effects on the plan

- T007: migration extends `agg_daily_kpis` (no new tables).
- T010: dropped as a consumer; replaced by a query over `lot_cost_projection`.
- T048: extend `refresh_aggregates` rows; history range comes from existing data.
- T074: wrap `infra/compose.yaml` plus the seed loader.
- T075 narrows to forecast-service accuracy history and procurement budget/open orders.
