# Implementation Plan: UX, Navigation & Spanish Localization (Agent 08)

**Branch**: `claude/speckit-specify-mmi-10-ccce8a` | **Date**: 2026-11-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/012-ux-navigation-localization/spec.md`

## Summary

Audit the current main branch against the spec, then close only the gaps found in navigation, the product and supplier journeys, Spanish text and formats, screen states, contextual help and accessibility. The work is presentation, wording and interaction in the existing web app. It reuses what feature 003 built (route registry, shared components, Spanish catalogue, formatters, i18n coverage test, axe and responsive end-to-end suites) and adds: an evidence-backed audit inventory, a business glossary, a tightened untranslated-text check, a screen-state and error-message coverage check, a role-by-route navigation matrix test, the two buyer journey end-to-end tests, and the screen-level fixes the audit proves necessary. No backend, contract, ERP or data change.

## Technical Context

**Language/Version**: TypeScript 5.6 on Node 20+, React 18 (existing `apps/web`)

**Primary Dependencies**: Existing only: react-router, i18next / react-i18next, recharts, vitest, Testing Library, Playwright, axe-core. No new runtime dependency.

**Storage**: N/A (no data stored or changed; user preferences already persist in the browser)

**Testing**: vitest unit tests (`apps/web/tests/unit`), Playwright end-to-end with axe (`apps/web/tests/e2e`, mock API), synthetic fixtures only

**Target Platform**: Modern desktop and mobile browsers; es-ES only

**Project Type**: Web application (single-page frontend; no backend work)

**Performance Goals**: No regression of the existing bundle budget (`check:bundle`: 350 KB gzip total, 160 KB charts chunk); layout does not shift when data arrives

**Constraints**: es-ES only, EUR and Spanish formats, no hard-coded user text, SKU shown and entered instead of ERP ids, free-text ERP notes never shown, no change to API or contract schemas, shared EUR 120/month budget untouched

**Scale/Scope**: About 10 routes, 7 feature areas, about 1,470 catalogue entries, 3 window sizes × 2 appearances

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle (constitution v1.3.0, AGENTS.md rules) | Status | Note |
|---|---|---|
| I. Least-privilege integrations / Siweb read-only except two writes | Pass | Adds no ERP request of any kind |
| II. Privacy and synthetic data | Pass | Synthetic fixtures only; screenshots taken from synthetic data; ERP notes never shown (only `has_note`) |
| III. Explainable, human-controlled purchasing | Pass | No decision, approval or send behaviour changes |
| IV. Contract-first service boundaries | Pass | No contract change. Shared UI component changes go through Agent 00 (FR-015) |
| V. Testable, observable, cost-bounded delivery | Pass | Hard CI checks added; no new service or cost |
| UI Spanish (es-ES) only, no hard-coded strings (rule 8) | Pass (goal) | This feature is the enforcement |
| SKU is what users see and supply (rule 5) | Pass (goal) | Audited in product journey |
| Money is Decimal, never float (rule 5) | Watch | Interface formatters take numbers; audit confirms amounts arrive as strings and are not recomputed in the browser (see research R6) |

Re-check after Phase 1 design: unchanged, no violations. Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/012-ux-navigation-localization/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── ui-localization-contract.md   # Phase 1
├── checklists/requirements.md
├── tasks.md             # /speckit-tasks (not created here)
└── evidence/            # audit inventory and screenshots, created during implementation
```

### Source Code (repository root)

```text
apps/web/
├── src/
│   ├── app/                 # routes.ts, Navigation, AppShell, CommandPalette, NoAccess, NotFound (reuse; fix gaps)
│   ├── i18n/                # es-ES.json, formatters.ts, index.ts (+ glossary.json, new)
│   ├── ui/                  # shared components and ScreenState (reuse; add help affordance if audit shows missing)
│   └── features/*           # screen-level wording, state and accessibility fixes (FR-015)
└── tests/
    ├── unit/                # i18n-coverage (extend), glossary, nav-role-matrix, screen-states (new)
    └── e2e/                 # journey-product, journey-supplier (new); a11y-all-routes, responsive (extend)
docs/architecture/integration/    # note of cross-feature UI changes for Agent 00
```

**Structure Decision**: Existing single web app; all work stays in `apps/web` plus the feature's spec directory and one note to Agent 00. No new package or service.

## Phases

- **Phase A, audit (first, blocks the rest)**: inventory each navigation entry, journey step, screen state, text source, format and accessibility item as complete, partial, broken, missing or unverified, with file and line evidence, written to `evidence/audit-inventory.md` (FR-001).
- **Phase B, checks first**: tighten the automated checks so the gaps show as failures: untranslated text (including strings outside JSX and export headers), error-code coverage, screen-state coverage, role-by-route navigation matrix, glossary consistency.
- **Phase C, close gaps**: shared components and catalogue first, then screen-level fixes by feature, listing each cross-feature change for Agent 00.
- **Phase D, journeys and evidence**: product and supplier journey end-to-end tests as buyer, role-permission checks for the other roles, accessibility and responsive runs at 1280/768/375 px in both appearances, screenshots, known limitations, pull-request notes.

## Complexity Tracking

No constitution violations; nothing to justify.
