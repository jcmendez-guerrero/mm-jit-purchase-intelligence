# Implementation Plan: Predictive Seed Import and Dataset Governance (MMI-7)

**Branch**: `claude/mmi-7-specification-c0756a` | **Date**: 2026-11-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-mmi-7-predictive-seed-import/spec.md`

## Summary

Feature 002 (user story 5, ADR-020) already delivered most of the seed pipeline and its tasks are marked done. This plan therefore **audits that baseline and closes the gaps** instead of rebuilding it. The audit ([research.md](research.md)) found upload, parsing, mapping, validation, quarantine, dry run, activation, rollback and background jobs present, and these gaps against the spec:

1. Rows are keyed by a user-supplied `variant_id`, not by SKU (FR-007, AGENTS rule 5).
2. Activation and rollback in the gateway do not require fresh multi-factor authentication, and activation has no approver-is-not-the-creator check (FR-016, FR-019).
3. Rollback takes no reason (FR-019).
4. No guard against two concurrent activations or rollbacks (edge case).
5. Several behaviours are unproven by a test or screen: "not assessable" in the dry run, retired-SKU handling, separation from feature 004 data, explanation text, the import status section, and an end-to-end flow in the Spanish interface showing the forecast changing and returning.

Approach: small additive changes in the forecast service (owner of seed data) and the gateway, one migration, additive contract changes, changes to the existing import screen, and tests that prove each acceptance criterion with synthetic data.

## Technical Context

**Language/Version**: Python 3.12 (services), TypeScript with React (web app)

**Primary Dependencies**: FastAPI, SQLAlchemy 2, Pydantic models generated from JSON Schemas in `packages/contracts`; existing modules in `services/forecast-service/src/seeds/`. No new dependencies.

**Storage**: PostgreSQL, forecast service schema (`seed_datasets`, `seed_rows`, `seed_quarantine`, `seed_mappings`, `import_jobs`); private blob container for original files (exists).

**Testing**: pytest (unit, contract, PostgreSQL integration, abuse), Vitest, Playwright; synthetic fixtures from `packages/testing`.

**Target Platform**: Existing Azure container apps and scale-to-zero worker job; local compose for development.

**Project Type**: Web application (single-page app, gateway, services).

**Performance Goals**: SC-004 and SC-006: 1,000-product import to activation under 15 minutes, rollback under 2 minutes, hard-cap file validated within 5 minutes.

**Constraints**: In-request validation up to 10,000 rows, queued up to 50,000 (feature 002); no always-on compute; shared budget about EUR 120 per month; Spanish only; no ERP write.

**Scale/Scope**: Files of a few tens of thousands of rows; one active dataset at a time.

## Constitution Check

| Principle | Assessment |
|-----------|------------|
| I. Least-privilege integrations | Pass. No Siweb request added; SKU resolution uses the synchronised catalogue; seed data never sent to Siweb. |
| II. Privacy and synthetic data | Pass. Synthetic fixtures; free text, tax ids and personal data discarded at load. |
| III. Explainable, human-controlled purchasing | Pass, strengthened: second approver, fresh multi-factor authentication, explanations name dataset and version. |
| IV. Contract-first boundaries | Pass. Schemas change first (additive); no cross-schema SQL. |
| V. Testable, observable, cost-bounded | Pass. Tests cover security, data quality, retries and duplicates; no new infrastructure. |

No violations. Re-check after design: unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/008-mmi-7-predictive-seed-import/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/seed-governance.delta.md
├── checklists/requirements.md
└── tasks.md              # later, /speckit-tasks
```

### Source Code (repository root)

```text
services/forecast-service/
├── migrations/versions/        # new: SKU column, approval and rollback-reason columns
├── src/seeds/validation.py     # SKU matching replaces variant_id input
├── src/seeds/parsers.py        # refuse ERP-export header shapes before parsing rows
├── src/seeds/lifecycle.py      # two-person rule, rollback reason, row locking
├── src/seeds/dryrun.py         # "not assessable" listing (verify, add if missing)
├── src/runs/seeds.py           # retired-SKU skip and report (verify, add if missing)
├── src/imports_api.py          # fields and error keys
└── tests/
services/api-bff/src/routes/imports.py   # fresh-MFA on activate and rollback; pass reason
services/inventory-service/              # only if series items lack sku: additive field (coordinated with Agent 00)
services/procurement-service/            # explanation line only: dataset id and version (feature 002 owns the rest)
docs/adr/020-seed-provenance.md          # note on the audited owner self-activation
apps/web/src/features/imports/           # SKU template wording, rollback reason, approval and status states
apps/web/tests/{unit,e2e}/
packages/contracts/   packages/testing/
```

**Structure Decision**: Reuse the existing layout. The forecast service owns seed rules; the gateway forwards and applies role and multi-factor checks; no new service or infrastructure.

## Complexity Tracking

None.
