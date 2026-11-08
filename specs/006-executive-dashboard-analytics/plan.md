# Implementation Plan: Executive Dashboard & Analytics

**Branch**: `006-executive-dashboard-analytics` | **Date**: 2026-11-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-executive-dashboard-analytics/spec.md` (Jira MMI-3, epic MMI-1)

## Summary

Turn the existing buyer dashboard into an executive dashboard whose every figure is computed from stored data. The baseline is already substantial (inventory value, coverage, expiring value, stockout severity, proposal spend, ABC/XYZ, demand trend with forecast, accuracy table, risk list, drill-down, product and supplier panels). The audit in [research.md](research.md) shows what is complete, partial, missing and unverified. The plan reuses the working parts and closes the gaps:

- add the missing indicators (demand, forecast, capital tied up, purchasing budget as a card, WAPE/bias as cards);
- make the date, warehouse, supplier and category filters apply to every figure, and make them shareable by link;
- add per-card freshness, origin and definition;
- add at least five live charts, each with a table view;
- add SKU-first drill-down with pagination (replace the `#variant_id` display);
- add audited, permission-gated exports;
- add role-based hiding of cost figures;
- prove it with API-backed Playwright tests on synthetic data, not only mocked responses.

No new service and no new always-on resource. The inventory service owns the figures, the BFF only orchestrates, the web app only presents.

## Technical Context

**Language/Version**: Python 3.12 (services), TypeScript 5 / React 18 (web). *Versions follow the repository's `pyproject.toml` and `package.json`; confirmed in the first task.*

**Primary Dependencies**: FastAPI, SQLAlchemy Core, Alembic, Pydantic (generated from JSON Schema); React, react-i18next, Recharts, Playwright, axe-core (all already in use). No new runtime dependency planned.

**Storage**: PostgreSQL, per-service schema. Inventory-service extends its existing `agg_daily_kpis` daily history (migration 0007: capital, demand, forecast, origin); the supplier filter reads the supplier already stored on each lot cost (`lot_cost_projection`). No new tables, no cross-schema SQL.

**Testing**: pytest (unit, contract, PostgreSQL integration, security-abuse), Vitest (unit), Playwright (E2E and axe). New: a live-stack Playwright project that runs against the real API with synthetic seed data.

**Target Platform**: Azure Container Apps (scale to zero) behind the existing BFF; modern desktop and tablet browsers; es-ES only.

**Project Type**: Web application (SPA + BFF + domain services), existing monorepo.

**Performance Goals**: first meaningful dashboard view within 2 s and filter change within 2 s on the reference dataset (spec SC-003); drill-down page within 1 s.

**Constraints**: read-only (no ERP write, no purchasing state change); Decimal money; UTC storage with original timestamp preserved; SKU shown, never `variant_id`; shared budget EUR 120/month, no always-on analytics service; synthetic data only; strings only via the es-ES catalogue.

**Scale/Scope**: single pharmacy and pet shop; catalogue in the low tens of thousands of variants; under 10 concurrent users; 10 indicator families, 6 or more charts, 6 existing drill-down kinds plus new ones, 3 export kinds.

## Constitution Check

*GATE: passed before Phase 0; re-checked after Phase 1 design (below).*

| Principle | Assessment | Result |
|-----------|------------|--------|
| I. Least-privilege integrations | Feature reads only the app's own databases; adds no Siweb call, no write, no allowlist change. | Pass |
| II. Privacy and synthetic data | Tests and fixtures synthetic (`packages/testing`); exports exclude notes, tax ids and Siweb ids; local-load data labelled and never mixed with ERP data. | Pass |
| III. Explainable, human-controlled | Read-only; every figure has a definition, basis and drill-down to contributing SKUs; no autonomous action. Money is Decimal. | Pass |
| IV. Contract-first boundaries | New and changed payloads defined first as JSON Schema in `packages/contracts` (additive `v2`, `v1` untouched); each service keeps its schema and role; the supplier filter reads inventory's own lot cost projection, never another service's tables; BFF holds no business rule. | Pass |
| V. Testable, observable, cost-bounded | Unit, contract, integration, abuse and E2E tests planned; export and refresh emit operational signals; no new always-on service; reuses the aggregate refresh job. | Pass |
| Additional constraints | UI Spanish only; UTC plus original timestamp; quarantined records counted and linked, not dropped. | Pass |

**Post-design re-check**: still passing after the audit and the review fixes. Two items stay explicit assumptions, not violations: the definition of "capital tied up" (owner answer, T003) and Agent 00's approval of the forecast and procurement changes (T075). The audit resolved the rest (supplier filter, history, viewer money; see `audit/dashboard-audit.md`).

## Project Structure

### Documentation (this feature)

```text
specs/006-executive-dashboard-analytics/
├── spec.md
├── plan.md              # this file
├── research.md          # audit of the current dashboard + decisions
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── dashboard-api.md
│   └── dashboard_indicators.v2.schema.json
├── checklists/requirements.md
└── tasks.md             # created by /speckit-tasks
```

### Source Code (repository root)

```text
packages/contracts/dto/
└── dashboard_indicators.v2.schema.json     # new; v1 left as is (contract-first, additive)

services/inventory-service/
├── src/dashboard/
│   ├── kpis.py               # extend: demand, forecast, capital, expiry bands, coverage buckets, date range
│   ├── filters.py            # done: validated FilterSet (T008)
│   ├── roles.py              # helper done: money hiding (T012); wiring in T023
│   ├── series.py             # new: stock-value-over-time and forecast-error series
│   ├── drilldown.py          # extend: SKU-first rows, offset pagination, new kinds
│   ├── export.py             # new: spreadsheet-friendly rows with filter header
│   └── freshness.py          # new: per-source refresh time, origin, staleness
├── src/api/dashboard.py      # extend routes; same role dependency
├── src/db/                   # migration 0007 extends agg_daily_kpis (no new tables)
└── tests/                    # unit, contract, PostgreSQL integration, abuse

services/api-bff/
├── src/routes/dashboard.py   # orchestrate only; pass-through filters; export audit entry
└── tests/                    # orchestration, RBAC, export audit, downstream failures

apps/web/src/
├── features/dashboard/       # reuse existing files; add indicator cards, charts/, useDashboardFilters.ts (done), useNewerDataNotice.ts, export
├── api/dashboard.ts          # new module (avoids growing client.ts, which other work edits)
├── i18n/es-ES.json           # additive `dashboard.*` keys only
└── ui/                       # reuse FilterBar, DataTable, ScreenState, StatusBadge

apps/web/tests/
├── unit/                     # model, filter URL state, formatting
└── e2e/                      # existing mocked specs kept; new live-stack spec + axe scan

scripts/live-stack/                              # seed loader and run guide over infra/compose.yaml (T074)
specs/006-executive-dashboard-analytics/audit/   # verified audit (done, T001/T002)
```

**Structure Decision**: extend the existing web + BFF + inventory-service layout. Figures live in inventory-service because it already owns stock, lots, demand and the aggregate refresh. Supplier-based filtering uses the supplier already stored on each lot cost in inventory (research R4), so no cross-service link table is needed. The BFF stays a thin orchestrator. Files shared with other parallel work (`client.ts`, `es-ES.json`, `packages/contracts`) are touched only additively; shared contract changes go through Agent 00.

## Complexity Tracking

No constitution violations and no extra tables, services or events: the audit showed that the existing `agg_daily_kpis` history and `lot_cost_projection` cover the daily history and the supplier filter.
