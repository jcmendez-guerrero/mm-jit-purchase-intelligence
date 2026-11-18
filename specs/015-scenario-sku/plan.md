# Implementation Plan: SKU in scenario changes and result lines

**Branch**: `claude/speckit-mmi-15-spec-724de9` | **Date**: 2026-11-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/015-scenario-sku/spec.md`

## Summary

Add a nullable `sku` next to `variant_id` in each scenario change and each scenario result line, so the scenarios screen shows the SKU and never the Siweb variant id. The SKU is looked up when a scenario is read, in procurement, from `product_refs` using the existing `sku_for_variant` helper. Nothing stored changes: old scenarios work, the result hash is untouched, and the optimiser is not touched. Order: schema, contract tests, procurement read path, web screen, baseline entry removed.

## Technical Context

**Language/Version**: Python 3.12, pinned `>=3.12,<3.13` in each `pyproject.toml` (procurement-service, api-bff, contracts); TypeScript/React (apps/web)

**Primary Dependencies**: FastAPI, SQLAlchemy Core, Pydantic models generated from JSON Schema; no new dependency

**Storage**: Existing procurement tables only (`scenario_results.lines` JSON, `scenarios.summary` JSON, `product_refs.sku`); no migration

**Testing**: pytest (procurement, api-bff, contracts), Vitest (web unit incl. variant-id display test), `python -m gates run` from `scripts/`

**Target Platform**: Existing Azure Container Apps services; no infrastructure change

**Project Type**: Multi-service web application (gateway + domain services + web app)

**Performance Goals**: A 200-line scenario opens within 0.5 s of today (SC-004): one batched SKU lookup per read, not one query per row

**Constraints**: Contract-first (rule 9); gateway does no arithmetic and no resolution (ADR-023); no Siweb request; synthetic fixtures only; es-ES strings from the catalogue

**Scale/Scope**: About 2,000 active SKUs; scenarios of up to a few hundred lines; 2 DTO schemas, 1 read path, 1 screen (2 places)

## Constitution Check

*GATE: passes before research and after design.*

| Principle | Result |
|-----------|--------|
| I. Least-privilege integrations | Pass: no ERP request, no new write; read-only enrichment from local data |
| II. Privacy and synthetic data | Pass: SKU is catalogue data, no free text; tests use `packages/testing` fixtures |
| III. Explainable, human-controlled purchasing | Pass: only identifies products in explanations; no decision or approval changes |
| IV. Contract-first boundaries | Pass, with the gate question in research R3: schema first, generated types follow, matrix entry through Agent 00 |
| V. Testable, observable, cost-bounded | Pass: contract, API and web tests listed; no new infrastructure or cost |

No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/015-scenario-sku/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/scenario-sku.delta.md
├── checklists/requirements.md
└── tasks.md            # created by /speckit-tasks
```

### Source Code (files this feature touches)

```text
packages/contracts/
├── dto/scenario_result.v1.schema.json     # line `sku`
├── dto/scenario.v1.schema.json            # change `sku` (summary.changes)
├── python/mmi_models/dto/                 # regenerated
├── baseline/dto/                          # per gate policy (R3)
└── tests/test_mmi002_contracts.py         # sku / null / missing cases
docs/architecture/integration/contract-matrix.json   # via Agent 00
services/procurement-service/
├── src/scenarios/store.py                 # get(): add sku to changes and lines
└── tests/test_scenarios_api.py            # sku, null sku, old scenario, hash unchanged
services/api-bff/                          # pass-through only; confirm no field filter
apps/web/
├── src/features/scenarios/ScenariosScreen.tsx
├── src/api/client.ts                      # types
├── src/i18n/es-ES.json                    # "no SKU" marker if absent
└── tests/unit/variant-id-display.baseline.json   # remove scenarios entry
```

**Structure Decision**: Existing layout. The only logic lives in procurement's `store.get`; every other change is schema, types, tests and the screen.

## Complexity Tracking

None.
