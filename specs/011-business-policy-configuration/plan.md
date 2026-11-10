# Implementation Plan: Business Policy Configuration (Agent 06)

**Branch**: `claude/jira-mmi-8-spec-f00d63` | **Date**: 2026-11-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/011-business-policy-configuration/spec.md` (Jira MMI-8, epic MMI-1)

## Summary

Completion and verification of the policy console that feature 002 delivered. The first-pass audit (see [research.md](research.md)) shows the rules, scopes, preview, effective dating and audit largely exist; the work is to close five concrete gaps and to prove the acceptance criteria with API-backed tests:

1. Budget-cap and demand-rule saves have no revision check (FR-010).
2. Policy and budget writes do not require fresh multi-factor authentication (FR-012).
3. Product scope is keyed and displayed by Siweb variant id, not SKU (FR-018, project rule 5).
4. Forecast runs record parameter versions but not the demand-exclusion and censoring-rule versions (FR-008).
5. No admin-readable policy audit view, no "default vs saved" source display, and no test proving a UI change alters the next calculation (FR-013, FR-005, SC-001); the existing browser tests mock the whole backend.

No new service, table family or always-on resource is added; changes extend the three services that already own the data (procurement, inventory, forecast), the BFF and the web app.

## Technical Context

**Language/Version**: Python 3.12 (services, FastAPI), TypeScript with React (web app)

**Primary Dependencies**: FastAPI, SQLAlchemy 2 and Alembic, Pydantic, existing `mmi_common` helpers (`error_code`, `redact`), React with the existing es-ES i18n catalogue and shared table and form components

**Storage**: PostgreSQL, one schema per service; procurement owns `policy_sets`, `budget_caps`, `stocking_settings`, `policy_override_requests`; inventory owns demand exclusions, censoring rules, criticality; forecast owns `forecast_parameters` and run records. No cross-schema SQL.

**Testing**: pytest per service (unit, contract, PostgreSQL integration), `python -m gates run` for contract changes, Playwright for the Spanish UI. Synthetic fixtures from `packages/testing` only.

**Target Platform**: Azure Container Apps (scale to zero), static web app behind the BFF

**Project Type**: web application with multi-service backend

**Performance Goals**: preview over the full synthetic catalogue within 5 s or visible progress (SC-008); screen requests under 2 s

**Constraints**: shared budget EUR 120/month, no always-on service, no ERP request from any policy action, money as `Decimal`, UTC timestamps, es-ES only

**Scale/Scope**: about 2,000 products, a handful of users (owner, buyers, approver), tens of policy edits per month

## Constitution Check

*GATE: passed before Phase 0; re-checked after Phase 1 design — still passes.*

| Principle | Assessment |
|-----------|------------|
| I. Least-privilege integrations | Pass. No Siweb call is added; policies stay local (FR-022). A test asserts no outbound ERP request from any policy action. |
| II. Privacy and synthetic data | Pass. Synthetic fixtures only; exclusion reasons use a pick list plus limited admin-only detail and never put free text in the audit payload (research D7). |
| III. Explainable, human-controlled purchasing | Pass. Policies only configure inputs; proposals still need a human approver; explanations cite scope and revision (FR-004). |
| IV. Contract-first | Pass with work: schema changes (`policy_set`, `budget_cap`, `demand_rule`, error codes) go to `packages/contracts` first and through Agent 00; `python -m gates run` before the PR. |
| V. Testable, observable, cost-bounded | Pass. API-backed end-to-end tests are added; no new always-on resource. |
| Additional constraints (Decimal, UTC, SKU, es-ES, quarantine) | Pass. The SKU gap is closed by D3; no data is dropped silently (orphaned policies are flagged, D6). |

No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/011-business-policy-configuration/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── policy-console.delta.md
├── checklists/requirements.md
└── tasks.md              # created by /speckit-tasks
```

### Source Code (repository root)

```text
packages/contracts/
├── dto/{policy_set,budget_cap,demand_rule,forecast_parameter}.v1.schema.json   # revision, source, sku fields
└── errors/error_codes.json                                                    # new stable keys

services/procurement-service/
├── src/policies/service.py        # budget revision check, overlap refusal, source/default resolution, orphan flag
├── src/api/policies.py            # If-Match on budget caps, effective-policy view, audit read
├── migrations/versions/0013_*.py  # budget cap revision uniqueness
└── tests/                         # test_budget_concurrency, test_policy_source_view, test_policy_audit_read, test_policy_effect

services/inventory-service/
├── src/api/demand_rules.py        # revision on rules and exclusions
├── src/projections/rules.py       # version identifiers exposed to the series export
└── tests/

services/forecast-service/
├── src/runs/runner.py             # record exclusion and censoring-rule versions next to parameter versions
├── migrations/versions/           # nullable rule_version_ids column
└── tests/

services/api-bff/
├── src/routes/policies.py         # require_fresh_mfa on budget and global writes; SKU-to-id resolution; audit read route
└── tests/test_policies_rbac.py    # extended: MFA, refusal audit, SKU

apps/web/
├── src/features/policies/         # source badges, audit view, SKU picker, MFA prompt, conflict display
├── src/i18n/es-ES.json
└── tests/e2e/policies-live.spec.ts  # API-backed journeys (no page.route mock of the policy endpoints)
```

**Structure Decision**: extend the existing services and screens in place; the BFF keeps orchestration only. Each service keeps its own schema and migration chain.

## Delivery Order

1. Contracts and error keys (Agent 00 note), then migrations.
2. Tests first per story, then fixes: concurrency and MFA (story 2), effect on the next calculation (story 1), budgets and criticality (story 3), exclusions, censoring and parameters (story 4), source and history views (story 5).
3. Spanish UI changes and API-backed browser journeys, screenshots for the PR.
4. Gates, then a PR with migration impact and known limitations. No deploy, no merge, no ERP write.

## Complexity Tracking

None.
