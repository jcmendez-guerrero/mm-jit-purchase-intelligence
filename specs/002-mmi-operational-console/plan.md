# Implementation Plan: MMI 002 — Operational Console, Analytics, Supplier Configuration and Predictive Seed Import

**Branch**: `claude/mmi-002-operational-console-ibqo4g` | **Date**: 2026-11-05 | **Spec**: [spec.md](spec.md)

**Status**: For human review. No implementation starts before this plan, `spec.md` and `tasks.md` are approved (Jira KAN-34, Confluence 1998849).

## Summary

Turn the 001 pipeline into a buyer-operated console without rewriting it. The work is mostly additive:
(1) close the PR #1 approval and security blockers (durable roles mirrored to procurement, review of the
second-agent web/BFF code); (2) extend the data each service already owns: procurement gains the missing
supplier terms, product-supplier overrides, purchase policies and scenarios; forecast gains seed datasets,
the import pipeline and editable model parameters; inventory gains aggregate read models; (3) add
contract-first BFF endpoints that only orchestrate; (4) build the Spanish screens: charts, terms editor, policy
console, import wizard, scenario comparison, admin status. No new Azure resources; no always-on workers.

Technical approach and rejected alternatives are in [research.md](research.md). Entities are in
[data-model.md](data-model.md). Contracts are in [contracts/](contracts/). Run and validation steps are in
[quickstart.md](quickstart.md).

## Technical Context

**Language/Version**: Python 3.12 (services); TypeScript 5 / React 18 (SPA); PostgreSQL 16. Unchanged from 001.

**Primary Dependencies (existing, reused)**: FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic, OR-Tools CP-SAT, openpyxl, Vite, React Router, TanStack Query, i18next, Playwright, Vitest.

**New dependencies (to be confirmed in research.md)**: a React charting library with SVG output (Recharts) and an accessible data-table fallback; `python-multipart` streaming upload in the BFF; `defusedxml`-style safe XLSX handling via openpyxl read-only mode with explicit zip-bomb limits; `axe-core` (Playwright) for accessibility. No new services, no new Azure resources.

**Storage**: existing PostgreSQL server, one schema and role per service. New: a `bff` schema and role for durable roles (the BFF has no database today). Seed files in a new private, encrypted container of the existing storage account.

**Testing**: pytest per service; JSON Schema contract tests and compatibility baseline; PostgreSQL migration upgrade/downgrade (`RUN_PG_MIGRATIONS=1`); Azurite adapters; compose E2E (`RUN_E2E=1`); Playwright es-ES flows with axe; security abuse tests (upload, CSRF, RBAC, MFA freshness, formula injection); localisation check that fails on hard-coded strings; cost-guardrail test over the Bicep and compose definitions. Synthetic fixtures only (`packages/testing`).

**Target Platform**: Azure Container Apps (Consumption) and Jobs, scale to zero; modern desktop browsers.

**Project Type**: Existing monorepo, multi-service web application.

**Performance Goals**: dashboard first meaningful content under 3 s for about 1,000 variants (SC-003); a seed file of 1,000 products validated and previewed in under 60 s; scenario computation under 2 min for the full catalogue; interactive endpoints p95 under 1 s for fewer than 10 users.

**Constraints**: ERP read-only except the existing supplier-cost PUT; shared EUR 120/month; scale-to-zero, replica and job caps; public repository (synthetic only); es-ES only; contract-first; no cross-schema SQL.

**Scale/Scope**: about 1,000 variants, fewer than 10 users, seed files up to a few tens of thousands of rows, about 8 new screens or major screen extensions.

## Constitution Check

*GATE: passes before research; re-checked after design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Least-privilege integrations | No new ERP call. Terms, policies, seeds, scenarios are local. The cost writer, its allowlist and MFA release are untouched. Tests prove no new path reaches the connector or writer. | PASS |
| II. Privacy & synthetic data | Seed templates and fixtures are synthetic; import ignores notes and tax identifiers and stores only `has_note`; no real files in the repository; retention for quarantined uploads defined. | PASS |
| III. Explainable, human-controlled purchasing | Scenarios are computed, never auto-applied; promotion creates a normal proposal needing a different approver with fresh MFA; every run records dataset, policy and terms versions; Decimal money. | PASS |
| IV. Contract-first | JSON Schemas and the BFF OpenAPI delta are written first; each service owns its tables and migrations; the BFF holds only identity data (roles) in its own schema and no business rules; role mirroring uses the authenticated internal endpoint with an outbox. | PASS |
| V. Testable, observable, cost-bounded | Test strategy above; metrics for import jobs, mirror lag and upload rejections; no new infrastructure; guardrail test. | PASS |
| Constraints | Bicep, reuse of shared resources, synthetic-only public content, quarantine of malformed data. | PASS |

**Post-design re-check**: PASS. Two items need a recorded decision and cost note, not a violation: the new `bff` schema and role, and the new storage container. Both are in the Complexity Tracking table and in ADR-018 / ADR-020.

## Project Structure

### Documentation (this feature)

```text
specs/002-mmi-operational-console/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── bff-api.delta.openapi.yaml     # new/changed BFF routes (design before code)
│   ├── service-apis.md                # per-service internal routes and ownership
│   ├── events.md                      # new/changed events
│   ├── import-template.md             # Spanish CSV/XLSX template and validation rules
│   └── error-keys.md                  # stable localised error keys
├── checklists/requirements.md
└── tasks.md                           # created by /speckit-tasks
docs/adr/018-configuration-ownership.md
docs/adr/019-override-precedence.md
docs/adr/020-seed-provenance.md
```

### Source code: existing components and the change each receives

```text
apps/web/src/features/
├── dashboard/      EXTEND  charts, KPIs, live filters, drill-down (no hard-coded warehouse)
├── suppliers/      NEW     list, terms editor, product overrides, history
├── policies/       NEW     policy console with preview and effective dates
├── imports/        NEW     template, upload, mapping, preview, validation, activation, rollback
├── scenarios/      NEW     scenario builder, comparison, promotion, export
├── admin/          EXTEND  roles (durable), sync, imports, model runs, costs
├── proposals/ costs/ quality/ config/   REUSE (proposals show terms and scenario links; config splits into policies/admin)
services/api-bff/
├── src/{auth,routes,clients}   EXTEND  new routes and clients; role store moves to the bff schema;
│                                       mirror to procurement; upload streaming and limits
├── migrations/ alembic.ini     NEW     schema `bff` (user_roles, role_audit, role_mirror_outbox)
services/procurement-service/
├── src/terms/                  EXTEND  full terms, effective-dated versions, product overrides, precedence
├── src/allocation/             EXTEND  consume terms (lead time, pack multiples, discounts, validity, disable)
├── src/policies/               NEW     purchase policy sets (service levels, budget, cadence, min/max)
├── src/scenarios/              NEW     what-if computation, comparison, sensitivity, promotion
├── src/users/                  REUSE   role mirror endpoint (already present)
├── migrations/                 ADD     0005 terms+overrides, 0006 policies, 0007 scenarios
services/forecast-service/
├── src/seeds/                  NEW     datasets, parsing, mapping, validation, activation, rollback
├── src/api.py                  EXTEND  runs, variants, imports, parameters, accuracy
├── src/runs/                   EXTEND  read active dataset and parameters; record versions
├── migrations/                 ADD     0003 seeds, 0004 parameters/accuracy
services/inventory-service/
├── src/api/                    EXTEND  summary, trend, abc-xyz, risks, filter options
├── src/projections/            EXTEND  daily aggregate read models; demand exclusions/censoring rules
├── migrations/                 ADD     0003 aggregates, exclusions
services/siweb-connector/ services/siweb-cost-writer/   UNCHANGED (tests assert no new path)
packages/contracts/             ADD     schemas for terms, policies, seeds, scenarios, aggregates, events
packages/testing/               ADD     synthetic seed files (valid, invalid, malicious), terms fixtures
infra/                          ADD     storage container + lifecycle (Bicep), compose wiring, guardrail test
```

**Structure Decision**: keep the monorepo and every existing service boundary. Ownership follows the data (ADR-018): procurement = commercial and purchase policy; forecast = datasets and model parameters; inventory = demand-side rules and aggregates; BFF = orchestration and identity only.

## Delivery Phases (one small PR per phase; no merge of PR #1; no deploy)

| Phase | Scope | Stories / FRs | Exit gate |
|-------|-------|---------------|-----------|
| 0 Blockers | Durable BFF roles in `bff` schema; mirror to procurement with outbox/retry; two-approver, separation and fresh-MFA proven in compose; review of commit 3a664a0 with findings fixed or recorded; track 001 gates (V6, V7, 429, threat model, cost review, smoke test) | US1; FR-001..004 | Full-stack approval survives BFF restart |
| 1 Contracts and migrations | JSON Schemas, BFF OpenAPI delta, event and error-key catalogue, compatibility baseline; migrations (up/down) for all new tables; ADRs 018–020 | all; FR-036 | Contract and PG migration tests green |
| 2 Supplier and policy CRUD | Terms and overrides services + routes + UI; policy sets + preview + revisions + UI; allocation consumes terms; audit | US3, US4; FR-010..019 | Edit → reload → next proposal uses it; ERP untouched |
| 3 Import pipeline | Upload hardening, parser, mapping, validation, quarantine, dry-run diff/backtest, activation/rollback, forecast run versioning, UI wizard | US5; FR-020..027 | Upload → activate → run → rollback end to end; malicious files refused |
| 4 Analytics | Aggregate read models, dashboard endpoints, charts, filters, drill-down, product detail, accessible alternatives | US2; FR-005..009 | KPIs equal reference totals; a11y clean |
| 5 Scenarios | Scenario engine, comparison, sensitivity, explanations, promotion, exports | US6; FR-028..032 | Constraint changes alter allocations with reasons |
| 6 Verification and cost | Admin status, Spanish Playwright suite with screenshots, security abuse suite, performance budget, localisation check, cost guardrails, final report | US7; FR-033..039 | All SC-001..011 evidenced |

Phase 4 reads data produced by Phases 2–3 but is independent of them in code, so it may run in parallel with Phase 3 after Phase 1.

## Complexity Tracking

| Addition | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|--------------------------------------|
| `bff` schema and role | Roles must survive restarts (FR-001); the BFF is the identity edge | Keeping roles in procurement would make the purchasing domain own session identity and add a synchronous dependency to every login; keeping them in memory is the blocker itself |
| Private storage container for quarantined seed files | Uploads need private, encrypted, retention-limited storage (FR-020) | Storing files in PostgreSQL bloats the shared database; a new storage account adds cost |
| Aggregate read models in inventory | Dashboard must meet the 3 s budget without always-on analytics (FR-038) | Computing from raw movements per request is too slow; a separate analytics store breaks the budget |
