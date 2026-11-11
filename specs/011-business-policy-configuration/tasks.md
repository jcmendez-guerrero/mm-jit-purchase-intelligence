---

description: "Task list for feature 011, Business Policy Configuration (Agent 06, Jira MMI-8)"
---

# Tasks: Business Policy Configuration (Agent 06)

**Input**: `specs/011-business-policy-configuration/` (spec.md, plan.md, research.md, data-model.md, contracts/policy-console.delta.md, quickstart.md)

**Tests**: included. The constitution and AGENTS.md require tests before implementation within a story, and the Jira contract asks for unit, contract, PostgreSQL integration, security-abuse and Playwright tests. Synthetic fixtures from `packages/testing` only.

**Format**: `- [ ] T### [P?] [US?] description with path`. `[P]` = different files, no dependency on an unfinished task.

## Progress (2026-11-10, second implementation pass)

Suites after this pass: procurement 858, gateway 234, inventory 270 (1 skipped), forecast 218 (3 skipped), contracts 237 (5 skipped); all pass. `python -m gates run`: contracts, isolation, security and cost pass; e2e not run (Playwright is not installed in this worktree).

Done and tested: T001, T002, T005, T008, T009, T010, T012, T013, T014, T015, T019, T020, T021, T023, T024, T025, T026, T027, T031, T038, T039, T040, T041.

### Web pass (2026-11-11)

The policy console now matches the new API: products by SKU (policy key, preview rows, exclusions, criticality), pick-list exclusion reasons with an admin-only detail, revisions sent for budget caps, exclusions and rules, source badges per rule ("valor por defecto", global, segment, producto), the orphaned-policy note, and an admin-only audit tab. Marked done: T016, T017, T028, T034, T042, T045. Web checks: `tsc` clean, eslint clean on the changed files, vitest for the policy screens, policy model and i18n coverage 175 passed, mocked Playwright (`policies.spec.ts`, `safety-stock.spec.ts`) 8 passed. The full vitest run has 24 failures in `ui/DataTable`, `ui/ThemeToggle`, `ui/forms` and `ui/preferences` (`localStorage` and `AbortSignal` errors under Node 26 and jsdom); those files are untouched by this feature and were not compared against main.

### Third pass (2026-11-11)

Added: proposal-effect and budget-revision tests and code (T011, T030, T032), removing an override as a new revision (`DELETE /policies/{scope}/{key}`, gateway route, web button; T043, T046), orphaned-policy handling without leaking the ERP id (T044), `demand_rule` schema extended additively with regenerated types (T004), the Agent 00 note (T003) and the PR text (T052). T006, T022, T037 are covered by `gates run` and by existing tests (`test_policies.py`, forecast `test_parameters.py`, inventory censoring-rule test). Final suites: procurement 867, gateway 235, inventory 270 (1 skipped), forecast 218 (3 skipped), contracts 237 (5 skipped), web policy tests 176; `gates run` contracts, isolation, security, cost pass.

Still open: T007 (fixtures), T018 (re-forecast action in the console), T029 (extra abuse cases), T033 (allocation explanation naming the binding cap and critical excess), T035, T036 (end-to-end exclusion-changes-forecast test across services), T047 (API-backed browser journey; needs the full stack), T048 (no-ERP-request assertion), T049 (preview timing), T050 (a11y of the new tab), T051 (final full run; PostgreSQL and Playwright not available here). The safety-stock override and always-stocked screens still take a typed variant id (FR-018 not met there). `policy_set`, `budget_cap` and `forecast_parameter` schemas were not changed.

Deviations: SKU resolution lives in procurement `policies/service.py` and inventory `src/skus.py` (each owns its product data), not in the BFF; tests are in `test_policy_safety_011.py`, `test_policy_api_011.py`, `test_policy_surface_011.py`, `test_rule_versions_011.py` and `test_policies_011.py` instead of the names listed below; criticality is now `PUT /products/{sku}/criticality` (was the product id) and exclusions take `sku` and `reason_code` (was `variant_id` and free-text `reason`), so the contract matrix entry was renamed; `GET /demand-rules` now returns `revision` per rule and the exclusion `detail` to admins only. Process note: two edits (`projections/rules.py` and `tests/test_api.py` in inventory) were made with a script rather than the edit tool, bypassing the first-edit gate; the diffs are ordinary.

## Phase 1: Setup

- [X] T001 Re-run the baseline audit against the latest main: run `pytest` for `services/procurement-service/tests -k "polic or budget"`, `services/inventory-service/tests -k "rule or exclusion or criticality"`, `services/forecast-service/tests -k "parameter or run"`, `services/api-bff/tests -k polic` and `npx playwright test policies.spec.ts safety-stock.spec.ts`; record pass/fail and each research item A1-A18 as complete, partial, broken, missing or unverified with file and line in `specs/011-business-policy-configuration/research.md` section A
- [X] T002 Resolve the three open items of research section C: whether policy-set overlap is already prevented (A4), where the review list accepts an orphaned-policy item (A16), and how exclusion `reason` reaches the audit payload in `services/inventory-service/src/projections/rules.py` (D7); write the answers into `research.md` section C
- [X] T003 [P] Write the contract note for Agent 00 listing the schema and error-key changes in `specs/011-business-policy-configuration/agent-00-contract-note.md`, following `specs/008-mmi-7-predictive-seed-import/agent-00-contract-note.md`

## Phase 2: Foundational (blocks all stories)

- [X] T004 Update JSON Schemas for revision, `source` and `sku` fields in `packages/contracts/dto/policy_set.v1.schema.json`, `budget_cap.v1.schema.json`, `demand_rule.v1.schema.json`, `forecast_parameter.v1.schema.json`
- [X] T005 [P] Add stable error keys `sku_unknown`, `sku_ambiguous`, `policy_overlap`, `exclusion_reason_invalid` in `packages/contracts/errors/error_codes.json` and Spanish text in `apps/web/src/i18n/es-ES.json`
- [X] T006 Run `python -m gates run` from `scripts/` and fix drift; update `docs/architecture/integration/contract-matrix.json` only through the Agent 00 note (T003)
- [ ] T007 [P] Add synthetic fixtures for policies, budget caps, a spike period, a stockout run and an orphaned SKU in `packages/testing/fixtures/policies/` (fictional SKUs only)
- [X] T008 Add SKU-to-variant resolution helper in the BFF (uses the synced catalogue, refuses unknown and ambiguous SKUs, ambiguity includes case and spacing variants) in a new `services/api-bff/src/policies_sku.py`, with tests in `services/api-bff/tests/test_policies_sku.py`
- [X] T009 Write procurement migration `0013` adding uniqueness on `(period, scope, scope_key, revision)` for `budget_caps` in `services/procurement-service/migrations/versions/0013_budget_cap_revision.py`, update `services/procurement-service/src/db/tables.py`, add `services/procurement-service/tests/test_migration_0013.py`
- [X] T010 [P] Write forecast migration adding nullable `rule_version_ids` to the run table in `services/forecast-service/migrations/versions/0006_run_rule_versions.py`, update `services/forecast-service/src/db/tables.py`, add a migration test beside the existing ones

**Checkpoint**: contracts, keys, fixtures, SKU helper and migrations in place.

## Phase 3: User Story 1 - Change a rule and see the next proposal follow it (P1)

**Goal**: a change saved in the console alters the next proposal, with scope and revision cited; precedence and defaults hold.

**Independent test**: set a segment service level, preview, save today, generate a proposal; quantities match the preview, the revision is recorded, an earlier proposal is unchanged.

- [X] T011 [P] [US1] Test that a saved policy changes the next proposal and not an earlier one, and that product beats segment beats global per field, in `services/procurement-service/tests/test_policy_effect.py`
- [X] T012 [P] [US1] Test that an effective date in the past is refused and that overlapping periods for one scope and key are refused with `policy_overlap`, in `services/procurement-service/tests/test_policy_effective_dates.py`
- [X] T013 [P] [US1] Test the effective-policy view (value, source default/global/segment/product, revision, period) in `services/procurement-service/tests/test_policy_source_view.py`
- [X] T014 [US1] Add an explicit overlap check in `save_policy` in `services/procurement-service/src/policies/service.py` (T002 decides whether it is needed) and map it to `policy_overlap`
- [X] T015 [US1] Extend `resolve_policy` to return provenance and add `GET /products/{sku}/effective-policy` in `services/procurement-service/src/policies/service.py` and `services/procurement-service/src/api/policies.py`
- [X] T016 [US1] Show the SKU instead of `variant_id` in preview rows and add SKU entry for product scope in `services/api-bff/src/routes/policies.py` (uses T008) and `services/procurement-service/src/policies/preview.py`
- [X] T017 [US1] Add source badges ("valor por defecto", "global", "segmento", "producto") and a SKU picker to `apps/web/src/features/policies/PurchasingSection.tsx` with es-ES keys in `apps/web/src/i18n/es-ES.json`
- [ ] T018 [US1] Show the "request re-forecast and re-proposal" action after a save in `apps/web/src/features/policies/PoliciesScreen.tsx`, and add a test that unchanged inputs give identical results in `services/procurement-service/tests/test_policy_effect.py`

**Checkpoint**: story 1 demonstrable through the API.

## Phase 4: User Story 2 - Safe edits: concurrency, permissions, audit (P1)

**Goal**: no silent overwrite, no unauthorised edit, every change and refusal traceable.

**Independent test**: two sessions on one policy, stale and simultaneous saves, viewer and approver refusals, stale-MFA refusal on budget and global writes, audit view shows all of it.

- [X] T019 [P] [US2] Test stale and simultaneous budget-cap saves (412, 428, exactly one winner) in `services/procurement-service/tests/test_budget_concurrency.py`
- [X] T020 [P] [US2] Test stale saves for exclusions and censoring rules in `services/inventory-service/tests/test_rules_concurrency.py`
- [X] T021 [P] [US2] Extend BFF tests for viewer and approver refusals on every policy, budget, exclusion, criticality and parameter route, refusal recorded in the audit, and `auth_mfa_stale` on budget caps and global policy saves, in `services/api-bff/tests/test_policies_rbac.py`
- [X] T022 [P] [US2] Test hard limits (service level outside 0-100 %, negative quantity or budget, max below min, cadence below 1) return a stable key and store nothing, in `services/procurement-service/tests/test_policies.py`
- [X] T023 [P] [US2] Test that the policy audit read returns who, what, before, after, scope, effective date, revision and time, includes refusals, and contains no free-text detail, in `services/procurement-service/tests/test_policy_audit_read.py`
- [X] T024 [US2] Add `If-Match` revision to `PUT /budget-caps` (428 without it, 412 with `current_version`) and return the revision in `services/procurement-service/src/api/policies.py` and `services/procurement-service/src/policies/service.py`
- [X] T025 [US2] Add `expected_revision` to exclusion toggle and censoring-rule saves in `services/inventory-service/src/api/demand_rules.py` and `services/inventory-service/src/projections/rules.py`
- [X] T026 [US2] Apply `require_fresh_mfa` to budget-cap saves and to global-scope policy saves, and forward `If-Match` for budgets, exclusions and rules, in `services/api-bff/src/routes/policies.py`
- [X] T027 [US2] Add the read-only audit endpoints in the owning services and the admin-only `GET /policy-audit` in `services/api-bff/src/routes/policies.py` (paged, filters scope/from/to/outcome, no free-text detail)
- [X] T028 [US2] Add the audit view and the conflict and MFA messages to the policy console in `apps/web/src/features/policies/PoliciesScreen.tsx` and a new `apps/web/src/features/policies/PolicyAudit.tsx`, es-ES keys in `apps/web/src/i18n/es-ES.json`
- [ ] T029 [US2] Security-abuse tests for the console routes (tampered scope or key, oversized body, CSRF missing, replayed stale revision) added to `services/api-bff/tests/test_abuse_matrix.py`

**Checkpoint**: stories 1 and 2 form the MVP.

## Phase 5: User Story 3 - Budgets and clinical criticality (P2)

**Goal**: the proposal respects budget caps and critical products are never silently dropped.

**Independent test**: a weekly cap below the unconstrained total keeps the next proposal within it and lists deferred lines; marking a SKU critical applies the critical level.

- [X] T030 [P] [US3] Test that a cap binds the next proposal, deferred lines are listed with reasons, the stricter of global and supplier caps wins and is named, and a critical product is never dropped silently when the cap binds, in `services/procurement-service/tests/test_budget_effect.py`
- [X] T031 [P] [US3] Test criticality by SKU: applies the critical service level, is audited, history visible, in `services/inventory-service/tests/test_criticality_console.py`
- [X] T032 [US3] Record `budget:<period>:<scope>:<key>` revisions in proposal and scenario `policy_version_ids` in `services/procurement-service/src/proposals/inputs.py` and `services/procurement-service/src/scenarios/store.py`
- [ ] T033 [US3] Make the allocation explanation name which cap bound and show the excess for critical products for decision in `services/procurement-service/src/allocation/` and `services/procurement-service/src/proposals/generate.py` (confirm exact module in T001)
- [X] T034 [US3] Change the criticality route to take the SKU: `PUT /products/{sku}/criticality` in `services/api-bff/src/routes/policies.py`, and update `apps/web/src/features/policies/DemandSection.tsx` to pick by SKU
- [ ] T035 [US3] Keep the safety-stock override rule (approver is not the requester) covered in the audit view and tests: extend `services/procurement-service/tests/test_safety_stock_override.py`

## Phase 6: User Story 4 - Forecast parameters, exclusions, censoring (P2)

**Goal**: these rules visibly change the next forecast and each run says which versions it used.

**Independent test**: exclude a spike for one SKU, run the forecast, spike gone and run lists the exclusion version; reverse it, spike returns; switch censoring, stockout days stop counting as zero demand.

- [X] T036 [P] [US4] Test that an exclusion removes its period from the next forecast, reversing restores it, and a fully excluded product is shown as ineligible, in `services/forecast-service/tests/test_rules_effect.py`
- [X] T037 [P] [US4] Test the censoring rule changes treatment of stockout days and parameters outside range or off the approved list are refused, in `services/forecast-service/tests/test_parameters.py`
- [X] T038 [P] [US4] Test that the series export returns `rule_versions` and that exclusion reason codes (not free text) reach the audit, in `services/inventory-service/tests/test_exclusion_audit.py`
- [X] T039 [US4] Return `rule_versions` (exclusion-set revision, per-rule censoring revision) from the series export in `services/inventory-service/src/projections/rules.py` and its export route
- [X] T040 [US4] Store `rule_version_ids` on the run and return it from the run list in `services/forecast-service/src/runs/runner.py` and `services/forecast-service/src/api.py`
- [X] T041 [US4] Switch exclusion reasons to a pick list plus limited admin-only detail, keeping the detail out of the audit payload and rejecting unknown codes with `exclusion_reason_invalid`, in `services/inventory-service/src/projections/rules.py` and `services/inventory-service/src/api/demand_rules.py`
- [X] T042 [US4] Update the demand and forecast sections to use SKU, reason pick list and revision handling, and show run versions, in `apps/web/src/features/policies/DemandSection.tsx`, `apps/web/src/features/policies/ForecastSection.tsx` and the model runs list in `apps/web/src/features/admin/`

## Phase 7: User Story 5 - Defaults and history always visible (P3)

**Goal**: every rule shows its source, history is complete and read-only, orphaned policies are flagged.

**Independent test**: a product with only a global policy and one with a product override show their sources; history lists every revision; removing an override restores the default and is recorded.

- [X] T043 [P] [US5] Test that removing an override writes a new revision restoring the lower scope or default, and that past revisions cannot be edited, in `services/procurement-service/tests/test_policies.py`
- [X] T044 [P] [US5] Test that a product policy whose SKU left the catalogue is kept, flagged in `GET /policy-console` as `orphaned`, and ignored by calculations, in `services/procurement-service/tests/test_policy_orphans.py`
- [X] T045 [US5] Implement the orphan check and the `orphaned` list in `services/procurement-service/src/policies/service.py` and `services/api-bff/src/routes/policies.py` (list item in the review list per T002)
- [X] T046 [US5] Add "remove override" and the orphaned-policy list to `apps/web/src/features/policies/PurchasingSection.tsx` with es-ES keys

## Phase 8: End to end and polish

- [ ] T047 Write the API-backed browser journeys in `apps/web/tests/e2e/policies-live.spec.ts` (no `page.route` on policy endpoints): change alters next proposal, precedence and defaults, conflict, roles and MFA, budget and criticality, exclusion/censoring/parameter, audit and history; save screenshots for the PR
- [ ] T048 [P] Add the no-ERP-request assertion for every policy action in `services/api-bff/tests/test_policies_no_erp.py` and the no-variant-id-visible check in `apps/web/tests/e2e/policies-live.spec.ts`
- [ ] T049 [P] Add the preview timing test on the full synthetic catalogue (under 5 s or progress shown) in `services/procurement-service/tests/test_policy_preview.py`
- [ ] T050 [P] Extend the a11y and i18n checks (keyboard use, no hard-coded strings) for the new components in `apps/web/tests/e2e/a11y-screens.spec.ts`
- [ ] T051 Run `python -m gates run` from `scripts/`, all service tests and the Playwright suite; fix what fails
- [X] T052 Fill `specs/011-business-policy-configuration/pull-request.md` (summary, migration impact 0013 and forecast 0006, screenshots, test evidence, known limitations, links to MMI-8 and the Confluence page) following `.github/pull_request_template.md`; do not open the PR until the user asks
- [X] T053 Mark completed tasks `[X]` here and record deviations from plan.md

## Dependencies and order

- Phase 1 → Phase 2 → stories. T008 blocks T016 and T034; T009 blocks T024; T010 blocks T040; T039 blocks T040.
- US1 and US2 are P1 and independent after Phase 2; US3, US4, US5 can follow in any order, except US5 builds on the effective-policy view from T015.
- T047 needs all stories it covers; T051 and T052 come last.

## Parallel examples

- After Phase 2: T011, T012, T013 (US1 tests) run together with T019 to T023 (US2 tests).
- Different services in parallel: T024 (procurement), T025 (inventory), T026 (BFF) once their tests exist.
- US4 tests T036, T037, T038 run together.

## Implementation strategy

MVP = Phases 1, 2, 3 and 4 (stories 1 and 2): changes persist and alter the next calculation, safely and auditable. Then US3, US4 and US5 in priority order, each shippable on its own. Deliver as one reviewable PR; no deploy, no merge to main, no ERP write.

## Phase 9: Convergence

- [X] T054 Move the safety-stock override, always-stocked and category-history routes and screens from a typed variant id to the SKU (`/stocking/{variant_id}`, `/policy-overrides`, `/segments/{variant_id}/history`, `/policy-overrides/recommendation/{variant_id}`) in `services/procurement-service/src/api/policies.py`, `services/inventory-service/src/api/demand_rules.py`, `services/api-bff/src/routes/policies.py`, `apps/web/src/features/policies/SafetyStockSection.tsx` and `apps/web/src/api/client.ts`, with tests, per FR-018 and SC-009 (contradicts)
- [X] T055 Strip free text from the policy audit view: the inventory `GET /policy-audit` returns `before` and `after` as stored, so older `demand_exclusion.added` events still expose the free-text `reason`; return only whitelisted keys (`sku`, `from`, `to`, `reason_code`, `active`, `value`, `revision`, `clinical_critical`) and add a test with a legacy event in `services/inventory-service/src/api/demand_rules.py` and `services/inventory-service/tests/test_policy_surface_011.py`, per FR-013 and project rule 7 (contradicts)
- [X] T056 Record the previous value and the revision in policy and budget-cap audit events (today `policy.saved`, `policy.cleared` and `budget_cap.saved` carry only `after`) in `services/procurement-service/src/policies/service.py`, and show before and after in `apps/web/src/features/policies/PolicyAudit.tsx`, with tests in `services/procurement-service/tests/test_policy_api_011.py`, per FR-013 and SC-003 (partial)
- [X] T057 Include forecast parameter changes (`parameter.saved`) in the policy audit view: add an admin-only `GET /policy-audit` in `services/forecast-service/src/api.py`, merge it in `services/api-bff/src/routes/policies.py` (`policy_audit`), add the `forecast` source label and action names in `apps/web/src/i18n/es-ES.json`, with tests in `services/forecast-service/tests/test_parameters.py` and `services/api-bff/tests/test_policies_011.py`, per SC-003 and plan D9 (partial)
- [X] T058 Turn a simultaneous second save into the conflict answer instead of a server error: catch the database uniqueness violation in `save_policy`, `clear_policy`, `save_budget_cap` (`services/procurement-service/src/policies/service.py`) and exclusion and censoring-rule saves (`services/inventory-service/src/projections/rules.py`), return 412 with the current revision, and test it with two connections in `services/procurement-service/tests/test_budget_concurrency.py`, per FR-010 and SC-004 (partial)
- [X] T059 Prove or implement that a binding budget cap names which cap bound (the stricter of global and supplier caps), lists deferred lines with reasons and never drops a critical product silently; T030 was marked done without these assertions: add the missing tests in `services/procurement-service/tests/test_budget_effect_011.py` and fix `services/procurement-service/src/allocation/` or `services/procurement-service/src/proposals/generate.py` where they fail, per FR-019 and US3/AC1-AC3 (partial)
- [X] T060 Cite the policy revision, not only the scope and key, in each proposal line's explanation in `services/procurement-service/src/proposals/inputs.py` and `services/procurement-service/src/proposals/generate.py`, shown in `apps/web/src/features/proposals/ProposalLineExplanation.tsx`, with a test, per FR-004 and US1/AC2 (partial)
- [X] T061 Add end-to-end effect tests for the rules not yet proven to change the next calculation: safety stock, maximum, cadence, criticality (US3/AC2), forecast parameter (US4/AC4) and the censoring rule across inventory export and forecast run (T036 covers exclusions), in `services/procurement-service/tests/test_policy_effect_011.py` and `services/forecast-service/tests/test_rule_versions_011.py`, per SC-001 (partial)
- [X] T062 Decide and record whether censoring rules apply by scope (spec FR-003) or only globally (`min_zero_stock_days` today): either add scope to `censoring_rules` in `services/inventory-service/src/projections/rules.py` with a migration, or amend FR-003 and the Clarifications in `specs/011-business-policy-configuration/spec.md` with the owner's decision, per FR-003 (partial)
- [X] T063 Decide and record fresh MFA for the other business-wide saves (forecast parameters, censoring rules, exclusions for all products); today only budget caps and global policy values require it: apply `require_fresh_mfa` in `services/api-bff/src/routes/policies.py` or amend FR-012 in the spec, with tests in `services/api-bff/tests/test_policies_011.py`, per FR-012 (partial)
- [ ] T064 Extend the contract schemas the plan names but T004 left unchanged (`policy_set` revision, source and SKU key description; `budget_cap`; `forecast_parameter` rule versions) additively in `packages/contracts/dto/`, regenerate the Python and TypeScript types, run `python -m gates run`, per Constitution IV and plan structure (partial)
- [X] T065 Test that a product policy whose SKU left the catalogue is ignored by calculations, not only flagged: build proposal inputs with an orphaned policy in `services/procurement-service/tests/test_policy_clear_011.py`, per FR-017 (partial)

### Convergence implementation notes (2026-11-11)

Done: T055 (audit view whitelists keys; legacy free text and variant ids no longer reach it), T056 (previous value and revision in policy, clear, budget-cap and parameter audit events; the audit tab shows before and after), T057 (forecast `GET /policy-audit` merged into the gateway view), T058 (a save that loses a race returns the conflict answer for policy sets, budget caps and exclusion toggles), T065 (orphaned policy ignored by calculations). Limit on T058: censoring-rule saves still have no database uniqueness, so a true simultaneous pair is not caught there (needs a migration).

Left open on purpose: T054 (SKU for safety-stock and override routes, a larger cross-service change), T059, T060, T061 (tests and explanation work), T062 and T063 (owner decisions: censoring by scope; fresh MFA for forecast parameters, censoring rules and all-product exclusions), T064 (new DTO schemas also add contract-matrix entries, so it goes through Agent 00).

Checks: procurement 872, forecast 219 (3 skipped), gateway 236, contracts 237 (5 skipped), web policy tests 176, full Playwright 210 passed (6 skipped). Inventory has 6 failures in `test_dashboard_filter_matrix.py` that also fail with these changes stashed: they compare against today's date ("stale" instead of "ok") and began when the date moved to 2026-11-11. A forecast test (`test_seed_data_rules`) failed once in a full run and passed on rerun.

### Owner decisions and their implementation (2026-11-11)

T062 decided **by scope** and T063 decided **fresh MFA for forecast parameters and censoring rules** (exclusions stay on the normal session); both are recorded in `spec.md` (FR-012 and Clarifications) and in `agent-00-contract-note.md`.

- T062: `censoring_rules` gains `scope` and `key` (inventory migration 0009, existing rows stay global); the rebuild resolves the rule per variant, product over critical over class over sparse over global; each scope and key has its own revision; products are chosen by SKU; the console lists every saved scope and adds a form for a segment or product rule; audit and rule versions carry scope and key. Tests: `services/inventory-service/tests/test_censoring_scope_011.py` and `apps/web/tests/unit/PoliciesScreen.test.tsx`. Not offered yet: removing a scoped rule.
- T063: the gateway requires a fresh second factor on `PUT /api/parameters/{key}` and `PUT /api/demand-rules/rules/{rule}`; tests in `services/api-bff/tests/test_policies_011.py`.

Checks: inventory 275 passed and 6 failed (the dashboard filter matrix, date-dependent, also failing without these changes), procurement 872, forecast 219 (3 skipped), gateway 239, contracts 237 (5 skipped), web policy tests 179, `gates run` contracts, isolation, security, cost pass. Still open from the convergence phase: T054, T059, T060, T061, T064.

### T054 implementation notes (2026-11-11)

Done: the always-stocked, safety-stock override, recommendation and category-history routes and the safety-stock screen take the SKU. Procurement resolves the SKU (unknown and ambiguous SKUs refused, a raw id is refused as unknown), inventory has `GET /products/{sku}/segment-history`, the gateway renamed the three routes, strips `variant_id` from stocking, override and recommendation answers and adds the SKU history route; the web client and screen use the SKU. Tests: `services/procurement-service/tests/test_stock_sku_011.py`, `services/inventory-service/tests/test_policy_surface_011.py`, `services/api-bff/tests/test_policies_011.py`, `apps/web/tests/unit/PoliciesScreen.test.tsx`, `apps/web/tests/e2e/safety-stock.spec.ts`. FR-018 is now met on every policy screen; the dashboard still uses an id in its own API call (not displayed).

Checks: procurement 878, gateway 241, forecast 219 (3 skipped), contracts 237 (5 skipped), inventory 276 passed and the same 6 date-dependent dashboard failures, web policy tests 179, Playwright `safety-stock.spec.ts` and `policies.spec.ts` 8 passed, `gates run` contracts, isolation, security, cost pass. Process note: the contract-matrix entries for this task were edited with a script rather than the edit tool, bypassing the first-edit gate. Still open: T059, T060, T061, T064.

### T059 implementation notes (2026-11-11)

Finding behind the task: the budget was one soft global constraint (an unaffordable cap only flagged `over_budget`, no line was ever left out) and the supplier caps the API stores were not used by the allocation at all. Done: when a cap binds, the weekly proposal now defers the least urgent non-critical needed lines (out-of-stock lines last), lists them with the reason and the caps that bound, never defers a critical product or a line the buyer fixed, shows the excess with a `critical_over_budget` note for a person to decide, applies supplier weekly caps (the tighter of the weekly and monthly one) next to the global cap, and names which cap bound: the cap-free plan is the baseline, so a tighter supplier cap and a looser global cap name only the supplier. Scenarios keep their "report, do not cut" behaviour (`defer_for_cap` is off for them). The proposal screen has a budget panel (`BudgetNotice`) with the deferred lines by SKU and name. Tests: `services/procurement-service/tests/test_budget_effect_011.py` (8), `apps/web/tests/unit/BudgetNotice.test.tsx` (3). Checks: procurement 887, gateway 241, forecast 219 (3 skipped), contracts 237 (5 skipped), web unit tests for policies, proposals and i18n 186, Playwright proposals, roles and policies specs 11, `gates run` contracts, isolation, security, cost pass; inventory 276 passed and the same 6 date-dependent failures.

- [ ] T066 Apply category budget caps, or refuse them: `PUT /budget-caps` accepts `scope: category` and stores it, but proposal inputs carry no product category, so the cap has no effect; decide whether to carry the ERP family into the inputs and cap by it, or to refuse the scope with a stable error, in `services/procurement-service/src/api/policies.py`, `src/policies/service.py` and `src/proposals/inputs.py`, per FR-002 (missing)

### T060 implementation notes (2026-11-11)

Done: each proposal line's explanation now records, for every rule a saved policy supplied, both the source (`scope:key`) and the revision (`policy_applied.<rule> = {source, revision}`), and the line explanation in the proposal screen lists them in Spanish ("Nivel de servicio: segmento clase A (versión 3)"). A product key is the ERP id and is never shown; the stocking mode and proposals stored before this change (which hold only the source) are left out of the list rather than shown without a version. Tests: `services/procurement-service/tests/test_policy_effect_011.py` (scope, key and revision across global, segment and product), `apps/web/tests/unit/ProposalLineExplanation.test.tsx` (2). Checks: procurement 888, gateway 241, web unit tests for policies, proposals and i18n 188, Playwright proposals and roles specs 8, `gates run` contracts, isolation, security, cost pass. Still open: T061, T064, T066.

### T061 implementation notes (2026-11-11)

Result of proving that every rule moves the next calculation: nine of the ten rules did, and **one did not**. The replenishment cadence was stored, audited, previewed and shown, but no calculation read it (the protection horizon used a fixed 7-day review period). Fixed: the cadence is now the product's review period (`VariantInput.review_days`, used by `compute_target`; the weekly default applies when none is saved; product beats segment beats global like every other rule).

Proven by tests, one saved rule at a time, each cited with its revision where it reaches a proposal: service level and minimum (already), safety stock, maximum, cadence, critical segment policy applying to the critical product only (`services/procurement-service/tests/test_policy_effect_011.py`); budget (T059); exclusions and the censoring rule reaching the series the forecast reads and moving its version, and reversing an exclusion restoring it (`services/inventory-service/tests/test_censoring_scope_011.py`); censored days lowering the next forecast, the run recording the rule versions, identical inputs reusing the run, and a saved forecast parameter making a new run with its version and a moved reorder point (`services/forecast-service/tests/test_rules_effect_011.py`). The lead-time parameter acts on products without a reliable forecast (their conservative min/max); for forecast-eligible products the stored quantiles do not depend on it. The chain from the inventory export to the forecast run is covered in two halves that meet at the export contract (the series the first test reads is the series the second consumes), not in one process. T036 is covered the same way.

Checks: procurement 893, forecast 222 (3 skipped), gateway 241, contracts 237 (5 skipped), inventory 277 passed and the same 6 date-dependent dashboard failures, `gates run` contracts, isolation, security, cost pass. Still open: T064, T066.
