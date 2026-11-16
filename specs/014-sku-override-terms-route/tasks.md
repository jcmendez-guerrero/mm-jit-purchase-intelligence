# Tasks: SKU Route for Product-Supplier Terms

**Input**: `specs/014-sku-override-terms-route/` (spec.md, plan.md, research.md, data-model.md, contracts/, quickstart.md)

**Prerequisites**: plan.md, spec.md. Tests come before implementation (project rule); all fixtures synthetic (`packages/testing`), never a real Siweb host.

**Decision (research D1)**: the route is renamed in place to `/product-suppliers/{sku}/{supplier_id}/terms` and the variant-id route is deleted in this change (no production data). The override screen moves with it. Existing tests that call the old path are updated, not duplicated.

## Phase 1: Setup (contract first, rule 9)

- [X] T001 Copy `specs/014-sku-override-terms-route/contracts/override_terms_view.v1.schema.json` to `packages/contracts/dto/override_terms_view.v1.schema.json` (check the `$ref`s and `required` against `OverrideView` in `apps/web/src/api/client.ts`)
- [X] T002 Update the baseline and regenerate types with `packages/contracts/tools/update_baseline.py` and `packages/contracts/tools/codegen.py` (outputs: `packages/contracts/baseline/dto/override_terms_view.v1.schema.json`, `packages/contracts/python/mmi_models/dto/`, `apps/web/src/api/generated/dto/`)
- [X] T003 [P] Contract test in `packages/contracts/tests/test_override_terms_view.py`: a synthetic view validates; a body with `variant_id` is rejected (`additionalProperties: false`)
- [X] T004 Rename the two matrix entries in `docs/architecture/integration/contract-matrix.json` to `GET` and `PUT /api/product-suppliers/{sku}/{supplier_id}/terms` (consumer `web`, status `draft`) and write `specs/014-sku-override-terms-route/agent-00-contract-note.md` (breaking rename; only consumer is the web app, changed in the same PR; new schema `override_terms_view.v1`)
- [X] T005 Check whether the project publishes a generated API description (OpenAPI file or a test that snapshots it; none was found while planning): if one exists, update it for the renamed routes and cover it in a test; if not, record "none" in `agent-00-contract-note.md` (spec FR-007)

**Checkpoint**: `python -m gates run` from `scripts/` passes.

## Phase 2: Foundational (shared by the stories)

- [X] T006 Add an optional `audit_label: str | None = None` argument to `save_override` in `services/procurement-service/src/terms/overrides.py`, used as the entity id of the `terms.override_saved` audit entry instead of `variant_id:supplier_id` when given (no other caller changes)
- [X] T007 Update `_target` in `services/procurement-service/src/api/refusals.py` so a request on `/product-suppliers/...` builds the entity id `<sku>:<supplier>` from `params['sku']`

**Checkpoint**: existing procurement terms tests still green (the old-path tests are updated in US3).

## Phase 3: User Story 1 - Read the product-supplier terms by SKU (P1) 🎯 MVP

**Goal**: read the terms of a product and supplier by SKU, no variant id in the answer.

**Independent Test**: read a synthetic SKU; compare with the stored terms; unknown and ambiguous SKUs are refused.

- [X] T008 [P] [US1] Procurement tests in `services/procurement-service/tests/test_terms_sku_014.py`: GET by SKU returns the stored terms with `sku` and no `variant_id` key anywhere; `as_of` works and a bad `as_of` gives 400 `request_invalid`; a SKU with spaces, an encoded slash, accents and different case resolves exactly; unknown, empty and ambiguous SKU give 422 `sku_unknown` / `sku_ambiguous`; a local-load surrogate-id product (9,000,000 range) resolves and its id is not returned; a supplier with no terms gives today's empty view; the answer validates against `override_terms_view.v1`; captured logs of the request (caplog) hold no variant id
- [X] T009 [P] [US1] Gateway tests in `services/api-bff/tests/test_terms_sku_014.py`: viewer, buyer, approver and admin may read; no session is refused; the request is forwarded with identity and roles; procurement's 422 codes pass through; a NUL byte in the SKU gives 422 `invalid_input` before the service is called
- [X] T010 [US1] Change the GET in `services/procurement-service/src/api/terms.py` to `/product-suppliers/{sku}/{supplier_id}/terms`: resolve with `variant_for_sku` (from `policies.service`), map `PolicyError` to 422 with `error_code(exc)`, keep the rest of the logic, answer with `sku` (the trimmed request SKU) instead of `variant_id`
- [X] T011 [US1] Change `get_override_terms` in `services/api-bff/src/clients/procurement.py` to take a SKU (percent-encoded with `quote(..., safe='')`) and the GET route in `services/api-bff/src/routes/api.py` to `/product-suppliers/{sku}/{supplier_id}/terms` with the same roles; no money arithmetic and no `Decimal`, `float(` or `round(` in comments

**Checkpoint**: T008 and T009 green.

## Phase 4: User Story 2 - Save the product-supplier terms by SKU (P1)

**Goal**: save terms by SKU with today's rules (buyer only, `If-Match`, idempotency, audit).

**Independent Test**: save by SKU with current and stale versions; replay a key; read it back.

- [X] T012 [P] [US2] Procurement tests in `services/procurement-service/tests/test_terms_sku_014.py`: PUT by SKU stores the terms and answers `{version}`; terms saved before the change (stored by variant id) are returned by SKU and the next save continues their version; stale `If-Match` gives 412 with `current_version`, missing gives 428; the same `Idempotency-Key` replays with `Idempotent-Replay: true`; non-buyer gets 403 `auth_forbidden_role`; unknown or ambiguous SKU stores nothing and writes no change event; both the saved and the refused audit entries have entity id `<sku>:<supplier>` and no variant id; captured logs hold no variant id
- [X] T013 [P] [US2] Gateway tests in `services/api-bff/tests/test_terms_sku_014.py`: only buyer may save; `If-Match` and `Idempotency-Key` are forwarded; the "only the recorded routes declare an Idempotency-Key" test (`services/api-bff/tests/test_gateway_idempotency.py`) and `test_terms_idempotency_forwarding.py` use the SKU path
- [X] T014 [US2] Change the PUT in `services/procurement-service/src/api/terms.py` to `/product-suppliers/{sku}/{supplier_id}/terms`: resolve the SKU first, keep the idempotency scope `product_supplier_terms` and target `variant_id:supplier_id`, pass `audit_label=f"{sku}:{supplier_id}"` to `save_override` (T006), keep the change event key by variant id
- [X] T015 [US2] Change `put_override_terms` in `services/api-bff/src/clients/procurement.py` and the PUT route in `services/api-bff/src/routes/api.py` to the SKU (buyer role; `If-Match` and `Idempotency-Key` forwarded)

**Checkpoint**: T012 and T013 green.

## Phase 5: User Story 3 - Remove the variant-id route and ask for the SKU on screen (P1)

**Goal**: no path takes a variant id and the override screen asks for the SKU.

**Independent Test**: the old path is unknown; a buyer reads and saves terms on the screen with a synthetic SKU; an unknown SKU shows the Spanish message.

- [X] T016 [US3] Update the existing tests that call the variant-id path to the SKU path: `services/procurement-service/tests/test_terms_api.py`, `test_terms_roles.py`, `test_terms_events.py`, `test_terms_idempotency.py`, `test_terms_refusal_audit.py`; `services/api-bff/tests/test_suppliers_rbac.py`, `test_gateway_idempotency.py`, `test_terms_idempotency_forwarding.py`; and add a test in `services/api-bff/tests/test_terms_sku_014.py` that `GET`/`PUT /api/product-suppliers/{numeric id}/{supplier}/terms` no longer answers as a variant route (a numeric value is just a SKU and gives `sku_unknown` unless a product has that SKU)
- [X] T017 [P] [US3] Web unit and e2e tests first: update `apps/web/tests/e2e/suppliers-terms-journey.spec.ts` and `suppliers-manage.spec.ts` so the buyer types a SKU and sees the Spanish `sku_unknown` message for an unknown one; confirm `apps/web/tests/unit/glossary.test.ts` and the variant-id display check fail while the exception entries are still there
- [X] T018 [US3] Delete the variant-id routes from `services/procurement-service/src/api/terms.py` (nothing may be left that takes `variant_id` in the path) and from `services/api-bff/src/routes/api.py` and `src/clients/procurement.py`
- [X] T019 [US3] In `apps/web/src/api/client.ts` change `getOverrideTerms` and `putOverrideTerms` to take a SKU (`/product-suppliers/${encodeURIComponent(sku)}/${encodeURIComponent(supplierId)}/terms`) and `OverrideView` to carry `sku` instead of `variant_id` (use the generated type from T002 if the file imports generated types)
- [X] T020 [US3] In `apps/web/src/features/suppliers/OverrideEditor.tsx` ask for the SKU instead of the numeric variant id (Spanish labels from `apps/web/src/i18n/es-ES.json`, replacing `suppliers.override.variant`), show the `errors.sku_unknown` and `errors.sku_ambiguous` messages, and replace the numeric `variant` state, the `Number.isInteger` check and the idempotency key built from `variantId` with a trimmed non-empty SKU; remove the `suppliers.override.variant` entry from `KNOWN_EXCEPTIONS` in `apps/web/tests/unit/glossary.test.ts`; open `apps/web/tests/unit/variant-id-display.baseline.json`, remove the entry for `OverrideEditor.tsx` if present (none was found by a text search) and run `apps/web/tests/unit/no-variant-id-display.test.tsx`
- [X] T021 [US3] Mark T050 in `specs/012-ux-navigation-localization/tasks.md` as partly done (override screen only; the safety-stock and demand sections remain) and note the overlap with PR 24 in `agent-00-contract-note.md`

**Checkpoint**: no path or screen field takes a variant id for product-supplier terms.

## Phase 6: Polish & cross-cutting

- [X] T022 [P] Confirm `errors.sku_unknown` and `errors.sku_ambiguous` exist in `apps/web/src/i18n/es-ES.json` and `packages/contracts/errors/error_codes.json` (both already do; add nothing unless a test shows a gap)
- [X] T023 Run the suites and the gate: `pytest` in `services/procurement-service`, `services/api-bff` and `packages/contracts`, the web unit tests, the suppliers e2e specs, then `python -m gates run` from `scripts/`; follow `specs/014-sku-override-terms-route/quickstart.md`
- [X] T024 Fill `.github/pull_request_template.md` (data: synthetic only; security: roles unchanged; cost: none; contract impact: two routes renamed, one new schema, old path removed) in `specs/014-sku-override-terms-route/pull-request.md`

## Dependencies & order

- Phase 1 first (contract first). Phase 2 before Phases 3 and 4.
- US1 (T008–T011) before US2 (T012–T015): they edit the same two source files. Test tasks T008, T009, T012, T013 can be written in parallel.
- US3 after US1 and US2 (T018 deletes what the SKU routes replaced; T019–T020 need the new route). T017 (web tests) can start early; T016 goes in with T010 and T014.
- Parallel: T003 with T004; T008 with T009; T012 with T013; T017 with T016's gateway part; T022 with others. T016's procurement test updates go in with T010/T014 (they fail as soon as the routes are renamed).

## Implementation strategy

- **MVP**: Phases 1–3 prove the read by SKU, but the change is shippable only with all three stories, because deleting the old route needs the screen to move with it. Land them in one PR.
- Write each test task first and watch it fail before the matching implementation task.
- Mark tasks `[X]` as they finish.
- If PR 24 (feature 012) lands first, take its `OverrideEditor.tsx` and keep only what T020 still needs.

## Phase 7: Convergence

- [X] T025 Settle the SKU-with-slash edge case: either make `/product-suppliers/{sku:path}/{supplier_id}/terms` accept a slash in `services/procurement-service/src/api/terms.py` and `services/api-bff/src/routes/api.py` (the gateway client already encodes it as `%2F`), or change the edge-case line in `specs/014-sku-override-terms-route/spec.md` to say a SKU containing `/` is not supported on SKU routes; add a synthetic accented SKU (for example `SYN-ÁÑO-1`) to `services/procurement-service/tests/test_terms_sku_014.py` and `services/api-bff/tests/test_terms_sku_014.py` per spec edge case "SKU with spaces, slashes, accents" (partial)
- [X] T026 Add a SKU step to `apps/web/tests/e2e/suppliers-terms-journey.spec.ts`: a buyer types a SKU in "SKU del producto", loads the terms, and sees the Spanish `sku_unknown` message when the mocked route answers 422; run the supplier e2e specs where Playwright is installed and record the result in `specs/014-sku-override-terms-route/pull-request.md` per US3/AC2-AC3 and SC-001 (partial)

## Phase 8: Convergence

- [X] T027 Add the missing `override_terms_view` row (`dto`, v1, agent-00, `api-bff, web`, draft) to `docs/architecture/integration/contract-matrix.md` next to `policy_audit_page`, matching `contract-matrix.json`, and update any entry count or summary line in that file per FR-007 (partial)

## Phase 9: Convergence

- [X] T028 Keep the supplier id whole in the audit entity id: build the label as `f"{sku.strip()[:23]}:{supplier_id}"` in `services/procurement-service/src/api/terms.py` (the `audit_label` passed to `save_override`) and in `_target` in `services/procurement-service/src/api/refusals.py`, because `audit_events.entity_id` holds 60 characters and the supplier id uses 37; add a test with a 40-character SKU to `services/procurement-service/tests/test_terms_sku_014.py` and `test_terms_refusal_audit.py` that checks the full supplier id is in both the saved and the refused entry per FR-002 (partial)
- [X] T029 Remove the empty `KNOWN_EXCEPTIONS` object, its outdated comment and the test "known exceptions still exist" from `apps/web/tests/unit/glossary.test.ts`; the remaining glossary test still checks every catalogue value per plan: lean (unrequested)
