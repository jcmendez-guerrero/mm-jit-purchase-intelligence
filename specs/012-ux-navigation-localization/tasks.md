# Tasks: UX, Navigation & Spanish Localization (Agent 08)

**Input**: Design documents from `specs/012-ux-navigation-localization/` (spec.md, plan.md, research.md, data-model.md, contracts/ui-localization-contract.md, quickstart.md)

**Prerequisites**: plan.md, spec.md. Tests come before implementation within each story (project rule); all fixtures synthetic.

**Format**: `- [ ] T### [P?] [US?] Description with file path`. `[P]` = different files, no dependency on an unfinished task. Paths are relative to the repository root; `web/` means `apps/web/`.

**Rules for every task**: presentation, wording and interaction only; no API, contract, ERP or business-rule change (FR-016). A fix inside another feature's screen is allowed (FR-015) but must be logged in the Agent 00 note (T002). Mark `[X]` when done. Task IDs T021–T051 were added after the analysis pass and sit in the phase where they belong.

---

## Phase 1: Setup

- [X] T001 Create `specs/012-ux-navigation-localization/evidence/` with `audit-inventory.md` (table: area, item, status complete/partial/broken/missing/unverified, evidence file:line, decision reuse/fix/build, owning feature) per data-model.md "Audit inventory item"
- [X] T002 [P] Create `specs/012-ux-navigation-localization/agent-00-contract-note.md` with an empty table (feature, file, change, reason, shared-or-screen-level) to log cross-feature changes for Agent 00 (FR-015)

---

## Phase 2: Foundational (blocks every story)

**Audit and the checks that make gaps visible. Nothing in Phase 3+ starts before T003–T011 are done.**

- [X] T003 Audit navigation: for each entry in `web/src/app/routes.ts` and each role (viewer, buyer, approver, admin) record offered/hidden, label and description keys, quick-jump behaviour, no-access and not-found screens in `evidence/audit-inventory.md` (FR-001, FR-002, FR-003)
- [X] T004 Audit text and formats: scan `web/src/features/**`, `web/src/app/**`, `web/src/ui/**` for user text outside the catalogue (`.ts` models, notices, export headers, accessible names, placeholders), non-Spanish text, and amounts/dates/numbers shown without `web/src/i18n/formatters.ts`; record file:line in `evidence/audit-inventory.md` (FR-006, FR-008)
- [X] T005 Audit states, help, accessibility and responsive: for each screen record loading/empty/error/success handling (uses `ScreenState` or not), contextual help presence, focus handling in dialogs/drawer/palette, chart table alternatives, 1280/768/375 px behaviour; record in `evidence/audit-inventory.md` (FR-011–FR-014)
- [X] T006 Audit the journeys: walk dashboard → product detail (`web/src/features/dashboard/ProductDetail.tsx`) → supplier/proposal and supplier search → terms → import (`web/src/features/suppliers/*`); record broken or missing steps, any ERP id shown instead of SKU, any amounts computed in the browser (research R6) in `evidence/audit-inventory.md` (FR-004, FR-005)
- [X] T007 [P] Add `web/src/i18n/glossary.json` (concept, preferred es-ES term, forbidden variants, Spanish definition) seeded from terms found in T004 (FR-009)
- [X] T008 [P] Write glossary test `web/tests/unit/glossary.test.ts`: every entry complete; no catalogue value in `web/src/i18n/es-ES.json` contains a forbidden variant
- [X] T009 Extend `web/tests/unit/i18n-coverage.test.ts`: also scan `.ts` files under `web/src/features` and `web/src/app` for user-text literals (labels, notices, export headers), keep the self-check, keep `hardcoded-strings.baseline.json` empty; add a check for unused and empty catalogue keys (FR-007) [FR-006, FR-007, SC-003]
- [X] T010 [P] Write `web/tests/unit/nav-role-matrix.test.ts`: for viewer, buyer, approver, admin assert the offered routes equal the expected set derived from `routes.ts` and reported capabilities; every `labelKey`/`descriptionKey` exists in the catalogue (SC-001) [FR-002, SC-001]
- [X] T011 [P] Write `web/tests/unit/screen-states.test.tsx`: render each screen with mocked loading, empty, error responses and assert Spanish content, retry button, input preserved, no technical detail (FR-010, FR-011, SC-006) [FR-010, FR-011, SC-006]

**Checkpoint**: audit complete, new checks written and failing where gaps exist.

---

## Phase 3: User Story 1 - Find any task from the navigation (P1)

**Goal**: every role reaches exactly its screens; forbidden and unknown addresses explain themselves.
**Independent test**: sign in as each role, open every offered screen from the rail and the quick-jump, open a forbidden and an unknown address.

- [X] T012 [P] [US1] E2E `web/tests/e2e/navigation.spec.ts` (extend): per role, rail and quick-jump list the expected screens; keyboard-only open lands focus on the page heading; current screen indicated; forbidden and unknown addresses show the Spanish screens with a way back
- [X] T013 [P] [US1] E2E role-change case in `web/tests/e2e/roles.spec.ts` (extend): a role change while a screen is open updates the offer without a stale entry (edge case)
- [X] T014 [US1] Fix navigation gaps from T003 in `web/src/app/routes.ts`, `web/src/app/Navigation.tsx`, `web/src/app/CommandPalette.tsx`, `web/src/app/NoAccess.tsx`, `web/src/app/NotFound.tsx`; make T010 and T012 pass
- [X] T015 [US1] Add a visible step indicator and "back to list" to multi-step workflows (proposal review) in `web/src/features/proposals/ProposalsScreen.tsx` if T003/T006 show it missing; add catalogue keys in `web/src/i18n/es-ES.json`

---

## Phase 4: User Story 2 - Product journey (P1)

**Goal**: dashboard signal → product detail by SKU → supplier/proposal → back, with context preserved.
**Independent test**: as buyer with synthetic data, complete the journey keyboard-only.

- [X] T016 [P] [US2] E2E `web/tests/e2e/journey-product.spec.ts` (new): at-risk product on dashboard → detail shows SKU, stock, supplier terms, quality warning → link to supplier and to a proposal line → back to the same product; product with missing data shows what is missing and what to do; no ERP id visible
- [X] T017 [P] [US2] Unit `web/tests/unit/dashboard-sku-display.test.tsx` (extend): SKU shown and entered in product detail, drill-down and proposal lines; no internal id rendered
- [X] T018 [US2] Fix product-journey gaps from T006 in `web/src/features/dashboard/ProductDetail.tsx`, `DrillDownPanel.tsx`, `SupplierPanel.tsx`, `web/src/features/proposals/ProposalLineExplanation.tsx` (links with preserved context, back links, missing-data messages)
- [X] T019 [US2] Add catalogue keys for new messages in `web/src/i18n/es-ES.json`

---

## Phase 5: User Story 3 - Supplier journey (P1)

**Goal**: search → terms → edit or import → confirmation, with Spanish validation and unsaved-change protection.
**Independent test**: as buyer, edit with an invalid value, correct, leave with and without unsaved changes, import a file with a rejected row.

- [X] T020 [P] [US3] E2E `web/tests/e2e/journey-supplier.spec.ts` (new): search and open supplier, invalid save names field and rule in Spanish and focuses the first error, unsaved-change prompt on leaving, import lists rejected rows with reasons
- [X] T021 [P] [US3] Extend `web/tests/e2e/roles.spec.ts` and `dashboard-roles.spec.ts`: on the product and supplier screens, viewer, approver and admin see each action offered, hidden or read-only exactly as the role matrix says (FR-017) [FR-017]
- [X] T022 [P] [US3] Unit `web/tests/unit/SupplierManagement.test.tsx` and `SupplierImport.test.tsx` (extend): field-level messages, focus on first error, rejected rows never dropped silently
- [X] T023 [US3] Fix supplier-journey gaps from T006 in `web/src/features/suppliers/SupplierForm.tsx`, `SupplierTermsEditor.tsx`, `SupplierImport.tsx`, `SupplierReview.tsx`, `LinksPanel.tsx`, `BulkAssign.tsx`, `OverrideEditor.tsx`; reuse `web/src/ui/useFieldErrors.ts` and `useUnsavedChanges.ts`
- [X] T024 [US3] Add catalogue keys in `web/src/i18n/es-ES.json`

---

## Phase 6: User Story 4 - Correct Spanish and Spanish formats (P1)

**Goal**: zero untranslated or inconsistent text; euro, date and number formats everywhere, including exports.
**Independent test**: T009, T008 and T011 pass; every screen reviewed in each state.

- [X] T025 [P] [US4] Unit `web/tests/unit/i18n.test.ts` (extend): amounts, dates (Spanish format, local zone, daylight-saving boundary), quantities, percentages, and export headers use the shared formatters [FR-008, SC-007]
- [X] T026 [P] [US4] Unit `web/tests/unit/api-errors.test.ts` (extend): every code in `packages/contracts/errors/error_codes.json` maps to a Spanish message with a next step; unknown code gives the generic message; raw code never shown [FR-010, SC-005]
- [X] T027 [P] [US4] Unit `web/tests/unit/i18n.test.ts` (extend): a catalogue key missing at runtime renders a readable Spanish fallback, never the raw key, and is reported to the console in development (edge case) [FR-006]
- [X] T028 [P] [US4] Unit `web/tests/unit/no-erp-notes.test.tsx` (new): with a synthetic fixture whose product and supplier carry a free-text note, no screen, help text or CSV export shows the note text, only the "has note" indicator (FR-016, project rule 7) [FR-016]
- [X] T029 [US4] Move all user text found in T004 into `web/src/i18n/es-ES.json` and replace literals with `t()` in `web/src/features/**` and `web/src/app/**` (`.tsx` and `.ts`), grouped by feature; make T009, T027 and T028 pass with an empty baseline; implement the Spanish missing-key fallback in `web/src/i18n/index.ts`
- [X] T030 [US4] Apply glossary terms (T007) across `web/src/i18n/es-ES.json`; fix any value flagged by T008
- [X] T031 [US4] Replace ad-hoc number, date and currency formatting found in T004 with `web/src/i18n/formatters.ts`, including CSV export headers and values in `web/src/features/proposals/` and `web/src/features/dashboard/`; confirm no amount is summed or rounded in the browser (R6) and record any exception in `evidence/audit-inventory.md`

---

## Phase 7: User Story 5 - Loading, empty, error and help states (P2)

**Goal**: every data screen has all four states; contextual help available and keyboard-operable.
**Independent test**: T011 passes for every screen; help opens and closes by keyboard.

- [X] T032 [P] [US5] Unit `web/tests/unit/ui/HelpHint.test.tsx` (new): button with accessible name, opens a glossary definition, closes with Escape, returns focus, never renders free-text notes [FR-012]
- [X] T033 [P] [US5] E2E `web/tests/e2e/states.spec.ts` (extend): forced loading (placeholder appears if data takes more than 300 ms; cumulative layout shift ≤ 0.1 when data arrives), empty (reason and action), error (retry, input preserved) on each screen
- [X] T034 [US5] Add `web/src/ui/HelpHint.tsx` (accessible disclosure fed by `glossary.json`) only if T005 confirms none exists; export from the shared UI [FR-012]
- [X] T035 [US5] Migrate screens that bypass `ScreenState` (from T005) to `web/src/ui/ScreenState.tsx` in `web/src/features/**`; fix loading placeholders to match layout
- [X] T036 [US5] Place `HelpHint` next to key terms (stock de seguridad, plazo de entrega, cobertura, nivel de servicio) in `web/src/features/policies/*` and `web/src/features/dashboard/*`; add catalogue keys [FR-012]

---

## Phase 8: User Story 6 - Accessibility, zoom and screen sizes (P2)

**Goal**: no serious or critical axe violations on every route at 1280, 768 and 375 px in light and dark; focus management; no colour-only status.
**Independent test**: run the matrix; complete the journeys keyboard-only.

- [X] T037 [P] [US6] E2E `web/tests/e2e/a11y-all-routes.spec.ts` and `a11y-screens.spec.ts` (extend): run every route at 1280, 768 and 375 px in light and dark appearance (clarification 4) [FR-013, SC-004]
- [X] T038 [P] [US6] E2E `web/tests/e2e/responsive.spec.ts` and `touch-targets.spec.ts` (extend): same three sizes; no horizontal page scroll at 375 px or 200% zoom except inside tables; very long product and supplier names, 500+ rows and amounts of 9 digits wrap or truncate with the full value available
- [X] T039 [P] [US6] E2E focus checks in `web/tests/e2e/forms-feedback.spec.ts` (extend): dialog, drawer and palette trap focus, close on Escape, return focus to the trigger [FR-013]
- [X] T040 [US6] Fix axe, focus, contrast, table-alternative and colour-only-status findings in `web/src/ui/**`, `web/src/app/Drawer.tsx`, `web/src/app/CommandPalette.tsx`, `web/src/features/dashboard/ChartWithTable.tsx` and affected screens; log in `specs/012-ux-navigation-localization/agent-00-contract-note.md`
- [X] T041 [US6] Fix responsive and zoom findings in `web/src/styles/**` and affected screens; confirm the bundle budget still holds (`npm run check:bundle`)

---

## Phase 9: Polish & cross-cutting

- [X] T042 Update `evidence/audit-inventory.md` so no item remains "unverified"; mark each as complete after fixes, or list it under known limitations
- [X] T043 Capture Spanish-UI screenshots with synthetic data for navigation, product journey, supplier journey, states and one a11y run into `specs/012-ux-navigation-localization/evidence/` (FR-018)
- [X] T044 Run all quickstart steps in `specs/012-ux-navigation-localization/quickstart.md` plus `python -m gates run` from `scripts/`; record results in `evidence/verification.md` [SC-008]
- [ ] T045 Prepare a short usability script (product journey and supplier journey, synthetic data, buyer role) and record the result of one moderated run, time per journey and problems found, in `specs/012-ux-navigation-localization/evidence/usability.md`; reported, not a gate (SC-002) [SC-002]
- [X] T046 Write `specs/012-ux-navigation-localization/pull-request.md` (change summary, screenshots, test evidence, cross-feature changes, risks, known limitations, links to MMI-10 and the Confluence page) and mark completed tasks `[X]` here

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 (T003–T006 audits before fixes; T007–T011 can run in parallel with each other after T004).
- Phase 3–8 depend on Phase 2. Within a phase, tests (`[P]`) first and failing, then fixes.
- US1, US2, US3 and US4 are independent after Phase 2; US4 (T029–T031) touches the same screens as US2/US3, so do US2 and US3 before US4 or coordinate by file. US5 depends on T007 (glossary). US6 runs last on the finished screens.
- T008 and T009 intentionally fail from Phase 2 until T029/T030 land; this is one pull request, so do not merge or push to a protected branch mid-way.
- Shared component and catalogue changes (T034, T040, T030) land before screen-level fixes that depend on them.

## Parallel Examples

- Phase 2: T007, T008, T010, T011 together after T004.
- US2 and US3 tests: T016, T017, T020, T022 together.
- US6 tests: T037, T038, T039 together.

## Implementation Strategy

- **MVP**: Phase 1, Phase 2 and US1 (navigation proven for every role) plus US4's T029 (no untranslated text), since the Jira gate is "no untranslated text".
- **Then**: US2 and US3 (journeys), US5, US6, polish.
- Stop and demonstrate after each story; the cross-feature note (`agent-00-contract-note.md`) is sent to Agent 00 at the end of Phase 3 and again before the pull request.

## Phase 10: Convergence

- [X] T047 Inventory every place that shows the Siweb variant id (`web/src/features/quality/QualityScreen.tsx:71,111`, `admin/AdminStatusScreen.tsx:130`, `policies/SafetyStockSection.tsx:143`, `policies/DemandSection.tsx:95`, `scenarios/ScenariosScreen.tsx:220,259`, `proposals/ProposalsScreen.tsx:196`, catalogue `policies.preview.row`, `scenarios.change_row`, `safety.queue_row`, `demand.variant_n`) in `evidence/audit-inventory.md`, and list in `agent-00-contract-note.md` which API payloads need a `sku` field per FR-004 (contradicts)
- [X] T048 Add a shrink-only guard test `web/tests/unit/no-variant-id-display.test.tsx` with a baseline of the files from T047 that render `variant_id`, so no new screen shows the Siweb id per FR-004 (contradicts)
- [X] T049 Switch the places from T047 whose payload already carries a SKU (the `#variant_id` fallback in `web/src/features/proposals/ProposalsScreen.tsx:196` first) to show the SKU, and lower the T048 baseline per FR-004 (contradicts)
- [ ] T050 Once Agent 00 provides a SKU-to-variant lookup, replace the typed variant id with SKU entry in `web/src/features/suppliers/OverrideEditor.tsx`, `web/src/features/policies/SafetyStockSection.tsx` and `web/src/features/policies/DemandSection.tsx`, remove `KNOWN_EXCEPTIONS` in `web/tests/unit/glossary.test.ts`, and cover it in the supplier journey test per FR-004 and FR-005 (contradicts)
- [X] T051 [P] Add `HelpHint` for plazo de entrega beside `lead_time_days` in `web/src/features/suppliers/SupplierTermsEditor.tsx` and for cobertura on the coverage indicator in `web/src/features/dashboard/IndicatorCard.tsx`, with unit tests per FR-012 and US5/AC4 (partial)
- [X] T052 [P] Triage the 95 keys in `web/tests/unit/unused-keys.baseline.json`: delete the keys nothing uses from `web/src/i18n/es-ES.json`, and keep only keys reached through a dynamic prefix, noting the prefix per FR-007 (partial)
- [X] T053 Run the `e2e`, `security` and `cost` gates (`python -m gates run` from `scripts/` with `pytest` installed) and record the result in `evidence/verification.md` per SC-008 (partial)

## Phase 11: Convergence

- [ ] T054 Once Agent 00 adds a `sku` field to the quality items, administration policy history, safety-stock queue, demand exclusions, policy preview and scenario lines, show the SKU in `web/src/features/quality/QualityScreen.tsx`, `admin/AdminStatusScreen.tsx`, `policies/SafetyStockSection.tsx`, `policies/DemandSection.tsx`, `policies/PurchasingSection.tsx` and `scenarios/ScenariosScreen.tsx`, and empty `web/tests/unit/variant-id-display.baseline.json` per FR-004 (contradicts)
- [X] T055 [P] Add a test with 500 or more rows and amounts of 9 digits on the proposals and costs screens: no horizontal page scroll, Spanish euro format and the full value reachable, in `web/tests/e2e/states.spec.ts` per Edge Cases and FR-014 (partial)
- [X] T056 [P] Add a test that a failed save keeps what the person typed and offers a retry, on the supplier terms form (`web/tests/e2e/journey-supplier.spec.ts`) per US5/AC3 (partial)
- [X] T057 [P] Check the headers and values of the proposal CSV and Excel exports and the audit CSV (dot or comma decimals, date format, euro), record the result in `evidence/verification.md`, and add a unit test for any export the web app builds itself per FR-008 and SC-007 (partial)

## Phase 12: Convergence

- [ ] T058 Once Agent 00 and feature 010 make the audit CSV (`services/api-bff/src/routes/admin_audit.py`) use Spanish headers, `;` and `dd/mm/aaaa` dates like the proposal exports, check it with the same read-through as T057, record the result in `evidence/verification.md`, and align the download name in `web/src/features/admin/AuditScreen.tsx` per FR-008 and SC-007 (contradicts)
- [ ] T059 [P] Record the owner's answer on the "Variante (ID Siweb)" column of the proposal exports in `agent-00-contract-note.md`, and if it is dropped, confirm the export no longer carries it per FR-004 (partial)

## Phase 13: Convergence

- [ ] T060 Check which of T050 and T054 PR 22 (open) and PR 18 (merged) already unblock, switch the screens whose lookup or `sku` field now exists in `web/src/features/suppliers/OverrideEditor.tsx`, `web/src/features/policies/SafetyStockSection.tsx`, `web/src/features/policies/DemandSection.tsx` and the other five screens listed in `evidence/audit-inventory.md`, lower `web/tests/unit/variant-id-display.baseline.json`, and answer Agent 00 on PR 24 with what is still blocked per FR-004 and Agent 00 comment 1 (contradicts)
- [X] T061 Put the original sentence back in `errors.auth_forbidden_role` in `web/src/i18n/es-ES.json` ("No tiene permiso para realizar esta acción.") and list that key as an exception in the next-step test in `web/tests/unit/api-errors.test.ts`, because the no-access box already gives the next step per review finding 1 (partial)
- [X] T062 [P] Add a test in `web/tests/unit/i18n-coverage.test.ts` that every literal key passed to `t(` in `web/src` exists in `web/src/i18n/es-ES.json`, now that a missing key shows a fallback instead of failing visibly per FR-007 and review finding 2 (partial)
- [X] T063 [P] Make the loading placeholder of `web/src/features/admin/AdminStatusScreen.tsx` match the loaded height so the layout shift in `web/tests/e2e/states.spec.ts` is well under 0.1 (now about 0.094) per FR-011 and review finding 3 (partial)
- [ ] T064 Decide with the owner whether the catalogue uses formal or informal address, write the choice in `web/src/i18n/glossary.json` or the spec, convert `web/src/i18n/es-ES.json` to it, and add a test that flags the other form per Agent 00 comment 5 and FR-009 (partial)
- [X] T065 After PR 22 merges, merge `main` into this branch, resolve the conflicts in `web/src/api/client.ts`, `web/src/i18n/es-ES.json` and the policy and dashboard screens, and rerun unit, lint, build and Playwright per Agent 00 comment 6 (partial)
- [X] T066 [P] Make closing the product detail replace the history entry (`replace: id === null`) in `web/src/app/App.tsx`, with a Playwright check that Back after closing leaves the panel per US1 and review finding 4 (partial)

## Phase 14: Convergence

- [X] T067 Write the four owner requests, schema first, in `evidence/owner-requests.md` (a `sku` in the data-quality items for inventory; a `sku` in the policy history for procurement or forecast; a `sku` in scenario changes and lines for procurement; a SKU route for the `product-suppliers` overrides for procurement) and open each with its owner, so T050 and T054 can proceed, per Agent 00 re-review 2 and FR-004 (contradicts)
- [ ] T068 Ask the owner of PR 25 whether any ERP hand-off needs the "Variante (ID Siweb)" column of the proposal exports; if none does, request its removal in `services/procurement-service/src/proposals/export.py` and its locale file, record the answer in `agent-00-contract-note.md`, and close T059 per Agent 00 re-review 1 and FR-004 (contradicts)
- [ ] T069 [P] Extend T065: when merging `main` after PR 22 and PR 25 land, also resolve the conflict in `web/src/features/proposals/ProposalsScreen.tsx` (PR 25), besides `PurchasingSection.tsx` and `web/src/i18n/es-ES.json` (PR 22), then rerun unit, lint, build and Playwright per Agent 00 re-review, merge order (partial)
