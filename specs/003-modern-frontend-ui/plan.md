# Implementation Plan: MMI 003 — Modern Web Interface

**Branch**: `feat/003-modern-frontend-ui` (cut from `origin/main`) | **Date**: 2026-11-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-modern-frontend-ui/spec.md`; visual direction in [design.md](design.md)

## Summary

Modernise the existing React SPA (`apps/web`) without touching business logic, API contracts or backends, following the client's brand identity manual as applied in [design.md](design.md). The approach is a small in-repo design system built on CSS custom properties (tokens), a handful of accessible primitives (page header, data table, badges, notices, dialog, command palette, empty/loading/error states), URL-based routing with a grouped responsive shell, self-hosted fonts and icons, and a light/dark/system theme. Screens are migrated one at a time onto the shared primitives. No UI component library is added: the current JS bundle is 67 kB gzip against a 350 kB budget, but a library would still add review, licence and upgrade cost for a small team, and every primitive needed is small.

Delivery is incremental and ordered by the spec priorities: foundation → shell and navigation (US1) → tables and states (US2) → responsive polish (US3) → forms and feedback (US4) → dark appearance (US5, may slip).

## Technical Context

**Language/Version**: TypeScript 5.6, React 18.3, Node ≥ 20 (existing)

**Primary Dependencies**: existing `react-router-dom` 6 (installed but unused today), `react-i18next`, `recharts`. New: self-hosted variable fonts via `@fontsource-variable/bricolage-grotesque` (titles) and `@fontsource-variable/inter` (body, tables), the two typefaces fixed by the brand identity manual, both OFL and pinned in the lockfile (see [design.md](design.md)). No component library, no icon package (an in-repo inline-SVG icon set of ~25 icons).

**Storage**: Browser `localStorage` for two preferences (appearance, table density). No server storage, no personal or business data.

**Testing**: Vitest + Testing Library (unit/component), Playwright + `@axe-core/playwright` (end-to-end, accessibility, viewport matrix), existing bundle-size check and i18n/hard-coded-string tests.

**Target Platform**: Modern evergreen desktop browsers; tablet portrait/landscape; ≥ 768 px width fully supported, below that navigation must not break.

**Project Type**: Web application (frontend only change inside the monorepo; `apps/web`).

**Performance Goals**: First meaningful dashboard view ≤ 2 s on an office connection (SC-005); no layout shift on data arrival; JS stays within the existing budgets (total ≤ 350 kB gzip, charts ≤ 160 kB gzip); new CSS and fonts do not block first paint.

**Constraints**: Spanish (es-ES) only, no hard-coded user-facing strings; synthetic data only; no third-party hosts at runtime (SC-006); WCAG 2.2 AA; strict CSP (`script-src 'self'`) so no inline scripts; no backend, contract or infra change except the web container's CSP/nginx config tightening.

**Scale/Scope**: 9 existing screens (~2,700 lines of screen code) plus app shell; a few staff users.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle / constraint | Assessment |
|---|---|
| I. Least-privilege integrations | Pass. No integration or Siweb change. Confirmation dialogs (FR-019) wrap existing actions; separation of duties, fresh MFA and audit stay server-side and unchanged. |
| II. Privacy and synthetic data | Pass, improved. Removing Google Fonts stops leaking every page view to a third party. Preferences hold no personal data. Tests and any committed screenshots use synthetic fixtures only. |
| III. Explainable, human-controlled purchasing | Pass. Presentation only; explanations, approvals and warnings keep their content. Risky actions gain a clearer confirmation, never an automatic one. |
| IV. Contract-first boundaries | Pass. No API/event/schema change. UI-internal contracts (routes, nav registry, status vocabulary, preference keys) are documented in [contracts/ui-contracts.md](contracts/ui-contracts.md). |
| V. Testable, observable, cost-bounded | Pass. Tests added per story; bundle budget kept; no new infrastructure or cost. |
| Additional: Spanish only, EUR/es-ES formats, no hard-coded strings | Pass, with work: the app shell and `Navigation` contain hard-coded Spanish today (baseline file lists 7 occurrences); this feature moves them into `es-ES.json` and lowers the baseline. |
| Additional: public repo | Pass. Only generic code, tokens and synthetic fixtures; logo assets already present. |

No violations; Complexity Tracking is empty. Post-design re-check (after design.md, the brand manual and the consistency analyses): still pass. The ruler uses only data the dashboard already receives, the shell's development sign-in is verified rather than assumed (T084), and no logo, font or data asset from outside the repo's public assets is introduced.

## Project Structure

### Documentation (this feature)

```text
specs/003-modern-frontend-ui/
├── plan.md
├── design.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ui-contracts.md
├── checklists/requirements.md
└── tasks.md              # created by /speckit-tasks
```

### Source Code (repository root)

```text
apps/web/
├── index.html                      # drop Google Fonts links; load theme-init script
├── nginx.conf.template             # CSP: remove fonts.googleapis.com / fonts.gstatic.com
├── public/theme-init.js            # sets data-theme before paint (same-origin, CSP-safe)
├── src/
│   ├── main.tsx                    # data router (RouterProvider), starts the theme sync
│   ├── vite-env.d.ts               # build-time flag types (VITE_ENABLE_DEV_LOGIN)
│   ├── index.css                   # imports tokens + base; legacy classes migrated away per screen
│   ├── styles/
│   │   ├── tokens.css              # colour, type, spacing, radius, elevation, motion; light + dark
│   │   ├── base.css                # reset, typography, focus ring, reduced motion, print
│   │   └── components.css          # primitives' classes
│   ├── app/
│   │   ├── App.tsx                 # session, 401 probe, notice provider, routes
│   │   ├── routes.ts               # route table + navigation registry (see contracts)
│   │   ├── AppShell.tsx            # skip link, rail, drawer, top bar, page header, header-actions slot, outlet
│   │   ├── Navigation.tsx          # grouped navigation (rail and drawer), current-location state
│   │   ├── Drawer.tsx              # navigation drawer below 1024 px (native dialog)
│   │   ├── DevLoginStrip.tsx       # development-only sign-in, hidden in production builds
│   │   ├── devLogin.ts             # build-time gate for the strip
│   │   ├── CommandPalette.tsx      # quick-jump (screens only)
│   │   └── NoAccess.tsx  NotFound.tsx
│   ├── ui/                         # shared primitives (no business logic)
│   │   ├── PageHeader.tsx  PageActions.tsx  Card.tsx  Button.tsx
│   │   ├── StatusBadge.tsx  statusVocabulary.ts   # one vocabulary for every status and tag
│   │   ├── SeverityRuler.tsx       # stockout-severity ruler for the dashboard (design.md §6)
│   │   ├── FilterBar.tsx           # grouped filters with removable chips (design.md §7)
│   │   ├── DataTable.tsx           # sticky header, sort, density, pagination, scroll region
│   │   ├── Skeleton.tsx  EmptyState.tsx  ErrorState.tsx  ScreenState.tsx
│   │   ├── FormField.tsx  useFieldErrors.ts   # label, hint, error wiring; field-level messages
│   │   ├── ConfirmDialog.tsx       # native <dialog>
│   │   ├── NoticeProvider.tsx      # non-blocking toasts, aria-live
│   │   ├── Icon.tsx  icons/        # inline SVG set
│   │   ├── ThemeToggle.tsx  theme.ts  DensityToggle.tsx
│   │   ├── UnsavedChangesPrompt.tsx  useUnsavedChanges.ts
│   │   ├── useChartColors.ts  dialog.ts  usePreferences.ts
│   ├── i18n/es-ES.json             # new keys for shell, states, dialogs, palette
│   └── features/*                  # every screen uses the ui/ primitives; no inline styles
└── tests/
    ├── unit/                       # ui primitives, routes registry, preferences, status vocabulary
    └── e2e/                        # navigation, viewports, themes, states, a11y (both themes)
```

**Structure Decision**: Keep the single `apps/web` project; add `styles/`, `ui/` and route/shell files inside it. Primitives live in `ui/` and never import from `features/`, so screens depend on the design system and not the reverse. No new package or workspace.

## Phasing

| Phase | Scope | Spec coverage | Releasable on its own |
|---|---|---|---|
| F — Foundation | Self-hosted fonts, tokens, base styles, icons, `ui/` primitives, preferences, i18n keys, router wiring (screens unchanged inside) | FR-006, 007, 009, 015, 025 (partly) | Yes (visually near-identical, safer) |
| 1 — Shell and navigation | Routes with Spanish paths, grouped nav, skip link, page headers, command palette, no-access, session-expiry notice | US1; FR-001–005, 020 | Yes |
| 2 — Data presentation | `DataTable`, `StatusBadge` vocabulary, loading/empty/error states on every data screen, stockout-severity ruler, filter bar, chart restyle | US2; FR-008, 010–014 | Per screen |
| 3 — Responsive | Sidebar/drawer breakpoints, scroll regions, touch targets, wide-screen layout | US3; FR-021–023 | Yes |
| 4 — Forms and feedback | `FormField` validation, unsaved-changes guard, notices, `ConfirmDialog` on approval/release/delete/import-activate | US4; FR-016–019 | Per form |
| 5 — Dark appearance | Dark token set, theme toggle, chart/status palettes, axe in dark | US5; FR-024, 026 (dark) | Yes; may slip |

The plan's phases map to the task phases as: F = Phases 1–2, 1 = US1 (Phase 3), 2 = US2 (Phase 4), 3 = US3 (Phase 5), 4 = US4 (Phase 6), 5 = US5 (Phase 7); polish is Phase 8.

A screen is never left half-migrated in a release: it either uses the new primitives completely or the legacy classes completely.

## Complexity Tracking

No constitution violations to justify.
