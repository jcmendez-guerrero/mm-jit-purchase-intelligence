# Tasks: Procurement Proposals & Scenarios (Agent 03)

**Input**: Design documents in `/specs/011-procurement-proposals-scenarios/` (plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md)

**Approach**: audit-then-close-gaps. Gaps G1 to G7 are in research.md section 2. Tests come before implementation within each story. Synthetic fixtures only (`packages/testing`). Paths are relative to the repo root; `PS` = `services/procurement-service`, `BFF` = `services/api-bff`, `WEB` = `apps/web`.

## Note: T043 to T046 were added after the analysis pass; IDs are unique, not in file order

## Format: `- [ ] T### [P?] [US?] Description with file path`

## Phase 1: Setup

- [X] T001 Re-run the evidence inventory against current main and update the status column in `specs/011-procurement-proposals-scenarios/research.md` (execute the existing proposal, approval, scenario, allocation and export tests under `PS/tests` and `BFF/tests` and record pass/fail)
- [X] T002 [P] Add a synthetic 2,000-SKU catalogue builder with at least two eligible approvers to `PS/tests/builders.py` (reuse `packages/testing/src/generator`)
- [X] T003 [P] Draft the Agent 00 note from `contracts/proposals-scenarios.delta.md` as `specs/011-procurement-proposals-scenarios/agent-00-contract-note.md` (draft only, not sent)

## Phase 2: Foundational (blocks all stories)

- [X] T004 Add error keys `proposal_line_conflict` and `proposal_superseded` to `packages/contracts/errors/error_codes.json` and `specs/002-mmi-operational-console/contracts/error-keys.md`, with Spanish text in `WEB/src/i18n/es-ES.json`; regenerate types and run `python -m gates run` from `scripts/`. The change lands as a PR proposal: do not merge until Agent 00 has confirmed the note from T003 (record the answer in research.md)
- [X] T005 [P] Add a network-denied test fixture (any outbound request fails the test and is recorded) in `PS/tests/conftest.py`

**Checkpoint**: contracts and fixtures ready.

## Phase 3: User Story 1 - Explained weekly proposal (Priority: P1)

**Goal**: proposals are deterministic, every line is explained, stale saves are rejected clearly, generation meets the time target.
**Independent test**: generate from synthetic data twice, compare, open explanations, edit with a stale version.

- [X] T006 [P] [US1] Test: two generations from identical inputs are identical line by line with the same versions in `PS/tests/test_proposal_determinism.py`
- [X] T007 [P] [US1] Test: a rounded-up or topped-up line states the rounding or top-up and its cost impact, and an unmeetable supplier minimum is flagged as a shortfall with its cost impact in `PS/tests/test_line_explanation_constraints.py`
- [X] T008 [P] [US1] Test: stale line save returns 409 `proposal_line_conflict`, changes nothing, and is audited (`proposal.line_conflict`) in `PS/tests/test_edit_conflict.py`
- [X] T009 [P] [US1] Test: generation for the 2,000-SKU catalogue finishes under 60 s in `PS/tests/perf/test_generation_time.py` (extend the existing test)
- [X] T010 [US1] Return `proposal_line_conflict` (not `version_conflict`) for a stale line save, keeping `version_conflict` unchanged elsewhere, with the audit entry, in `PS/src/proposals/edit.py` and `PS/src/api/proposals.py`
- [X] T011 [US1] Show the Spanish "line changed, reload" message and reload action in `WEB/src/features/proposals/ProposalsScreen.tsx`
- [X] T043 [P] [US1] Test (FR-014): a malformed or ambiguous supplier term or cost reaching generation goes to the review list, the line is flagged and nothing is dropped silently, in `PS/tests/test_review_list_inputs.py`
- [X] T044 [P] [US1] Test (FR-012): money is exact decimal, timestamps are stored UTC with the original string, lines are keyed by variant id while users see the SKU, in `PS/tests/test_proposal_money_time_keys.py` (reuse `test_money_and_time_storage.py` and `test_refuse_local_ids.py` as evidence)
- [X] T012 [US1] Contingency (run only if T006, T007, T009, T043 or T044 fail): fix the failing behaviour in `PS/src/proposals/generate.py`, `PS/src/proposals/inputs.py` or `PS/src/allocation/`, record the finding in research.md, and re-run the failing test; mark done as "not needed" if all four pass — not needed as a separate fix: T043 exposed the silent drop, fixed in `PS/src/proposals/generate.py`

**Checkpoint**: US1 independently verified.

## Phase 4: User Story 2 - Deterministic scenarios (Priority: P1)

**Goal**: same constraints give the same scenario; promotion makes a new draft version and supersedes the old one.
**Independent test**: run a scenario 20 times, change one constraint, promote.

- [X] T013 [P] [US2] Test: 20 runs of the same scenario give one `result_hash` in `PS/tests/test_scenarios_determinism.py`
- [X] T014 [P] [US2] Test: changing one constraint changes only affected lines and each change has an explanation; two scenarios compare side by side (total, per-supplier spend, shortfalls, ranked sensitivity); an infeasible scenario reports the conflicting constraints, in `PS/tests/test_scenarios_constraints.py`, `PS/tests/test_scenarios_infeasible.py` and `PS/tests/test_scenarios_sensitivity.py` (extend)
- [X] T015 [P] [US2] Test: running a scenario leaves the real proposal and supplier terms untouched (reuse `PS/tests/test_scenarios_isolation.py` as evidence); promotion creates a new draft, marks the week's earlier proposals `superseded`, earlier approval does not carry over, repeat promote returns `scenario_already_promoted`, stale scenario returns `scenario_stale`, in `PS/tests/test_scenarios_promote.py` (extend)
- [X] T016 [P] [US2] Test: a superseded proposal cannot be edited, submitted, approved or exported (409 `proposal_superseded`) in `PS/tests/test_superseded_proposal.py`
- [X] T017 [US2] Enforce `proposal_superseded` in `PS/src/approvals/workflow.py`, `PS/src/proposals/edit.py` and `PS/src/proposals/export.py`
- [X] T019 [P] [US2] Vitest (written first, fails until T018 lands) for the superseded and stale displays in `WEB/tests/unit/proposals-superseded.test.tsx` and `WEB/tests/unit/scenarios-stale.test.tsx` — implemented in `WEB/tests/unit/proposals-superseded.test.tsx` and `WEB/tests/unit/scenarios-export-roles.test.ts` (stale scenarios use the existing `errors.scenario_stale` message)
- [X] T018 [P] [US2] Show superseded proposals (read-only badge, link to the newer version) in `WEB/src/features/proposals/ProposalsScreen.tsx` and stale scenarios (disabled promote with reason) in `WEB/src/features/scenarios/ScenariosScreen.tsx`

**Checkpoint**: US2 independently verified.

## Phase 5: User Story 3 - Approval, export roles, nothing sent (Priority: P1)

**Goal**: separation of duties holds, only permitted roles export, no supplier or ERP request exists, repeated actions have one effect.
**Independent test**: attempt approval as creator, last editor, viewer and eligible approver; attempt export as each role.

- [X] T020 [P] [US3] Test: viewer export of a proposal is refused 403 `auth_forbidden_role` and audited as `proposal.export_refused`; buyer, approver and admin succeed, in `PS/tests/test_export_roles.py`
- [X] T021 [P] [US3] Test: same role matrix for scenario export in `PS/tests/test_scenarios_export.py` (extend) and `BFF/tests/test_scenario_routes.py`
- [X] T022 [P] [US3] Test: gateway proposal export role matrix in `BFF/tests/test_proposal_routes.py`
- [X] T023 [P] [US3] Test: generate, edit, scenario, promote, submit, approve and export make zero outbound requests using the T005 fixture, in `PS/tests/test_no_outbound_requests.py`
- [X] T024 [P] [US3] Test: repeated submit, approve, promote and export requests have one effect and one audit entry each in `PS/tests/test_idempotent_actions.py`
- [X] T025 [P] [US3] Test: edit after submission resets approval; fewer than two eligible people refuses submission in `PS/tests/test_approval_eligibility.py` (extend)
- [X] T026 [US3] First check whether `require("buyer")` in `PS/src/api/proposals.py` admits approver and admin; if not, widen the gate to buyer, approver and admin. Then restrict proposal export to those roles and audit viewer refusals in `BFF/src/routes/api.py`, `PS/src/api/proposals.py` and `PS/src/proposals/export.py`
- [X] T027 [US3] Restrict scenario export the same way in `BFF/src/routes/scenarios.py` and `PS/src/api/scenarios.py`
- [X] T028 [US3] Hide export buttons from viewers in `WEB/src/features/proposals/ProposalsScreen.tsx` and `WEB/src/features/scenarios/ScenariosScreen.tsx`
- [X] T045 [P] [US3] Verify the edge cases (deactivated supplier or unconfirmed cost after generation is flagged not repriced, non-EUR supplier shown with original amount and rate) by listing and running the existing tests (`test_supplier_deactivation.py`, `test_non_eur_supplier.py`, `test_cost_provenance_difference.py`) and adding any missing case, in `PS/tests/test_proposal_edge_cases.py`
- [X] T046 [P] [US3] Verify approved proposals show grouped by supplier for manual ordering (per-supplier totals, CSV and Excel per supplier) in `WEB/tests/unit/proposals-grouped.test.tsx` and `PS/tests/test_export_locale.py` (extend)
- [X] T029 [US3] Contingency (run only if T024, T025, T045 or T046 fail): fix the failing behaviour in `PS/src/approvals/workflow.py`, `PS/src/scenarios/store.py`, `PS/src/proposals/export.py` or `WEB/src/features/proposals/ProposalsScreen.tsx` (the grouped-by-supplier view); mark done as "not needed" if both pass — not needed: T024, T025, T045 and T046 pass on the existing code

**Checkpoint**: US3 independently verified; the three P1 stories are the MVP.

## Phase 6: User Story 4 - Budgets, shipping and discounts (Priority: P2)

**Goal**: cap, delivery thresholds and held discounts shape the plan transparently.
**Independent test**: set a cap below the unconstrained total and inspect the flagged excess.

- [X] T030 [P] [US4] Test: with a cap below the total, every needed quantity stays (clinically critical needs never dropped), the excess over the cap is reported with its amount, and each line is flagged over budget in `PS/tests/test_budget_cap_explanation.py`
- [X] T031 [P] [US4] Test: for a supplier just under its free-delivery threshold, top-up versus reallocation is shown with the cheaper choice and why, in `PS/tests/test_allocation_terms.py` (extend)
- [X] T032 [P] [US4] Test: a discount tier already held in supplier terms applies when crossed and is stated on the line; absent discount data is reported, not invented, in `PS/tests/test_discount_application.py`
- [X] T033 [US4] Add the missing explanation text for the over-budget amount and delivery decisions in `PS/src/allocation/common.py` and `PS/src/proposals/generate.py`, with Spanish strings in `WEB/src/i18n/es-ES.json`
- [X] T034 [US4] Contingency (run only if T032 shows supplier terms hold no discount data): record the gap in research.md and in `agent-00-contract-note.md`, add no terms editing here; mark done as "not needed" otherwise — not needed: supplier terms already hold discount tiers (`test_delivery_and_discount_explanations.py`)

**Checkpoint**: US4 independently verified.

## Phase 7: User Story 5 - Proven end to end in Spanish (Priority: P2)

**Goal**: the whole journey runs against the real stack in es-ES.
**Independent test**: run the Playwright journey.

- [X] T038 [US5] Wire the compose seed (two eligible approvers, synthetic suppliers) for the journey in `infra/compose.yaml` fixtures or `packages/testing/src/seed_fixtures`
- [ ] T035 [US5] API-backed Playwright journey in `WEB/tests/e2e/procurement-journey.spec.ts`, also timing the path from opening a proposal to a compared scenario (SC-005, under 3 minutes) and saving screenshots for the PR: generate, explain, edit, stale save refused, scenario, compare, promote (old shows superseded), submit, self-approval refused, second user approves with fresh MFA, export CSV and Excel, viewer cannot export — PARTLY DONE: real-services journey written and passing (`WEB/tests/live/procurement-journey.spec.ts`); the full generate-to-approve journey cannot run on the compose stack (no forecast service, no proposal-generation route on the gateway); covered by service tests — Option A built (Agent 00 advice): the local compose stack seeds one synthetic draft (`MMI_DEMO_SEED=1`, `services/procurement-service/src/local_demo/seed.py`, local only). The live journey runs from opening the proposal: explanation, line edit, scenario compared (timed), promote, submit, creator cannot approve, approver sees the approve button. NOT ticked on purpose: generate is proven by service tests, and approve and export files are not run in the browser (an approved week would block repeat runs).
- [X] T036 [P] [US5] Spanish and format check on proposal and scenario screens (no English strings, EUR and es-ES dates) in `WEB/tests/e2e/procurement-i18n.spec.ts`
- [X] T037 [P] [US5] Accessibility check of both screens in `WEB/tests/e2e/a11y-screens.spec.ts` (extend)

**Checkpoint**: all stories verified.

## Phase 8: Polish

- [X] T039 Run the full suites and `python -m gates run`; fix regressions
- [ ] T040 Update `docs/architecture/integration/feature-status.json` entries for this domain with the new evidence — NOT DONE: `feature-status.json` is owned by Agent 00; evidence is in research.md section 5
- [X] T041 Write `specs/011-procurement-proposals-scenarios/pull-request.md` following `.github/pull_request_template.md` (data, security, cost, contract impact, screenshots, known limits, links to MMI-5 and Confluence 3145771)
- [X] T042 Run the quickstart steps and tick completed tasks here

## Dependencies

- Phase 1 then Phase 2, which block everything.
- US1, US2 and US3 are independent after Phase 2; T017 and T026 touch different files, but T011, T018 and T028 all edit `ProposalsScreen.tsx` (and T018, T028 also `ScenariosScreen.tsx`): do them in that order.
- T004 may be developed immediately but is not merged until Agent 00 confirms the T003 note.
- US4 depends on nothing but shares `PS/src/allocation/common.py` with US1's T012.
- US5 depends on US1 to US3 being done (the journey exercises them); within US5, T038 (seed) comes before T035 (journey).
- Within US2, T019 (Vitest) is written before T018 (UI).
- Polish last.

## Parallel examples

- US1 tests T006 to T009 run together; US2 tests T013 to T016 together; US3 tests T020 to T025 together.
- US1 and US2 implementation can proceed in parallel once their tests exist.

## Implementation strategy

MVP is the three P1 stories (Phases 3 to 5): deterministic proposals and scenarios, and the approval and export controls. Then US4, then US5 for the final evidence. Stop at each checkpoint and verify before moving on.

## Phase 9: Convergence

- [X] T047 Show the budget excess over the cap in euros on the proposal screen, read from the proposal's over-budget flag (add it to the proposal detail response in `services/procurement-service/src/api/proposals.py`, to the `Proposal` type in `apps/web/src/api/client.ts`, to `apps/web/src/features/proposals/ProposalsScreen.tsx` and the Spanish text in `apps/web/src/i18n/es-ES.json`), with a Vitest in `apps/web/tests/unit/proposals-over-budget.test.tsx` and an API assertion in `services/procurement-service/tests/test_budget_cap_explanation.py` per US4/AC1 and FR-004 (partial; T033 was ticked without this)
- [ ] T048 Run the full Spanish journey end to end against a stack that can generate a proposal (generate, open an explanation, edit a line, stale save refused, scenario and comparison, promote, submit, self-approval refused, second user approves with fresh MFA, export CSV and Excel, viewer cannot export) in `apps/web/tests/live/procurement-journey.spec.ts`, timing the path from opening a proposal to a compared scenario against the 3-minute target, per US5/AC1, FR-016 and SC-005 (partial; finishes T035) — Option A built (Agent 00 advice): the local compose stack seeds one synthetic draft (`MMI_DEMO_SEED=1`, `services/procurement-service/src/local_demo/seed.py`, local only). The live journey runs from opening the proposal: explanation, line edit, scenario compared (timed), promote, submit, creator cannot approve, approver sees the approve button. NOT ticked on purpose: generate is proven by service tests, and approve and export files are not run in the browser (an approved week would block repeat runs).
- [X] T049 On the superseded proposal screen add a link to the newer version of the same week in `apps/web/src/features/proposals/ProposalsScreen.tsx`, with a Vitest in `apps/web/tests/unit/proposals-superseded.test.tsx`, per US2/AC6 and FR-008 (partial)
- [ ] T050 Send `specs/011-procurement-proposals-scenarios/agent-00-contract-note.md` to Agent 00 and record the answer in `specs/011-procurement-proposals-scenarios/research.md`; do not merge the contract change before it is confirmed, per plan: Constitution IV and T003/T004 (missing)
- [ ] T051 Hand the evidence in `specs/011-procurement-proposals-scenarios/research.md` section 5 to Agent 00 so `docs/architecture/integration/feature-status.json` is updated by its owner, per FR-001 and SC-008 (missing; finishes T040)

## Phase 10: Convergence

- [X] T052 Record the "no usable supplier" note only when the product needs stock or has a fixed quantity (use the same `compute_target(v, fastest).need > 0 or fixed_qty` check, with the shortest lead time among all its offers), so a stocked product behind a disabled supplier raises no warning, in `services/procurement-service/src/allocation/common.py` and `services/procurement-service/src/proposals/generate.py` per FR-014 and US4 (contradicts)
- [X] T053 Add a test that a stocked product whose only supplier is disabled produces no `no_eligible_supplier` note, and that a product with real need still does, in `services/procurement-service/tests/test_review_list_inputs.py` per FR-014 (partial)
- [X] T054 Truncate the id written to the audit entry of a refused export to 60 characters (`proposal_id[:60]`, `sid[:60]`) so a long id cannot turn a 403 into a 500 on PostgreSQL, in `services/procurement-service/src/api/proposals.py` and `services/procurement-service/src/api/scenarios.py`, with a test in `services/procurement-service/tests/test_export_roles.py` per FR-010 and FR-013 (partial)
- [X] T055 Give `over_budget` and `review_notes` each their own comment in `Proposal`, in `apps/web/src/api/client.ts` per FR-014 (partial)
- [X] T056 Keep one definition of the export roles per layer: import the gateway constant in `services/api-bff/src/routes/scenarios.py` instead of repeating it, and have `canExportScenario` reuse the proposal export rule in `apps/web/src/features/scenarios/scenariosModel.ts` per FR-010 (unrequested)
- [X] T057 Move `Blob` and `Users` into `services/procurement-service/tests/proposal_support.py` so the plugin no longer imports a test module, and update `tests/test_api_proposals.py` to import them from there, per plan: test approach (unrequested)

## Phase 11: Convergence

- [X] T058 Add the new optional properties (`over_budget`, `review_notes` with `variant_id` marked "web lookups only, never displayed", and every other detail field the proposal response now returns) to `packages/contracts/dto/proposal.v1.schema.json`, refresh its baseline with `packages/contracts/tools/update_baseline.py`, regenerate `mmi_models/dto/proposal_v1_schema.py`, and add a test that a real detail response validates against the schema (`additionalProperties: false` rejects it today), then run `python -m gates run`, per Agent 00 finding 1, FR-004, FR-014 and AGENTS.md rule 9 (partial)
- [X] T059 Record Agent 00's answer to the contract note in `specs/011-procurement-proposals-scenarios/research.md` (export routes confirmed, two error keys accepted, `review_notes` and `over_budget` accepted once T058 lands) and tick the contract checkbox in `pull-request.md` after T058, per plan: Constitution IV and T050 (partial)
- [X] T060 Add one line to `docs/architecture/integration/gateway-review.md` stating that proposal and scenario export is for buyer, approver and admin, a viewer is refused and the refusal is audited, per Agent 00 finding 6 and FR-010 (missing)
- [X] T061 Open an issue for the failing `a11y-all-routes.spec.ts` "reference task 3 by keyboard" test and either fix it or quarantine it so the `e2e` gate is not red for this branch, and link the issue in `pull-request.md`, per Agent 00 finding 3 and SC-008 (partial) — DONE: issue opened as MMI-12 (https://mundomascotix.atlassian.net/browse/MMI-12); the test is quarantined with `test.fixme` until it is fixed there
- [X] T062 Fix the Markdown lint error MD026 (trailing period in the heading at `specs/011-procurement-proposals-scenarios/tasks.md` line 7, found by the Super-linter job) by removing the period, per the CI Linting check (partial)
- [ ] T063 Rebase on `main` once #22 and #24 are merged and resolve the semantic conflicts by hand in `apps/web/src/api/client.ts`, `services/procurement-service/src/api/proposals.py` and `apps/web/src/features/proposals/ProposalsScreen.tsx`, then re-run the procurement, gateway and web suites, per Agent 00 finding 2 (missing)
- [ ] T064 Decide whether to rename this spec folder or `specs/011-business-policy-configuration` (#22) so spec numbers are unique, and update `.specify/feature.json` and links if renamed, per Agent 00 finding 4 (unrequested)

## Phase 12: Convergence

- [X] T065 Format `packages/contracts/dto/proposal_detail.v1.schema.json` with Prettier and copy it unchanged to `packages/contracts/baseline/dto/proposal_detail.v1.schema.json`, regenerate the model with `packages/contracts/tools/codegen.py`, and confirm the contracts tests and gate still pass, so the Super-linter JSON_PRETTIER job passes, per CI Linting and T058 (partial)
- [X] T066 Link MMI-12 (the failing supplier-terms keyboard test) in `specs/011-procurement-proposals-scenarios/pull-request.md` and on the T061 line of `tasks.md`, then tick T061, per Agent 00 finding 3 and T061 (partial)
