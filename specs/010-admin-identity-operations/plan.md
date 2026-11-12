# Implementation Plan: Administration, Identity & Operations (Agent 07)

**Branch**: `claude/jira-mmi-9-spec-id-98c87e` | **Date**: 2026-11-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/010-admin-identity-operations/spec.md` (Jira MMI-9, Confluence 3244047)

## Summary

Audit-then-close-gaps. The evidence inventory ([research.md](research.md) section 1) shows durable roles, the role mirror with backoff, approver eligibility, separation of duties, the audit chain, source-freshness and job re-run screens already exist and are tested. The real gaps are: (1) fresh MFA is missing on role changes, mirror retry and re-runs; (2) no audit viewer, verify or export; (3) no concurrency guard on role edits; (4) no unified queue/dead-letter view; (5) no in-app, de-duplicated, acknowledgeable alerts; (6) no backup status; (7) cost is a static number. Approach: harden the existing BFF routes, add a small admin-ops slice (alerts, snapshots, settings) in the BFF-owned schema, evaluate alerts from the existing scheduled worker (scale to zero), ingest backup/cost/queue figures as validated read-only snapshots, and extend the existing admin screens in es-ES.

## Technical Context

**Language/Version**: Python 3.12 (api-bff), TypeScript with React (apps/web), as in the existing code

**Primary Dependencies**: FastAPI, SQLAlchemy and Alembic (BFF), existing `audit.py` chain, existing React app with `i18n/es-ES.json`; no new runtime dependency

**Storage**: PostgreSQL, BFF-owned `bff` schema; migration `0002_admin_ops.py` adds `alerts`, `ops_snapshots`, `ops_settings`

**Testing**: pytest (unit, API contract, PostgreSQL integration, security-abuse), Vitest, Playwright e2e; synthetic fixtures under `packages/testing/fixtures/ops/`

**Target Platform**: Azure Container Apps (scale to zero) and local compose

**Project Type**: web application (BFF service plus SPA)

**Performance Goals**: console cards load in under 2 s on the synthetic dataset; an audit page of 50 rows under 500 ms

**Constraints**: shared EUR 120/month; no always-on evaluator; no cross-service SQL; no ERP requests; no secrets or free text in audit, logs or exports

**Scale/Scope**: a handful of users; audit table in the tens of thousands of rows; about 6 new BFF route groups and 4 console sections

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design: still passing.*

| Principle (constitution v1.3.0) | Result |
|---|---|
| I. Least-privilege integrations | Pass. No new cloud identity: cost, backup and queue figures arrive as read-only snapshots (D3). No ERP request. |
| II. Privacy and synthetic data | Pass. Fixtures synthetic; audit and exports carry ids and codes, never notes or tokens; SC-008 scan test. |
| III. Explainable, human-controlled purchasing | Pass. Approver is not creator or last editor (existing); MFA extended to all sensitive admin actions; no autonomous writes. |
| IV. Contract-first | Pass. Contracts drafted in [contracts/](contracts/) and negotiated through Agent 00 before code (task order enforces it). |
| V. Testable, observable, cost-bounded | Pass. Tests precede implementation; alerts via the existing scheduled job; `infra/tests/test_cost_guardrails.py` stays green. |
| V (cost bound) and `AGENTS.md` rule 10, shared EUR 120 budget | Pass. No new always-on resource or paid service. |

No violations, so Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/010-admin-identity-operations/
├── plan.md
├── research.md          # inventory (FR-001) and decisions D1-D9
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── admin-ops.delta.openapi.yaml
│   ├── ops_snapshot.v1.schema.json
│   └── error-keys.md
└── tasks.md             # created by /speckit-tasks
```

### Source Code (repository root)

```text
services/api-bff/
├── migrations/versions/0002_admin_ops.py        # new tables
├── src/
│   ├── db/{tables.py, roles.py}                 # expected_revision; new stores in db/ops.py (new)
│   ├── routes/{admin_roles.py, admin_status.py} # add fresh MFA; new routes/admin_audit.py, admin_ops.py (new)
│   ├── ops/{alerts.py, snapshots.py}            # pure evaluation and snapshot validation (new)
│   └── worker.py                                # add alerts and snapshot-ingest passes
└── tests/                                       # new MFA, audit API, alerts, snapshots, no-secrets tests
apps/web/src/features/admin/                     # AuditScreen, AlertsPanel, QueuePanel, OpsCards (new); extend RolesScreen
apps/web/src/i18n/es-ES.json                     # new admin.* keys
apps/web/tests/{unit,e2e}/                       # new specs
packages/testing/fixtures/ops/                   # synthetic snapshots
packages/contracts/{dto,errors}/                 # promoted from contracts/ via Agent 00
infra/bicep/modules/alerts.bicep                 # reuse the action group; add one log-marker rule (ADMIN_ALERT_OPENED); no new always-on resource
```

**Structure Decision**: extend the existing BFF and web admin feature folders; the only new storage is three BFF-schema tables. Other services are untouched (shared contract changes go through Agent 00).

## Complexity Tracking

None.
