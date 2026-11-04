# Implementation Plan: Mundo Mascotix Intelligence — Inventory Intelligence & Weekly Purchasing Platform

**Branch**: `001-mmi-purchase-intelligence` | **Date**: 2026-11-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-mmi-purchase-intelligence/spec.md`

## Summary

Build an independent, Spanish-language inventory-intelligence and weekly-purchasing platform on
top of the Siweb360 ERP. Siweb is read through a closed GET allowlist; demand is derived from
stock movements; classification, intermittent-demand policies and backtests drive safety stock
per service-level segment; a deterministic constraint engine allocates needs across suppliers
(unit cost, combined order cost, lead time, delivery minimums, free-delivery thresholds); the
buyer edits, a different person approves, and the approved proposal is read by supplier or
exported (CSV/Excel). After the buyer confirms an order, the supplier cost (including recargo de
equivalencia) is written back to Siweb through the only permitted write, executed by a
separate, minimally privileged writer.

Technical approach (details in [research.md](research.md)): Python/FastAPI microservices with
per-service PostgreSQL schemas, React/TypeScript SPA behind a cookie-session BFF, Azure
Container Apps + Jobs, Storage Queues with outbox/inbox, JSON Schema contracts with generated
Pydantic/TS types, Bicep IaC, everything runnable locally with Docker Compose against a
synthetic-data Siweb mock.

## Technical Context

**Language/Version**: Python 3.12 (services, jobs); TypeScript 5.x / React 18 (SPA); SQL (PostgreSQL 16)

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic (per service), httpx, Polars + DuckDB (analytics jobs only), statsmodels/numpy/scipy (intermittent-demand policies, no heavy ML), OR-Tools CP-SAT (supplier allocation), azure-storage-queue / azure-storage-blob / azure-identity SDKs behind interfaces, Vite + React Router + TanStack Query + i18next (SPA), openpyxl (Excel export), datamodel-code-generator + json-schema-to-typescript (codegen)

**Storage**: Existing Azure PostgreSQL Flexible Server, dedicated `mmi` database, one schema + role + migration identity per service; Azure Blob (raw payloads, Parquet, snapshots); Azure Storage Queues; local: PostgreSQL + Azurite via Compose

**Testing**: pytest (+ hypothesis for money/allocation/classification invariants), schemathesis/JSON-Schema contract tests, Vitest + Testing Library + Playwright (UI, es-ES checks), Gitleaks/Trivy/pip-audit in CI

**Target Platform**: Azure Container Apps (Consumption) + Container Apps Jobs, scale-to-zero; Linux containers; modern desktop browsers

**Project Type**: Web application with multiple backend services (monorepo, microservices)

**Performance Goals**: Nightly sync completes inside a night window within ≤ 500 Siweb req/h; weekly proposal for ~1,000 variants generated in < 2 min; interactive pages respond < 1 s p95 for a team of < 10 users

**Constraints**: Shared Siweb limit 1,000 req/h (MMI ≤ 500 req/h, token bucket); shared EUR 120/month across all Mundo Mascotix workloads; read-only toward Siweb except supplier-cost PUT (constitution v1.1.0); public repository (no real data/IDs); es-ES only UI; no Azure credentials needed locally

**Scale/Scope**: ~1,000 variants, 3 warehouses + unassigned, ~9 months of synthetic movements for tests (real: < 6 months, a few thousand movements/month), < 10 users, ~15 buyer-facing screens

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Least-privilege integrations | Reader: host + GET path allowlist enforced before send. Writer: separate identity, separate deployable, allowlist of exactly `PUT /inventory/products/{id}/suppliers/{contact_id}`, buyer review, audit, visible retries. Token only in Key Vault; reader and writer identities get separate access policies | PASS (relies on v1.1.0 exception; see [contracts/siweb-allowlist.md](contracts/siweb-allowlist.md)) |
| II. Privacy & synthetic data | Synthetic generator + mock only; `supplier_cif` and `notes` dropped at the connector boundary; `has_note` flag only | PASS |
| III. Explainable, human-controlled purchasing | Decimal money, cost provenance/versioning, explanation per line, recorded inputs/rule versions, creator ≠ approver, fresh MFA; only the buyer-initiated cost write reaches Siweb | PASS |
| IV. Contract-first boundaries | JSON Schema in `packages/contracts` → Pydantic + TS; per-service schema/role/migrations; audience-scoped service identities; idempotent, schema-validated messages | PASS |
| V. Testable, observable, cost-bounded | Test strategy per boundary; metrics/alerts defined; reuse shared Azure resources; scale-to-zero; replica/job caps; budget alerts | PASS |
| Constraints | Bicep, monorepo, reuse DB/ACA/ACR/KV/Monitor; no real data in repo | PASS |

**Post-design re-check**: PASS. One justified addition recorded in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-mmi-purchase-intelligence/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── bff-api.openapi.yaml
│   ├── events.md
│   └── siweb-allowlist.md
├── checklists/requirements.md
└── tasks.md             # created later by /speckit-tasks
```

### Source Code (repository root)

```text
apps/
└── web/                              # React/TS SPA (es-ES, i18next), static hosting
    ├── src/{app,features,i18n,api}/
    └── tests/{unit,e2e}/

services/
├── siweb-connector/                  # ACA Job: read-only collection, raw→Blob, normalize, outbox
│   ├── src/{client,allowlist,ratelimit,sync,mapping,outbox}/
│   ├── migrations/                   # `integration` schema
│   └── tests/{unit,contract,integration}/
├── siweb-cost-writer/                # ACA app: ONLY the supplier-cost PUT; separate identity
│   ├── src/{allowlist,writer,audit}/
│   ├── migrations/                   # `costwrite` schema
│   └── tests/
├── inventory-service/                # catalogue, stock, lots, movements, demand series, ABC/XYZ
│   ├── src/{api,projections,demand,classification,quality}/
│   ├── migrations/                   # `inventory` schema
│   └── tests/
├── forecast-service/                 # Job: policies, backtests, eligibility
│   ├── src/{policies,backtest,runs}/
│   ├── migrations/                   # `forecasting` schema
│   └── tests/
├── procurement-service/              # costs, supplier terms, allocation, proposals, approval, orders
│   ├── src/{api,costs,terms,allocation,proposals,approvals,orders,audit}/
│   ├── migrations/                   # `procurement` schema
│   └── tests/
└── api-bff/                          # cookie-session BFF, RBAC, aggregation, no domain logic
    ├── src/{auth,routes,clients}/
    └── tests/

packages/
├── contracts/                        # JSON Schema (events, DTOs) + codegen config + compat tests
└── testing/                          # synthetic generator, Siweb mock, shared fixtures

infra/
├── bicep/{modules,main.bicep,*.bicepparam.example}
└── compose.yaml                      # Postgres, Azurite, mock Siweb, dev JWT issuer, all services

docs/{architecture,adr,runbooks}/
security/{threat-model-template.md,data-classification.md}   # method only, no findings
.github/workflows/                    # path-filtered CI, security scans, OIDC deploy
AGENTS.md  CLAUDE.md
```

**Structure Decision**: Monorepo with independently built and deployed services as in the architecture document. `recurrence-service` is omitted (deferred, needs a privacy assessment). `siweb-cost-writer` is added as a separate service so the write capability has its own identity, code path and allowlist (constitution Principle I).

## Delivery Phases and Story Mapping

| Phase | Scope | Spec stories | Gate |
|-------|-------|--------------|------|
| 0 Verify & decide | Live-API checks (timezone, `reference_type`, history depth, page sizes, 429s, PUT supplier-cost behaviour); confirm rate share; accountant (VAT sources); update ADRs | — | Findings recorded in internal wiki |
| 1a Foundation | Monorepo, contracts+codegen, synthetic generator, Siweb mock (incl. PUT), Compose, skeletons, CI, Bicep skeleton | 7 (local run) | `docker compose up --build` with zero Azure credentials; CI green |
| 1b Early capture | Connector job in Azure, allowlist, rate budget, raw→Blob, snapshots + movements | 1 | 7 clean nights; counts reconcile |
| 2 Integration | Full typed client, checkpoints, mappings, import errors, outbox events | 1 | 2 weeks clean reconciliation |
| 3 Demand | Demand provider, backward stock reconstruction, censoring, loss classification, ABC/XYZ, policies, backtests | 2, 3 | Per-SKU eligibility flag |
| 4 Procurement MVP | Cost sources (ERP/CSV/manual), recargo handling, supplier terms, allocation, proposals, approval, order confirmation, cost write-back, exports, es-ES UI | 4, 5, 6 | Buyer approves and uses a proposal unaided (shadow mode) |
| 5 Production | Entra roles + MFA, network review, restore drill, alerts, runbooks, shadow 4–8 weeks | 7 | Shadow results reviewed |

## Complexity Tracking

| Violation / Addition | Why Needed | Simpler Alternative Rejected Because |
|----------------------|------------|--------------------------------------|
| Extra service `siweb-cost-writer` (7th deployable) | Principle I requires the write to use separate identity/permissions and a one-operation allowlist; the shared token is full-scope | Keeping the write inside `siweb-connector` would give the nightly read job write capability and a larger blast radius if compromised |
| OR-Tools CP-SAT in this release (originally P2) | Spec FR-038 requires joint allocation over combined order cost, minimums and free-delivery thresholds | A greedy per-line cheapest-supplier rule cannot satisfy supplier minimums or threshold effects; kept as the explanation baseline and fallback |
