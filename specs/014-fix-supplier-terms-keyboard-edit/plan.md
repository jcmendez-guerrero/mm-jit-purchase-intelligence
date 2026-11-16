# Implementation Plan: Fix Supplier Terms Keyboard Edit (e2e gate)

**Branch**: `claude/jira-spec-mmi-12-c32d10` | **Date**: 2026-11-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/014-fix-supplier-terms-keyboard-edit/spec.md`

## Summary

The quarantined e2e check "reference task 3 by keyboard" saves lead time `3` instead of `7`. Plan: first **reproduce and name the root cause** (screen defect or test defect, see [research.md](research.md)), fix it where it lives, add a regression check for a numeric and a money term, remove `test.fixme`, and prove stability with 20 consecutive runs. No backend, contract, data or ERP change.

## Technical Context

**Language/Version**: TypeScript, React (apps/web); Playwright for e2e

**Primary Dependencies**: React, react-i18next, `@playwright/test`, `@axe-core/playwright` (all already in the workspace manifest)

**Storage**: N/A (the screen's form state only; the terms API is mocked in the e2e check)

**Testing**: Playwright e2e (`apps/web/tests/e2e/a11y-all-routes.spec.ts`), Vitest unit tests for `termsModel` and the editor; synthetic fixtures only

**Target Platform**: Web app, desktop browsers (keyboard-only and assistive technology)

**Project Type**: Web application (frontend only for this fix)

**Performance Goals**: None new; the keyboard task completes in under 1 minute for a person (SC-003)

**Constraints**: es-ES text only; no change to versioning, validation, roles, audit or ERP requests (FR-007); `npm ci` and Playwright browsers must be installed before the check can run (not installed in this worktree at planning time)

**Scale/Scope**: One screen (`SupplierTermsEditor`), one e2e test, possibly one shared field component (`ui/FormField`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Note |
|-----------|--------|------|
| I. Least-privilege integrations | Pass | No ERP request added or changed; mocked API in tests |
| II. Privacy and synthetic data | Pass | Fixtures are the existing synthetic supplier ("Proveedor Sintético A") |
| III. Explainable and human-controlled purchasing | Pass | Buyer still reviews and saves; no autonomous write |
| IV. Contract-first service boundaries | Pass | No schema or API change (no `contracts/` needed) |
| V. Testable, observable, cost-bounded delivery | Pass | Adds regression tests, re-enables the gate; no new infrastructure or cost |

Post-design re-check: still Pass (the design adds tests and at most a small UI state change).

## Project Structure

### Documentation (this feature)

```text
specs/014-fix-supplier-terms-keyboard-edit/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
└── tasks.md              # created by /speckit-tasks
```

No `contracts/` directory: the feature exposes no new or changed interface.

### Source Code (repository root)

```text
apps/web/
├── src/
│   ├── features/suppliers/
│   │   ├── SupplierTermsEditor.tsx   # form state, load, save (likely fix site)
│   │   ├── termsModel.ts             # text form <-> payload, validation
│   │   └── SuppliersScreen.tsx       # mounts the terms editor and OverrideEditor
│   └── ui/FormField.tsx              # shared labelled input (change only if the cause is here)
└── tests/e2e/a11y-all-routes.spec.ts # remove test.fixme; add numeric + money regression
```

**Structure Decision**: Existing web app layout; changes are confined to the suppliers feature and its e2e test.

## Complexity Tracking

No constitution violations; nothing to justify.
