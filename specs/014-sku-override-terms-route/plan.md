# Implementation Plan: SKU Route for Product-Supplier Overrides

**Branch**: `claude/mmi-16-spec-implement-139980` | **Date**: 2026-11-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/014-sku-override-terms-route/spec.md` (Jira MMI-16)

## Summary

Replace the variant-id route for the product-supplier terms with a SKU route, `/product-suppliers/{sku}/{supplier_id}/terms` (read and save). Procurement resolves the variant id from the synced catalogue with the helper feature 011 already uses (`variant_for_sku`) and never returns it; the gateway forwards. Stored records, versions and idempotency keys stay keyed by variant id internally, so existing data stays reachable by SKU. The app has no production data, so the old route is deleted in the same change (one-step rename, as PR 22 did) and the override screen moves to the SKU with it. Schema and matrix entries come first (rule 9).

## Technical Context

**Language/Version**: Python 3.13 (FastAPI services), TypeScript only for generated types
**Primary Dependencies**: FastAPI, SQLAlchemy Core, pytest; JSON Schema codegen in `packages/contracts`
**Storage**: existing procurement tables (override history, `product_refs`); **no migration**
**Testing**: pytest in `services/procurement-service/tests` and `services/api-bff/tests`; contract tests in `packages/contracts/tests`; synthetic fixtures only
**Target Platform**: Azure Container Apps (scale to zero); no new resource
**Project Type**: web-service (gateway + domain service)
**Performance Goals**: one extra indexed lookup by SKU per request; no measurable change
**Constraints**: no variant id in the route's requests, responses, audit entries (saved and refused) or logs; behaviour otherwise identical to before
**Scale/Scope**: 2 routes renamed in procurement and in the gateway, 1 new response schema, 1 web screen, ~5 test files

## Constitution Check

| Principle (v1.3.0) | Result |
|--------------------|--------|
| I. Least-privilege integrations | Pass. No ERP request; no connector or writer change. |
| II. Privacy and synthetic data | Pass. Synthetic SKUs only; no notes or personal data touched. |
| III. Human-controlled purchasing | Pass. Same buyer-only save, same `If-Match`; no autonomous write. |
| IV. Contract-first service boundaries | Pass. Schema and matrix entries before code; no cross-schema SQL (procurement reads its own `product_refs`). |
| V. Testable, observable, cost-bounded | Pass. Tests first; no new resource, no cost change. |
| Rule 5 (SKU for people) | This feature closes the last known gap on these two routes and on the override screen. |
| ADR-023 (no money arithmetic in the gateway) | Pass. The gateway only forwards. |

No violations; Complexity Tracking not needed. Re-checked after design: unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/014-sku-override-terms-route/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── sku-override-terms-route.md
│   └── override_terms_view.v1.schema.json   # draft; moves to packages/contracts/dto when implemented
└── tasks.md            # created by /speckit-tasks
```

### Source Code (repository root)

```text
packages/contracts/
├── dto/override_terms_view.v1.schema.json        # new response schema (no variant_id)
├── baseline/dto/override_terms_view.v1.schema.json
├── python/mmi_models/dto/…                       # generated
└── tests/                                        # contract test for the new schema
apps/web/src/api/generated/dto/…                  # generated types only (no screen change)

services/procurement-service/
├── src/api/terms.py                              # routes now take the SKU; old variant-id routes deleted
├── src/terms/overrides.py                        # save_override takes an optional audit label (the SKU)
├── src/api/refusals.py                           # refusal target uses the SKU
└── tests/test_terms_sku_014.py                   # new

services/api-bff/
├── src/routes/api.py                             # the two routes now take the SKU
├── src/clients/procurement.py                    # the two calls now take the SKU
└── tests/test_terms_sku_014.py                   # new; plus update old tests, matrix and idempotency-recorded-routes tests

apps/web/
├── src/api/client.ts                             # getOverrideTerms / putOverrideTerms take a SKU; OverrideView has sku
├── src/features/suppliers/OverrideEditor.tsx     # asks for the SKU
├── tests/unit/glossary.test.ts                   # KNOWN_EXCEPTIONS entry removed
├── tests/unit/variant-id-display.baseline.json   # entry removed
└── tests/e2e/suppliers-*.spec.ts                 # follow the SKU

docs/architecture/integration/contract-matrix.json   # two entries renamed to {sku} (via Agent 00 note)
specs/014-…/agent-00-contract-note.md                # note for Agent 00
packages/contracts/errors/ , apps/web/src/i18n/es-ES.json   # unchanged: sku_unknown, sku_ambiguous already exist
```

**Structure Decision**: Edit the existing procurement `terms.py` and gateway `api.py` in place; no new module. Only the override screen moves in the web app; the other screens of feature 012 T050 are untouched.

## Decisions taken

- **Path**: one-step rename to `/product-suppliers/{sku}/{supplier_id}/terms`; the old route is deleted now (owner: no production data). See [research.md](research.md) D1.
- **Overlap with feature 012 T050**: the override screen is changed here; if PR 24 lands first, take its version of `OverrideEditor.tsx` and keep only what is missing.
