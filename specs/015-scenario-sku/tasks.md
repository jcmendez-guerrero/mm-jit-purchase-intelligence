---

description: "Tasks for SKU in scenario changes and result lines"
---

# Tasks: SKU in scenario changes and result lines

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/scenario-sku.delta.md](contracts/scenario-sku.delta.md), [quickstart.md](quickstart.md)

**Tests**: Included. The project rule is tests before implementation within a story. Synthetic fixtures from `packages/testing` only.

**Format**: `- [ ] T### [P?] [Story] description with path`. `[P]` means a different file with no dependency on an unfinished task.

## Phase 1: Setup

- [X] T001 Confirm with Agent 00 the contract question in research R3 (clarified: `sku` required and nullable; confirm the gate accepts it in v1, else v2) and record the answer in `specs/015-scenario-sku/research.md` Decided in this branch: required and nullable stays in v1 (the contracts gate accepts it); see research R3.
- [X] T002 Run `python -m gates run` from `scripts/` on the untouched branch to record the starting state

## Phase 2: Foundational (blocks all stories)

- [X] T003 Add `sku` (string or null, non-empty when a string) to the `lines[]` item, and add `sku` to its `required` list, in `packages/contracts/dto/scenario_result.v1.schema.json`
- [X] T004 Add the documented `summary.changes[]` item shape with `sku` to `packages/contracts/dto/scenario.v1.schema.json` (fields in the contract delta); `sku` is in `required`, and add the `summary` object to the schema if it is absent
- [X] T005 Regenerate the Python models in `packages/contracts/python/mmi_models/dto/` with the repo's codegen (`packages/contracts/codegen.toml`) and update `packages/contracts/baseline/dto/` per the T001 decision
- [X] T006 If T001 says the gate refuses a required field in v1, create `scenario_result.v2` and `scenario.v2` schemas, their baseline and generated models, bump the matrix entry, and check consumers; skip otherwise Skipped: v1 holds, no v2 needed.
- [X] T007 Register the change in `docs/architecture/integration/contract-matrix.json` through Agent 00 (owner `procurement-service`), at v1 or v2 per the T001 answer No new entry: `scenario` and `scenario_result` are already registered at v1 and the gate passes.
- [X] T008 Add a batch helper `skus_for_variants(conn, variant_ids) -> dict[int, str | None]` (one query on `product_refs`, trimmed, empty becomes null) next to `sku_for_variant` in `services/procurement-service/src/policies/service.py`

**Checkpoint**: schema and helper exist; stories can start.

## Phase 3: User Story 1 - Buyer reads a scenario by SKU (P1) 🎯 MVP

**Goal**: change rows and result lines carry the SKU and the screen shows it.

**Independent test**: open a synthetic scenario whose products have SKUs; every change row and line shows its SKU and no variant id.

### Tests (write first; the contract test T009 passes against the Phase 2 schema, the others fail until T013 to T016)

- [X] T009 [P] [US1] Contract tests in `packages/contracts/tests/test_mmi002_contracts.py` (they validate the Phase 2 schema, so they do not fail first): a line and a change with a SKU validate; with `sku: null` validate; empty-string `sku` and a missing `sku` are rejected
- [X] T010 [P] [US1] Procurement test in `services/procurement-service/tests/test_scenarios_api.py`: `GET /scenarios/{id}` returns the catalogue SKU on every change and every line; same product gives the same SKU across two scenarios; no Siweb call is made and every pre-existing field is unchanged (FR-010, FR-011)
- [X] T011 [P] [US1] Unit test for `skus_for_variants` in `services/procurement-service/tests/test_policy_safety_011.py` (batch result matches `sku_for_variant`; one query)
- [X] T012 [P] [US1] Web unit test in `apps/web/tests/unit/` (new `ScenariosScreen.sku.test.tsx`): change rows and line table render the SKU and never `#variant_id`

### Implementation

- [X] T013 [US1] In `services/procurement-service/src/scenarios/store.py` `get()`, collect variant ids from `summary.changes` and `results[].lines`, call `skus_for_variants` once, and add `sku` to each change and line (do not touch `_persist`, `result_hash` or the stored JSON; add no Siweb call and keep every existing field, asserted in T010)
- [X] T014 [US1] Confirm `services/api-bff/src/routes/scenarios.py` passes the field through; add or extend an api-bff test in `services/api-bff/tests/` and check `test_routes_do_no_money_arithmetic` still passes
- [X] T015 [P] [US1] Add `sku: string | null` to the scenario change and line types in `apps/web/src/api/client.ts`
- [X] T016 [US1] Show the SKU in the change rows (around line 218) and the line table (around line 259) of `apps/web/src/features/scenarios/ScenariosScreen.tsx`; keep `variant_id` only as a React key
- [X] T017 [US1] Remove the `src/features/scenarios/ScenariosScreen.tsx` entry from `apps/web/tests/unit/variant-id-display.baseline.json` and make `no-variant-id-display.test.tsx` pass

**Checkpoint**: US1 works alone; quickstart steps 1 to 4 pass.

## Phase 4: User Story 2 - Items without a resolvable SKU stay readable (P2)

**Goal**: null SKUs never hide a row or break a scenario, including scenarios created before this change.

**Independent test**: a scenario with one product lacking a SKU is ready, lists the row with the marker, and totals are unchanged.

### Tests

- [X] T018 [P] [US2] Procurement tests in `services/procurement-service/tests/test_scenarios_api.py`: product with no `product_refs` row, null SKU, and whitespace SKU all give `sku: null`; row counts equal stored counts; also a change present only before or only after, and an infeasible scenario, still carry SKUs
- [X] T019 [P] [US2] Procurement test in `services/procurement-service/tests/test_scenarios_determinism.py`: a scenario stored without SKUs returns SKUs on read with identical `result_hash`, totals and status Covered in `test_scenarios_api.py` (same fixture), not in the determinism file.
- [X] T020 [P] [US2] Web unit test in `apps/web/tests/unit/ScenariosScreen.sku.test.tsx`: a null SKU shows the Spanish marker and the row stays listed

### Implementation

- [X] T021 [US2] Ensure the helper and `get()` in `store.py` return null (never blank, never dropped) for unresolved products, including surrogate ids from 9,000,000 (covered by T018)
- [X] T022 [P] [US2] Add the "no SKU" marker and its accessible label to `apps/web/src/i18n/es-ES.json` if no existing key fits (reuse one first) Reused the existing key `dashboard.drill.no_sku` ("Sin SKU"); no new key.
- [X] T023 [US2] Render the marker for null SKUs in `ScenariosScreen.tsx` (change rows and line table)

**Checkpoint**: US1 and US2 pass together.

## Phase 5: User Story 3 - Contract and guardrails reflect the change (P3)

**Goal**: the gate and the contract tests protect the new field.

**Independent test**: the contract gate and the display test pass with the baseline entry gone.

- [X] T024 [US3] Confirm T009 covers the SKU, null, empty and missing cases for both the line and the change; add any case it lacks in `packages/contracts/tests/test_mmi002_contracts.py`
- [X] T025 [US3] Run `python -m gates run` from `scripts/`; fix any baseline or matrix finding
- [X] T026 [US3] Final confirmation only: after T017, the baseline has no scenarios entry and the full web unit suite passes Only the scenarios entry went; the AdminStatus and Quality entries stay for MMI-14 and MMI-13.

## Phase 6: Polish

- [X] T027 Run the procurement scenario suite (`services/procurement-service/tests/test_scenarios_*.py`) to confirm determinism, export, compare and promote are unaffected
- [ ] T028 Measure opening a 200-line synthetic scenario against SC-004 (no more than 0.5 s slower)
- [ ] T029 Walk through [quickstart.md](quickstart.md) end to end and tick the completed tasks in this file
- [X] T030 Note in `specs/012-ux-navigation-localization/tasks.md` that the scenarios screen of T054 is done (T054 covers six screens, so leave it open), and update the owner request 3 note in `specs/012-ux-navigation-localization/evidence/owner-requests.md`

## Dependencies and order

- Phase 1 then Phase 2, then US1. T001 gates T003 to T007 (v1 or v2 decides which schema files are edited, the baseline and the matrix entry). US2 builds on the US1 read path (T013). US3 can start after Phase 2 and finishes last.
- Within a story: tests, then implementation.
- Parallel: T009 to T012; T015 with T013; T018 to T020; T022 with T021.

## Implementation strategy

- **MVP**: Phases 1, 2 and 3 (SKU shown for products that have one).
- Then US2 (null handling and old scenarios), then US3 (gate), then polish.
- Only the owner of procurement and Agent 00 can merge schema changes; run the gate before the PR.

## Phase 7: Convergence

- [X] T031 Show SKUs instead of variant ids in the "clinically critical products" line of an infeasible scenario: add the SKUs to `summary.infeasible` in `services/procurement-service/src/scenarios/store.py` (`_critical`) and the contract, render them at `apps/web/src/features/scenarios/ScenariosScreen.tsx` (`scenarios.critical`), and cover it in `services/procurement-service/tests/test_scenarios_api.py` and `apps/web/tests/unit/ScenariosScreen.sku.test.tsx` per SC-002 (contradicts). Done: `summary.infeasible.clinical_critical_skus`, same order as the ids
- [X] T032 Add a procurement test that validates a real `GET /scenarios/{id}` body against `packages/contracts/dto/scenario.v1.schema.json` (`summary.changes[]`), and align `packages/contracts/dto/scenario_result.v1.schema.json` `lines[]` with the real fields (`qty`, string `unit_cost`, `line_total`, `clinical_critical`) or document that it describes another shape, per FR-008 and SC-005 (partial). Done: the line schema keeps its legacy shape (removing fields is breaking) and now says so; the response is validated against `summary` instead
- [X] T033 Make rows without a SKU distinguishable: add the product name to scenario changes and lines in the contract and `store.py`, and show it next to "Sin SKU" in `ScenariosScreen.tsx`; or, if not wanted, record the limit in `spec.md` edge cases, per FR-005 (partial). Done: `name` (optional, nullable) on changes and lines; shown next to "Sin SKU"
- [X] T034 Move the "no SKU" text to a shared key (for example `common.no_sku`) in `apps/web/src/i18n/es-ES.json` and use it in `ScenariosScreen.tsx` and the dashboard files that use `dashboard.drill.no_sku`, per FR-012 (unrequested)
