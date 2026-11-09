# Implementation Plan: Architecture, Contracts & Integration (MMI 003 / Agent 00)

**Branch**: `claude/speckit-specification-ad04eb` | **Date**: 2026-11-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-architecture-contracts-integration/spec.md`

## Summary

Agent 00 does not add product features. It produces the coordination layer for the parallel MMI-1 effort: an evidence-based audit of main, a machine-checked contract matrix with frozen interface versions, ADRs, an integration plan, and a gate runner that reports pass/fail/not-run for six gates: contracts, schema isolation, integration status, end-to-end (including a real-services Spanish UI journey), security and cost. The gate report is saved as a CI artifact and summarized as a comment on each domain PR so agents can watch and auto-fix their own PRs. Approach: keep the artifacts as versioned files in the repo (JSON for machines, Markdown for people), reuse the existing contract tooling, tests and CI jobs, and add a small stdlib-only Python package (`scripts/gates`) that wraps them and emits one JSON report. Integration happens on a temporary local branch built from the domain PRs in documented order; Agent 00 never merges to main.

## Technical Context

**Language/Version**: Python 3.12 (gate runner and tooling), TypeScript for the existing web app (only its Playwright tests are invoked)

**Primary Dependencies**: Standard library plus what the repo already uses (pytest, jsonschema via `packages/contracts`, Playwright in `apps/web`, Bicep CLI). No new third-party dependency.

**Storage**: Files in the repository only. Gate reports are build artifacts, not persisted data. The schema-isolation gate reads SQL/migration files, never a live database; the existing PostgreSQL migration test covers the live check.

**Testing**: pytest (unit for the gate runner, contract tests), existing `infra/tests` (security, cost, e2e, migrations), `packages/contracts/tests`, Playwright for the Spanish UI. Synthetic fixtures from `packages/testing` only.

**Target Platform**: Developer machines and the existing GitHub Actions `ci.yml`; no new cloud resource.

**Project Type**: Monorepo tooling and documentation (no new deployable service).

**Performance Goals**: No fixed limit for the full gate run yet; the first run is timed and recorded in the PR and a limit is set from it (SC-008). Matrix and audit lookups are plain file reads (SC-007).

**Constraints**: Public repo, synthetic data only, no secrets, no ERP access, es-ES for anything user-facing (this feature has none besides test assertions), English engineering docs, cost within shared EUR 120/month (the feature adds no resources).

**Scale/Scope**: 6 services, about 40 shared schemas and events, 4 earlier feature specs, an unknown number of sibling agent PRs (MMI-1 children).

## Constitution Check

*Constitution v1.3.0. Gate: must pass before Phase 0 and again after Phase 1.*

| Principle | Assessment |
|-----------|------------|
| I. Least-privilege integrations | Pass. The feature performs no ERP call; the existing allowlist tests (`infra/tests/test_erp_boundary.py`) are run as part of the security gate and are not modified. |
| II. Privacy and synthetic data | Pass. Audit, matrix and reports contain file paths and identifiers of code only. The gate runner and the CI export-signature check refuse real-shaped data. |
| III. Human-controlled purchasing | Pass. Nothing here approves or writes purchases. Agent auto-fix is limited to the agents' own files and never merges (FR-010a). |
| IV. Contract-first service boundaries | Pass and reinforced. Contract matrix entries are derived from `packages/contracts`; versions follow the existing `vN` file suffix and baseline check; breaking changes add a new version (FR-005). |
| V. Testable, observable, cost-bounded | Pass. Every gate has a test; the cost gate reuses `test_cost_guardrails.py`; no new infrastructure. |
| Workflow: shared schema changes need contract tests and compatibility review | Pass. Enforced by the contract gate. |
| Workflow: no production deploy without approval | Pass. Out of scope (FR-017). |

No violations; Complexity Tracking is empty. Re-check after Phase 1: still passes (the design adds files and one stdlib package only).

## Project Structure

### Documentation (this feature)

```text
specs/005-architecture-contracts-integration/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── contract-matrix.schema.json
│   ├── feature-status.schema.json
│   ├── integration-plan.schema.json
│   ├── gate-report.schema.json
│   └── gate-runner-cli.md
└── tasks.md              # created by /speckit-tasks
```

### Source Code (repository root)

```text
docs/architecture/
├── adr/                          # new: one file per cross-domain decision
├── integration/
│   ├── feature-status.json       # audit result (validated by feature-status schema)
│   ├── feature-status.md         # rendered view
│   ├── contract-matrix.json      # owners, versions, consumers, status
│   ├── contract-matrix.md        # rendered view
│   └── integration-plan.json     # ordered domain PRs, prerequisites, verification
scripts/
├── gates/                        # new stdlib-only package
│   ├── __main__.py               # `python -m gates`
│   ├── validate.py               # artifacts vs schemas, schema-copy equality, plan checks (cycles, overlapping owners)
│   ├── audit_check.py            # audit evidence checker and Markdown view
│   ├── guarantees.py             # platform guarantee to test map
│   ├── matrix.py                 # contract matrix generation and Markdown view
│   ├── contracts_gate.py         # matrix vs packages/contracts, version/baseline, gateway endpoints
│   ├── isolation_gate.py         # static scan: no cross-schema SQL
│   ├── integration_gate.py       # every plan step integrated, or dropped with a reason
│   ├── suite_gate.py             # wraps existing pytest/Playwright suites (e2e, security, cost)
│   ├── report.py                 # gate-report JSON + exit code (not-run blocks)
│   ├── summary.py                # Markdown summary of a report for the PR comment
│   └── integrate.py              # build temporary integration branch, drop failing PRs + dependents
└── tests/                        # existing folder; add tests for scripts/gates
services/api-bff/                 # gateway (the "gateway" in the spec): shared contract + cross-domain tests only
infra/tests/                      # cross-domain integration tests added here
apps/web/tests/live/              # new real-services Spanish UI journey (compose stack, synthetic data)
.github/workflows/ci.yml          # added per-PR job: validate, contracts and isolation gates (required)
.github/workflows/integration-gates.yml  # new: all six gates on the integration branch; uploads the
                                  # gate report artifact and posts the summary as a comment on each domain PR
```

**Structure Decision**: Reuse the existing monorepo layout. Machine-readable artifacts live beside the existing architecture docs; the gate runner lives in `scripts/` next to the existing export-signature check and its tests. No new service or deployable.

## Complexity Tracking

No constitution violations to justify.
