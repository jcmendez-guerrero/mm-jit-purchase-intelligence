---

description: "Task list for fixing the supplier terms keyboard edit (MMI-12)"
---

# Tasks: Fix Supplier Terms Keyboard Edit (e2e gate)

**Input**: Design documents from `/specs/014-fix-supplier-terms-keyboard-edit/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md (no `contracts/`: no interface changes)

**Tests**: Requested by the spec (FR-005, FR-006): the quarantined e2e check returns and a regression case is added.

**Organization**: Grouped by user story. Synthetic fixtures only; never contact a real Siweb host.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1, US2, US3 from spec.md
- All paths are relative to the repository root

## Phase 1: Setup

**Purpose**: Be able to run the check locally

- [ ] T001 Install web dependencies and the Chromium browser for Playwright (`npm ci` and `npx playwright install chromium` in `apps/web`), as in `specs/014-fix-supplier-terms-keyboard-edit/quickstart.md`

---

## Phase 2: Foundational — find the root cause (blocks all stories)

**Purpose**: FR-004. The fix site (screen or test) is unknown until the failure is reproduced.

**⚠️ CRITICAL**: No fix starts until T003 names the cause.

- [ ] T002 Reproduce the failure: change `test.fixme(` to `test(` on "reference task 3 by keyboard: edit one supplier term and save it" in `apps/web/tests/e2e/a11y-all-routes.spec.ts` and run it with `--trace on`; confirm it saves `lead_time_days` 3
- [ ] T003 Test hypotheses H1–H4 from `specs/014-fix-supplier-terms-keyboard-edit/research.md` in order (focused element id after `tabTo`, input value after `ControlOrMeta+a` and typing, network calls and form value before save, request body against the visible value) and write the confirmed cause, the evidence and whether the fix is in the screen or in the check under "Root cause" in `specs/014-fix-supplier-terms-keyboard-edit/research.md`

**Checkpoint**: Cause recorded; US1 fix site known.

---

## Phase 3: User Story 1 - A keyboard-typed supplier term is the value that gets saved (Priority: P1) 🎯 MVP

**Goal**: Keyboard and mouse edits of a term save exactly what was typed.

**Independent Test**: Supplier with lead time 3, replace with 7 by keyboard, reason, Enter: saved lead time is 7.

### Tests for User Story 1 ⚠️

> Write these first and keep the reproduced failure (T002) in view before changing the fix site.

- [ ] T004 [P] [US1] Add a keyboard-only e2e case that edits the money term "Pedido mínimo" (`min_order_value`) and asserts the saved string, in `apps/web/tests/e2e/a11y-all-routes.spec.ts` (FR-006, SC-004)
- [ ] T005 [P] [US1] Add unit cases that `toPayload` returns the typed lead time and minimum order value (including Spanish decimal input such as `12,50`) in `apps/web/tests/unit/terms-model.test.ts`

### Implementation for User Story 1

- [ ] T006 [US1] Apply the fix at the site named in T003: the editor in `apps/web/src/features/suppliers/SupplierTermsEditor.tsx` (or `apps/web/src/features/suppliers/SuppliersScreen.tsx`, `apps/web/src/ui/FormField.tsx`) if the screen loses the typed value, otherwise correct the field lookup and key sequence in `apps/web/tests/e2e/a11y-all-routes.spec.ts`; if the cause is a duplicate lead-time label, scope the lookups to the terms form
- [ ] T007 [US1] If the screen was changed, add a component test that types a value, saves, and asserts the value in the request (mocked API, synthetic supplier) in `apps/web/tests/unit/SuppliersScreen.test.tsx`

**Checkpoint**: Keyboard and mouse edits save the typed lead time and minimum order value.

---

## Phase 4: User Story 2 - Typed input is never overwritten by late-arriving data (Priority: P2)

**Goal**: A slow terms response never replaces typed input or lets the buyer save unseen terms.

**Independent Test**: Delay the terms response; fields stay locked until it arrives, then the typed value is preserved on save.

### Tests for User Story 2 ⚠️

- [ ] T008 [US2] Add an e2e case that delays `GET /api/suppliers/s1/terms`, asserts the lead-time field is disabled while loading, and that after loading a keyboard edit saves the typed value, in `apps/web/tests/e2e/a11y-all-routes.spec.ts` (same file as T004: do it after T004)

### Implementation for User Story 2

- [ ] T009 [US2] Verify the existing lock (`readOnly = !canEdit || view === null`) satisfies T008; only if it does not, fix `apps/web/src/features/suppliers/SupplierTermsEditor.tsx` so editing is prevented or typed input preserved until the first load completes (any new loading text goes in the Spanish locale resources, no hard-coded strings)
- [ ] T010 [US2] Replace the timing workaround in the keyboard check (the `toHaveValue("3")` wait) with an explicit "field is enabled" wait, in `apps/web/tests/e2e/a11y-all-routes.spec.ts`

**Checkpoint**: US1 and US2 pass independently.

---

## Phase 5: User Story 3 - The end-to-end gate proves keyboard editing again (Priority: P3)

**Goal**: The check is active, stable, and the gate no longer fails because of it.

**Independent Test**: `--repeat-each=20` passes 20 of 20; `python -m gates run` shows no `e2e` failure from this check.

- [ ] T011 [US3] Confirm no `test.fixme` or skip remains for this check and that no comment still calls it quarantined in `apps/web/tests/e2e/a11y-all-routes.spec.ts`
- [ ] T012 [US3] Run the keyboard checks with `npx playwright test tests/e2e/a11y-all-routes.spec.ts -g "reference task 3" --repeat-each=20` from `apps/web` and record 20 of 20 in `specs/014-fix-supplier-terms-keyboard-edit/quickstart.md` under a "Results" heading
- [ ] T013 [US3] Run `npm test` and the full `npx playwright test` in `apps/web`, then `python -m gates run` from `scripts/`, and record that the `e2e` gate no longer fails because of this check (SC-002)

**Checkpoint**: All three stories verified.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T014 [P] Mark the MMI-12 references as resolved in `docs/architecture/integration/verification.md`, `docs/architecture/integration/feature-status.md`, `docs/architecture/integration/feature-status.json` and `specs/013-procurement-proposals-scenarios/pull-request.md`
- [ ] T015 [P] Confirm FR-007 and SC-005: the diff touches no validation, versioning, permission, audit or ERP code (review `git diff main --stat`)
- [ ] T016 Fill the PR from `.github/pull_request_template.md` (data, security, cost, contract impact: none) with the root cause and the 20-run result, and mark the finished tasks `[X]` in `specs/014-fix-supplier-terms-keyboard-edit/tasks.md`

---

## Dependencies & Execution Order

- **Phase 1** (T001) → **Phase 2** (T002 → T003) → stories.
- **US1** needs T003 (fix site). **US2** can start after T003 and edits the same e2e file as US1, so T008 and T010 follow T004. **US3** needs US1 and US2 done.
- Within US1: T004 and T005 in parallel, then T006, then T007.
- **Polish** after US3.

### Parallel Opportunities

- T004 (e2e file) and T005 (`terms-model.test.ts`) are different files.
- T014 and T015 are independent.
- Most tasks edit `a11y-all-routes.spec.ts`; do not run those in parallel.

## Implementation Strategy

### MVP first (User Story 1)

1. T001, then T002–T003 (reproduce and name the cause).
2. T004–T007 (regression tests, fix).
3. **Stop and validate**: the keyboard check and the money-term case pass.

### Incremental delivery

1. MVP above, then US2 (loading guarantee and a non-timing wait), then US3 (stability, gate), then polish.

## Notes

- [P] tasks = different files, no dependencies.
- Commit after each task or logical group; keep the change small and test-first.
- If T003 shows the defect is only in the test, T006 is a test-only change and T007 is skipped.
