# Implementation Plan: Dashboard & Analytics Completion

**Branch**: `claude/speckit-jira-mmi-11-93e5e3` | **Date**: 2026-11-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/014-dashboard-analytics-completion/spec.md` (Jira MMI-11, epic MMI-1; continues MMI-3 and PR 19)

## Summary

Finish feature 006 without redoing it. The design of 006 (plan, data model, API contract, quickstart in `specs/006-executive-dashboard-analytics/`) stays the design of record; this plan adds the order of work, the verification step and the evidence needed to close it. First a verification pass classifies the 48 unchecked 006 tasks against the code (research R1). Then the verified gaps are built in this order: filters and URL state, drill-down kinds and SKU route, analytical charts, exports, freshness and trust, live-stack evidence and gates.

On this branch the inventory service already has `kpis.py`, `filters.py`, `drilldown.py`, `freshness.py`, `indicators.py` and `roles.py`, and the BFF has `/overview`, `/drilldown` and a forecast-basis route. Still missing on disk: `series.py`, `export.py`, the SKU detail route, the charts, export and freshness routes in the BFF, `apps/web/src/api/dashboard.ts`, the `charts/` folder and `scripts/live-stack/` (research R1 lists the evidence; the verification task confirms it). No new service and no new always-on resource.

## Technical Context

**Language/Version**: Python 3.12 (services), TypeScript 5 / React 18 (web); versions follow `pyproject.toml` and `package.json`.

**Primary Dependencies**: FastAPI, SQLAlchemy Core, Alembic, Pydantic (generated from JSON Schema); React, react-i18next, Recharts, Playwright, axe-core, Vitest. All already in use; no new runtime dependency. XLSX output reuses the library already used for proposal export (research R6); if none can be shared, the XLSX part is documented as a follow-up instead of adding one.

**Storage**: PostgreSQL, per-service schema. The 006 migration extends `agg_daily_kpis`; no new tables and no cross-schema SQL.

**Testing**: pytest (unit, contract, PostgreSQL integration, security-abuse), Vitest, Playwright (mocked and a new live-stack project), axe-core, the gate runner (`python -m gates run` from `scripts/`).

**Target Platform**: Azure Container Apps (scale to zero) behind the BFF; modern desktop and tablet browsers; es-ES only.

**Project Type**: Web application (SPA + BFF + domain services), existing monorepo.

**Performance Goals**: first meaningful view and filter change within 2 s on the reference dataset (spec SC-007); drill-down page within 1 s; export of up to the stated limit within 10 s.

**Constraints**: read-only toward the ERP; Decimal money; UTC plus original timestamp; SKU shown, never `variant_id`; shared budget EUR 120/month; synthetic data only; strings only from the es-ES catalogue; no business logic in the BFF; shared contracts and gates changed only through Agent 00.

**Scale/Scope**: single pharmacy and pet shop; under 10 concurrent users; 48 unchecked tasks to classify; at least 5 charts; 5 new drill-down kinds; 3 export kinds.

## Constitution Check

*GATE: passed before Phase 0; re-checked after Phase 1 design.*

| Principle | Assessment | Result |
|-----------|------------|--------|
| I. Least-privilege integrations | Reads only the app's own databases; adds no Siweb call, no write, no allowlist change; a test proves the dashboard routes accept GET only (006 T079). | Pass |
| II. Privacy and synthetic data | Fixtures from `packages/testing`; exports and SKU page exclude notes, tax ids and Siweb ids; screenshots and benchmark records use synthetic data only; local-load figures labelled and never mixed. | Pass |
| III. Explainable, human-controlled | Read-only; every figure drills down to SKUs; no autonomous action; money is Decimal. | Pass |
| IV. Contract-first boundaries | New payloads (charts, export header, freshness, SKU detail, new drill-down kinds) are defined first as additive JSON Schema in `packages/contracts` through Agent 00; each service keeps its own schema and role; BFF stays a pass-through ([contracts/dashboard-completion.md](contracts/dashboard-completion.md)). | Pass |
| V. Testable, observable, cost-bounded | Tests come before implementation within each story; export and refresh signals without notes or secrets; no new always-on service; cost note recorded. | Pass |
| Additional constraints | UI Spanish only; UTC plus original timestamp; excluded records counted and linked, never dropped. | Pass |

**Post-design re-check**: still passing. The only shared-surface risks are the additive contract changes (Agent 00), `client.ts` and `es-ES.json` (touched additively; merge again if PR 17 lands first), and the gate runner results (research R9).

## Project Structure

### Documentation (this feature)

```text
specs/014-dashboard-analytics-completion/
├── spec.md
├── plan.md              # this file
├── research.md          # decisions R1-R11 and the starting evidence
├── data-model.md        # additions on top of 006 data-model.md
├── quickstart.md        # validation scenarios for the completion work
├── contracts/
│   └── dashboard-completion.md   # additive routes and rules on top of 006's dashboard-api.md
├── checklists/requirements.md
└── tasks.md             # created by /speckit-tasks
```

### Source Code (repository root)

```text
packages/contracts/dto/              # additive schemas for charts, export header, freshness, SKU detail (via Agent 00)

services/inventory-service/
├── src/dashboard/
│   ├── series.py        # new: chart series and table rows
│   ├── export.py        # new: export rows from the same queries as the screen
│   ├── drilldown.py     # extend: demand, forecast, capital, budget, expiry_band kinds
│   ├── freshness.py     # extend: route payload and excluded-record count
│   └── kpis.py          # extend: write the new aggregate columns, 25-month retention
├── src/api/dashboard.py # add charts, export, freshness, SKU detail routes
└── tests/               # series, export, dst, indicators edges, local-load

services/api-bff/
├── src/routes/dashboard.py   # forward only; export audit entry; request-shape validation
└── tests/                    # read-only, export audit, failure drills, indicators degrade

apps/web/src/
├── api/dashboard.ts          # new typed module (does not grow client.ts)
├── features/dashboard/       # filters notice, SKU detail page, charts/, export actions, banner, newer-data notice
└── i18n/es-ES.json           # additive `dashboard.*` keys only

apps/web/tests/               # unit, mocked Playwright, live-stack project, axe
scripts/live-stack/           # seed loader and run guide over infra/compose.yaml
specs/006-executive-dashboard-analytics/{tasks.md,audit/}   # ticked and updated in place
specs/014-dashboard-analytics-completion/closure-report.md  # created by the first task
```

**Structure Decision**: reuse the 006 layout; add files only where the audit shows none. Figures stay in inventory-service, the BFF forwards, the web app presents. Completed 006 tasks are ticked in the 006 `tasks.md`; this feature's own `tasks.md` carries the verification, the gap work and the evidence tasks and references the 006 task numbers.

## Phases and order

1. **Verify** (US1): classify the unchecked 006 tasks; produce the closure report; tick what is already done.
2. **Foundations**: `dashboard.ts` API module, live-stack seed loader (needed by later evidence), contract schemas through Agent 00.
3. **Filters and URL state** (US2), then **drill-down and SKU route** (US3).
4. **Charts** (US4) and **export** (US5), which share the series and the filter set.
5. **Freshness and trust** (US6).
6. **Evidence** (US7): live journey, performance, axe, cost note, quickstart, gates, one PR.

Stories 2 and 3 are the P1 slice and can be reviewed alone; 4 and 5 can proceed in parallel after the routes exist.

## Complexity Tracking

No constitution violations. No new tables, services or events.
