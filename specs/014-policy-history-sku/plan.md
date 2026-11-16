# Implementation Plan: SKU in the policy history of the administration status

**Branch**: `claude/jira-mmi-14-spec-edc3ba` | **Date**: 2026-11-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/014-policy-history-sku/spec.md` (Jira MMI-14)

## Summary

The administration status screen lists policy-override history rows keyed by the Siweb `variant_id`. People must see the SKU instead (rule 5). Research ([research.md](research.md)) found that procurement already adds `sku` to every row it returns from `GET /policy-overrides` (`override_json`, feature 011), and the gateway forwards the card untouched. What is missing is the contract (the `PolicyOverrideRequest` schema has `additionalProperties: false` and no `sku`), a test that pins the field, and the web column that still prints `variant_id`. The plan is: schema first, procurement test, gateway pass-through test, web column and Spanish copy, baseline entry removed. No new service logic, no migration, no Siweb call.

## Technical Context

**Language/Version**: Python 3.12 (procurement-service, api-bff, contracts), TypeScript with React (apps/web)

**Primary Dependencies**: FastAPI, SQLAlchemy Core, pytest, jsonschema, the contracts codegen (`packages/contracts/codegen.toml`), Vitest

**Storage**: Existing `product_refs.sku` in the procurement schema; no change

**Testing**: pytest (contracts, procurement, api-bff), Vitest (web unit, including the variant-id display baseline and i18n coverage)

**Target Platform**: Existing Azure Container Apps services and the web app

**Project Type**: Multi-service web application (contract change plus two services plus web)

**Performance Goals**: Status screen opens within +0.5 s of today with 200 history rows (SC-004); the SKU lookup is the one already done per row

**Constraints**: Additive contract; the gateway does no resolution or money arithmetic (ADR-023); es-ES only; synthetic fixtures only; no Siweb request

**Scale/Scope**: The card shows at most 20 rows; the list size is the existing override queue

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Note |
|-----------|---------|------|
| I. Least-privilege integrations | Pass | No new integration, no Siweb request, admin guard unchanged |
| II. Privacy and synthetic data | Pass | SKU is catalogue data; no notes or personal data; fixtures synthetic |
| III. Explainable, human-controlled purchasing | Pass | Read-only display change; no write or approval path touched |
| IV. Contract-first service boundaries | Pass | Schema edited first, generated model regenerated, matrix entry through Agent 00 |
| V. Testable, observable, cost-bounded | Pass | Contract, service, gateway and web tests listed; no new infrastructure or cost |

Post-design re-check: still Pass; nothing to justify.

## Project Structure

### Documentation (this feature)

```text
specs/014-policy-history-sku/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── policy-history-row.delta.md
├── checklists/requirements.md
└── tasks.md              # created by /speckit-tasks
```

### Source Code (repository root)

```text
packages/contracts/
├── dto/policy_override_request.v1.schema.json                    # add sku (first change)
├── python/mmi_models/dto/policy_override_request_v1_schema.py    # regenerated
└── tests/test_mmi002_contracts.py                                # sku cases

services/procurement-service/
├── src/policies/service.py            # sku_for_variant: blank SKU returns None
└── tests/test_policy_api_011.py       # list returns sku; unknown product gives null

services/api-bff/
└── tests/                             # policy_history card passes sku through unchanged

apps/web/
├── src/api/client.ts                  # policy_history row type: add sku
├── src/features/admin/AdminStatusScreen.tsx   # column shows sku, marker when null
├── src/i18n/es-ES.json                # column header and "not applicable" marker
└── tests/unit/variant-id-display.baseline.json   # remove the AdminStatusScreen entry

docs/architecture/integration/contract-matrix.json   # through Agent 00: note on the changed row
```

**Structure Decision**: Edit the existing files above; no new modules. Run `python -m gates run` from `scripts/` before the PR because a schema in `packages/contracts` changes.

## Complexity Tracking

No constitution violations; nothing to justify.
