# Implementation Plan: MMI 004 — Local Test Data Loading and Supplier Management

**Branch**: `004-local-test-data-suppliers` | **Date**: 2026-11-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-local-test-data-suppliers/spec.md`; constitution v1.3.0.

## Summary

Two deliverables on the existing platform:

1. **A local-only way to run the whole pipeline on export-shaped data.** The owner's three UI exports (inventory CSV, movements XLSX, suppliers CSV) are parsed by a new local loader that lives in `packages/testing` (never built into a cloud image). Inventory, stock and movements are translated into the same Siweb-shaped payloads the Siweb mock already serves, with deterministic surrogate IDs derived from SKU, so the **unchanged** connector → inventory → forecast → procurement pipeline runs on them. Suppliers and product-supplier links are pushed through the procurement service's own supplier API. A synthetic generator mimics the three formats so every automated test uses fictional data.
2. **Supplier management in the product.** `procurement-service` gains supplier create / edit / deactivate / classify, product-supplier link management (single and bulk), and conditions that reuse the existing versioned `supplier_terms` and `product_supplier_terms`. The SPA gets the matching es-ES screens. A gated third part (ERP note block, constitution v1.3.0) is built behind a disabled flag until Gate 0 confirms the ERP operation.

## Technical Context

**Language/Version**: Python 3.12 (services, loader), TypeScript 5.6 / React 18 (SPA, existing), Node ≥ 20.

**Primary Dependencies**: Existing FastAPI, SQLAlchemy, Alembic, Pydantic generated from `packages/contracts`, `openpyxl` (already used for price lists), `react-i18next`. No new third-party dependency planned; hardened-parser checks are reused from the seed import (research R3).

**Storage**: PostgreSQL, per-service schemas. New migration `0011` in `procurement-service` only (supplier columns, link source). Loader state (SKU → surrogate-ID map, review report) lives in a gitignored folder under `data/`.

**Testing**: pytest (unit, contract, integration against compose), Vitest + Testing Library, Playwright + axe for the new screens, the existing i18n hard-coded-string test, plus a new repository-safeguard test and a cloud-configuration test.

**Target Platform**: Local Docker Compose for the loader and mock; Azure Container Apps for the supplier features (loader excluded).

**Project Type**: Web application inside the existing monorepo (services + `apps/web` + `packages/*`).

**Performance Goals**: Owner-size load (≈3,000 products, ≈1,700 movements, ≈60 suppliers; design headroom ×5) populates the dashboard in under 5 minutes end to end (SC-001).

**Constraints**: es-ES only, no hard-coded strings; Decimal money; UTC plus original timestamp text; synthetic data only in the repository; loader absent from cloud; ERP note write disabled until Gate 0; no new Azure resources.

**Scale/Scope**: One owner, a few staff users; ≈ 60 suppliers, ≈ 3,000 SKUs today.

## Constitution Check (v1.3.0)

*GATE: passes before Phase 0; re-checked after Phase 1 design (see end of research.md).*

| Principle / constraint | Assessment |
|---|---|
| I. Least-privilege integrations | **Pass, with a gate.** Cost write unchanged. The note-block write is built only as a disabled operation (path `TBD`, fails closed, no request built); enabling needs Gate 0 evidence and a recorded allowlist change. The loader never touches Siweb. |
| II. Privacy and synthetic data | **Pass.** Real files are read only from a gitignored folder by a local-only loader; committed fixtures are synthetic and signature-checked; tax ID, bank/IBAN and notes are dropped at parse time; the screen upload is mounted only with the local flag and refuses in prod. |
| III. Explainable, human-controlled purchasing | **Pass.** Supplier and link changes are versioned and audited; no auto-approval; bulk assignment previews before applying; deactivation shows affected open lines. |
| IV. Contract-first | **Pass.** New schemas (supplier, link, load result, conditions block) go into `packages/contracts` first; each service keeps its own schema; the loader talks to services only through their APIs and the mock, using audience-scoped local-issuer tokens (T089, T090, FR-039). |
| V. Testable, observable, cost-bounded | **Pass.** Tests precede implementation per story; new load and review counters; no new cloud resources or cost. |
| Additional constraints | **Pass.** Outbound allowlist unchanged in code (one write) until Gate 0; public repo stays synthetic; malformed data goes to review. |

No unjustified violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/004-local-test-data-suppliers/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── export-formats.md        # the three export layouts and mappings
│   ├── local-loader.md          # CLI, local HTTP and BFF local-load routes
│   ├── suppliers-api.md         # supplier / link / bulk-assignment endpoints
│   └── supplier-note-block.md   # app-owned block format and sync rules (disabled until Gate 0)
├── checklists/requirements.md
└── tasks.md                     # /speckit-tasks
```

### Source Code (repository root)

```text
packages/testing/
├── src/export_loader/               # NEW, local-only; never installed in a cloud image
│   ├── formats.py                   # header signatures and column maps
│   ├── parse_inventory.py           # CSV → products/variants/stock/lots + review items
│   ├── parse_movements.py           # XLSX → movements (Spanish type/reason → platform reasons)
│   ├── parse_suppliers.py           # CSV → suppliers (drops CIF, bank, notes)
│   ├── sku_map.py                   # SKU → stable surrogate IDs (persisted, gitignored)
│   ├── to_mock.py                   # builds the mock Dataset
│   ├── to_procurement.py            # suppliers and links via the procurement API
│   ├── report.py                    # loaded/updated/unchanged/quarantined/excluded counts
│   ├── cli.py                       # python -m export_loader load|check|wipe
│   └── app.py                       # local HTTP app used by the screen upload
├── src/generator/exports.py         # NEW: synthetic files in export format
├── src/siweb_mock/                  # + /__mock__/load (replace dataset); local only
├── fixtures/exports/                # NEW: committed synthetic files (SYN- prefixed SKUs)
└── tests/export_loader/

packages/contracts/                  # NEW schemas first: supplier, supplier_link, load_result, conditions_block
services/procurement-service/
├── migrations/versions/0011_suppliers.py
├── src/suppliers/                   # NEW: service.py, links.py, bulk.py, dedupe.py
└── src/api/suppliers.py
services/api-bff/
├── src/routes/suppliers.py          # NEW proxy routes
└── src/routes/local_load.py         # NEW; mounted only when MMI_LOCAL_LOADER=1 and MMI_ENV != prod
services/siweb-cost-writer/
└── src/writer/note_block.py         # NEW; merge logic only, no network path (disabled)
apps/web/src/features/suppliers/     # + SupplierForm, ConditionsEditor, LinksPanel, BulkAssign, SupplierImport
apps/web/src/features/localload/     # NEW; shown only when the BFF reports the capability
infra/compose.local-data.yaml          # override file with the loader and the flag; never referenced by Bicep
infra/tests/test_no_local_loader_in_cloud.py
scripts/check_export_signatures.py   # pre-commit and CI guard
```

**Structure Decision**: extend the monorepo. The loader sits in `packages/testing` because that package already holds every local-only synthetic tool (generator, Siweb mock, dev issuer) and is in no cloud image. Supplier management belongs in `procurement-service`, which already owns suppliers, terms, costs and links.

## Phased Delivery

The phases below are the same as in `tasks.md`.

| Phase | Content | Stories | Exit |
|---|---|---|---|
| 1. Setup | Ignore rules, loader package skeleton, compose override, test helpers | — | Skeleton builds |
| 2. Foundational | Contracts, OpenAPI, signature guard, file hardening, SKU map, report, synthetic export generator and fixtures, migration 0011, loader identities | US4 foundations | Same seed gives identical files; guard blocks a real-shaped file |
| 3. Local load | Parsers, mock load, CLI, loader app, BFF routes, screen, review sources, export costs, sync trigger, mixing guard | US1 | Synthetic load reconciles; dashboard populated locally |
| 4. Supplier management | Supplier model and API, conditions, links, bulk assignment, merge, deactivate, duplicate detection, SPA screens, SKU → ERP id resolution | US2 | Create supplier → link → proposal honours terms |
| 5. Supplier import | Supplier-file parser, internal import, automatic linking, classification, import screen | US3 | Customers excluded; duplicates listed |
| 6. Local-only guarantee | Cloud-absence, runtime guards, wipe, runbook, security events | US4 | SC-006 and SC-007 verified |
| 7. ERP note block (gated) | Note-block merge, discrepancy alerts, disabled operation, Gate 0 | FR-027–032 | Tests green; operation still disabled |
| 8. Polish | Documentation, full test run, quickstart walkthrough, security and performance review, signals, PR | — | All success criteria evidenced |

Phases 1–6 meet the immediate need and do not depend on Gate 0. Phase 7 is built but not enabled.

## Complexity Tracking

*No constitution violations to justify.*
