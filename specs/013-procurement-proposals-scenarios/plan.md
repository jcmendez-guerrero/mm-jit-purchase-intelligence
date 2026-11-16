# Implementation Plan: Procurement Proposals & Scenarios (Agent 03)

**Branch**: `claude/speckit-specify-jira-mmi5-d4aabd` | **Date**: 2026-11-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/013-procurement-proposals-scenarios/spec.md` (Jira MMI-5, Confluence 3145771)

## Summary

Audit-then-close-gaps. The evidence inventory ([research.md](research.md) section 1) shows proposal generation, line edits with optimistic versioning, submit/approve with separation of duties and fresh MFA, scenarios with sensitivity and promotion (promotion already creates a new draft and supersedes the week's other proposals), allocation with budget and terms, and CSV/Excel export are all present with tests. The plan therefore builds only the gaps: viewer export is still allowed at the gateway (G1), no API-backed Playwright journey covers proposal to approval (G2), and several guarantees (20-run determinism, no supplier/ERP request from proposal and scenario paths, 2,000-SKU timing, stale-scenario and superseded display) are only partly proven (G3 to G7). No new service, table or runtime dependency is expected.

## Technical Context

**Language/Version**: Python 3.12 (procurement-service, api-bff), TypeScript with React (apps/web), as in the existing code

**Primary Dependencies**: FastAPI, SQLAlchemy and Alembic, OR-tools CP-SAT with greedy fallback (existing allocation), React with `i18n/es-ES.json`; no new runtime dependency

**Storage**: PostgreSQL, procurement-owned schema; no migration expected (a migration is added only if the inventory finds a missing column, and then only in procurement-service)

**Testing**: pytest (unit, API contract, PostgreSQL integration, security-abuse), Vitest, Playwright e2e against the compose stack with synthetic fixtures from `packages/testing`

**Target Platform**: Azure Container Apps (scale to zero) and local compose

**Project Type**: web application (BFF, domain service and SPA)

**Performance Goals**: proposal for about 2,000 active synthetic SKUs in under 60 s; scenario run bounded by the existing solver time limit with a deterministic fallback

**Constraints**: shared EUR 120/month; no always-on workers; no cross-service SQL; no ERP request and no supplier send from this domain; no free text in audit, logs or exports

**Scale/Scope**: a handful of users; hundreds to low thousands of SKUs; 5 user stories, about 7 gaps

## Constitution Check

*Gate: passed before research; re-checked after design.*

| Principle | Result |
|---|---|
| I Least-privilege integrations | Pass. No ERP request is added; a test proves proposal and scenario paths make none. |
| II Privacy and synthetic data | Pass. Synthetic fixtures only; exports carry no free text. |
| III Explainable, human-controlled | Pass. Approval keeps creator/last-editor separation and fresh MFA; promotion needs a new approval. |
| IV Contract-first | Pass. The only shared change is an error key and a role clarification in [contracts/proposals-scenarios.delta.md](contracts/proposals-scenarios.delta.md), routed through Agent 00. |
| V Testable, observable, cost-bounded | Pass. No new always-on resource. |

Post-design re-check: still pass; no violation to justify.

## Project Structure

### Documentation (this feature)

```text
specs/013-procurement-proposals-scenarios/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── proposals-scenarios.delta.md
└── tasks.md             # created by /speckit-tasks
```

### Source Code (repository root)

```text
services/procurement-service/src/{proposals,scenarios,approvals,allocation,api}/   # domain, owned
services/procurement-service/tests/                                                 # new guarantee tests
services/api-bff/src/routes/{api.py,scenarios.py}                                   # role gate on export (G1)
apps/web/src/features/{proposals,scenarios}/                                        # superseded and stale display (G6)
apps/web/src/i18n/es-ES.json                                                        # new Spanish strings
apps/web/tests/e2e/                                                                 # API-backed journey (G2)
```

**Structure Decision**: reuse the existing layout; edit only the files above. Files owned by other agents (supplier terms editing, policies, dashboard, admin) are not touched; shared contract changes go through Agent 00.

## Complexity Tracking

No constitution violations.
