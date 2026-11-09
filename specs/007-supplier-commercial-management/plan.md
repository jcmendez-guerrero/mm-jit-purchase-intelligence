# Implementation Plan: Supplier Commercial Management (MMI-6)

**Branch**: `claude/speckit-specification-d01b1d` | **Date**: 2026-11-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/007-supplier-commercial-management/spec.md`

## Summary

Features 002 and 004 already implement most of the supplier commercial domain. The audit in [research.md](research.md) shows: append-only effective-dated terms with window validation, If-Match revision conflicts, product-level overrides, proposals that record terms versions, and supplier/link/bulk screens are **complete or largely complete**. The real work is closing four verified gaps and proving the rest:

1. **Idempotent term saves** (FR-014): missing for terms and overrides; add an `Idempotency-Key` to the two save endpoints.
2. **Audit of refused attempts** (FR-026, FR-028): successful saves are audited; refused ones (role, conflict, abuse) are not recorded.
3. **Currency equivalence** (FR-034 to FR-036): no EUR-rate rule exists in the code. Decided: the existing worker, about once a day, caches ECB reference rates from Frankfurter in a local table; allocation uses stored rates only; missing, unsupported or stale (over 7 days) rates exclude the supplier and raise a review item.
4. **Proof gaps**: delivery date from schedule and cutoff on proposals (US5-2), cost-provenance difference display (FR-016), terms-history and conflict UI states, and an end-to-end Playwright journey for the P1 stories.

No new service, table family or ERP interaction is introduced; changes stay inside `procurement-service` (own schema), the BFF passthrough, the contracts package and the suppliers feature of the web app.

## Technical Context

**Language/Version**: Python 3.12 services (FastAPI, SQLAlchemy Core, Alembic); TypeScript/React web app

**Primary Dependencies**: existing only; no new dependencies

**Storage**: PostgreSQL, procurement-service schema (`supplier_terms`, `product_supplier_terms`, `supplier_costs`, `audit_events`); one additive migration (idempotency record and exchange rates)

**Testing**: pytest (unit, API contract, PostgreSQL integration, abuse), Vitest unit, Playwright e2e; synthetic fixtures from `packages/testing` only

**Target Platform**: Azure Container Apps (scale to zero), local development with the local issuer

**Project Type**: web application (BFF + services + SPA)

**Performance Goals**: terms save and read under 300 ms p95 for a supplier with 50 versions; proposal generation not slower than current baseline (`tests/perf`)

**Constraints**: shared EUR 120/month; no always-on services; Spanish (es-ES) only; money as `Decimal`; UTC timestamps

**Scale/Scope**: tens of suppliers, thousands of links, tens of terms versions per supplier

## Constitution Check

*GATE: must pass before Phase 0; re-checked after Phase 1.*

| Principle / rule | Status | Note |
|---|---|---|
| I. Least-privilege integrations; ERP read-only except the two permitted writes | PASS (action) | No new ERP call or write; FR-023/FR-024 verified by existing `test_terms_no_erp.py` and `test_refuse_local_ids.py`. The new Frankfurter call is a separate, non-ERP integration: single host, single path, GET only, no credentials, no data sent, enforced and tested before any request (T036, T038) |
| Additional constraints: new exceptions need a documented decision and cost review | PASS (action) | ADR for the outbound rate dependency (T041); no new job: runs inside the existing scale-to-zero worker, about once a day |
| II. Privacy and synthetic data | PASS | Fixtures synthetic; no notes, tax ids or bank details stored |
| III. Explainable, human-controlled purchasing | PASS | Lines already carry a terms explanation; no autonomous writes |
| IV. Contract-first | PASS (action) | Idempotency header and refusal codes are added to `packages/contracts` first; coordinated with Agent 00 (FR-033) |
| V. Testable, observable, cost-bounded | PASS | Tests listed in quickstart; no new always-on resource |
| Money `Decimal`, UTC | PASS | Existing columns `MONEY`/timezone-aware |
| Spanish UI only, catalogue texts | PASS (action) | New messages go to `es-ES.json`; e2e checks no hard-coded text |
| Each service owns its schema; no cross-schema SQL | PASS | Only procurement schema touched |

No violations; Complexity Tracking is not needed. **Post-design re-check (Phase 1)**: unchanged, PASS.

## Project Structure

### Documentation (this feature)

```text
specs/007-supplier-commercial-management/
├── plan.md
├── research.md          # audit + decisions
├── data-model.md
├── quickstart.md
├── contracts/
│   └── supplier-terms-api.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
packages/contracts/                      # schemas first: Idempotency-Key, error codes, delivery-date field
packages/testing/                        # synthetic exchange-rate response fixture
services/procurement-service/
├── src/terms/service.py                 # idempotent save, refusal audit hook
├── src/terms/overrides.py               # idempotent override save
├── src/terms/schedule.py                # order date, cutoff and delivery date (pure)
├── src/api/terms.py                     # Idempotency-Key handling, refusal audit
├── src/api/suppliers.py                 # refusal audit for supplier/link changes
├── src/audit/chain.py                   # reused (record refusals)
├── src/fx/rates.py                      # daily ECB rate fetch via Frankfurter, allowlisted
├── src/proposals/inputs.py              # conversion from stored rates, exclusion, review item
├── src/approvals/workflow.py            # block approval of lines for deactivated suppliers
├── src/worker.py                        # schedule the daily rate job
├── src/locale/es-ES.json                # new messages
├── migrations/                          # additive: 0012 terms_idempotency + fx_rates
└── tests/                               # new files are listed per task in tasks.md (idempotency, refusal audit, delivery date, scenarios, fx rates, non-EUR, roles, persistence, deactivation, abuse, privacy, provenance, fallback)
services/api-bff/src/routes/api.py       # forward Idempotency-Key on the two terms PUT routes
services/api-bff/tests/                  # second-factor freshness test
docs/adr/                                # decision for the outbound rate dependency
apps/web/src/features/suppliers/         # history/conflict states, cost difference
apps/web/tests/e2e/                      # suppliers-terms-journey.spec.ts
```

**Structure Decision**: extend the existing web-application layout in place. The audit table in `research.md` is the deliverable for FR-001/FR-002; no separate audit tree.

## Complexity Tracking

None; no constitution violations.
