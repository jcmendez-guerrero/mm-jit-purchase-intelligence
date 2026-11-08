# Tasks: MMI 003 — Modern Web Interface

**Input**: Design documents from `/specs/003-modern-frontend-ui/` (visual direction in `design.md`)

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-contracts.md, quickstart.md

**Tests**: Included and written first within each story (constitution Principle V; spec FR-026, FR-027 and SC-003 to SC-008). Synthetic fixtures only; no screenshots of real data are committed.

**Organization**: Grouped by user story in spec priority order (US1 → US2 → US3 → US4 → US5). Each story phase is one small reviewable PR. US5 (dark appearance) may slip to a later release without blocking US1–US4 (spec clarification).

## Format: `- [ ] [ID] [P?] [Story] Description with file path`

- **[P]**: parallelisable (different files, no dependency on incomplete tasks)
- **[USn]**: user story from spec.md
- Task IDs are stable identifiers, not file order: T078–T084 were added after the design specification and the consistency analysis and sit in the phase where they belong.
- All paths are relative to the repository root. The web app lives in `apps/web/`; below, `web/` stands for `apps/web/`.
- A screen is never left half-migrated in a release: it uses the new primitives completely or the legacy classes completely.
- No backend, API contract, database or infrastructure change; the only configuration change outside `src/` is the web container's CSP (T010).

---

## Phase 1: Setup

**Purpose**: Dependencies and test helpers shared by all stories.

- [X] T001 Add `@fontsource-variable/bricolage-grotesque` and `@fontsource-variable/inter` (pinned; the brand manual's typefaces) to `apps/web/package.json` and update `apps/web/package-lock.json`; confirm OFL licences are acceptable for a public repo
- [X] T002 [P] Create e2e helpers in `apps/web/tests/e2e/ui-helpers.ts`: sign in per role (viewer, buyer, approver, admin) reusing `dashboard-mock.ts`, viewport matrix constants (768×1024, 1024×768, 1280×800, 1920×1080), a recorder that fails on any cross-origin request, and an "assert no horizontal page scroll" helper
- [X] T003 [P] Add a colour-literal guard test in `apps/web/tests/unit/tokens-usage.test.ts` with baseline `apps/web/tests/unit/hardcoded-colors.baseline.json` (hex/rgb literals allowed only in `src/styles/tokens.css` and baselined legacy files; baseline may only shrink, mirroring `hardcoded-strings.baseline.json`)

---

## Phase 2: Foundational (blocking)

**Purpose**: Design tokens, fonts, icons, preferences, base primitives and states used by every story.

**⚠️ CRITICAL**: No user story work starts until this phase is complete.

### Tests first

- [X] T004 [P] Unit tests for the preference store in `apps/web/tests/unit/ui/preferences.test.ts`: defaults, invalid stored values fall back, keys `mmi.ui.appearance` and `mmi.ui.density`, no other storage written (contracts §3)
- [X] T005 [P] Component tests for `Button`, `Card`, `PageHeader`, `Skeleton`, `EmptyState`, `ErrorState`, `ScreenState` in `apps/web/tests/unit/ui/primitives.test.tsx`: one `h1`, roles/labels, `ScreenState` renders exactly one of loading/empty/error/no-access, error has retry, loading sets `aria-busy`, skeleton is `aria-hidden`
- [X] T006 [P] e2e test in `apps/web/tests/e2e/no-third-party.spec.ts` that loads the app root and fails on any cross-origin request (SC-006, FR-009); expected to fail until T009–T010; extended to every route in T031

### Implementation

- [X] T007 [P] Create `apps/web/src/styles/tokens.css`: `--mmi-` tokens for colour (surface, text, border, exactly the brand manual's five colours plus `azul-medio-texto` `#2A778D`, white, hairline and status tint pairs per design.md §4 (Azul medio never for small text, Turquesa never for text or graphics on light surfaces), status tones), type scale, spacing, radius, elevation, motion, layout; light values now, structured so a `[data-theme="dark"]` block can be added in T066; every text/background pair used by primitives ≥ 4.5:1
- [X] T008 [P] Create `apps/web/src/styles/base.css` (reset, typography on the new scale, visible focus ring, `prefers-reduced-motion` handling, print rules hiding navigation and sticky positioning, `rem`-based sizing for 200 % zoom) and `apps/web/src/styles/components.css` (classes for primitives)
- [X] T009 Self-host fonts: remove the Google Fonts `<link>` tags from `apps/web/index.html` and the `@import` from `apps/web/src/index.css`, import the Fontsource variable fonts (Latin and Latin-ext) in `apps/web/src/main.tsx`, set `font-display: swap` and the system-font fallback stack in `tokens.css`; confirm Inter tabular figures (`font-variant-numeric: tabular-nums`) and which Bricolage axes (opsz, wdth) the variable build provides, and record the result in research.md R5; wire `tokens.css`, `base.css`, `components.css` into `apps/web/src/index.css`
- [X] T010 Tighten CSP in `apps/web/nginx.conf.template`: remove `https://fonts.googleapis.com` from `style-src` and `https://fonts.gstatic.com` from `font-src`; keep long-lived caching for hashed assets; confirm deep links still fall back to `index.html`
- [X] T011 [P] Create the inline-SVG icon set (~25 glyphs: navigation items, status, sort, search, close, menu, sun, moon, check, warning, error, info, user, logout, download, filter, chevrons) in `apps/web/src/ui/icons/` and `apps/web/src/ui/Icon.tsx` using `currentColor`; decorative by default, labelled when meaningful
- [X] T012 [P] Implement `apps/web/src/ui/usePreferences.ts` (appearance and density, `localStorage`, validation, change subscription) to satisfy T004
- [X] T013 [P] Implement `Button`, `Card`, `PageHeader` in `apps/web/src/ui/Button.tsx`, `apps/web/src/ui/Card.tsx`, `apps/web/src/ui/PageHeader.tsx` with default/hover/focus/disabled/loading states (FR-007)
- [X] T014 [P] Implement `Skeleton`, `EmptyState`, `ErrorState`, `ScreenState` in `apps/web/src/ui/Skeleton.tsx`, `apps/web/src/ui/EmptyState.tsx`, `apps/web/src/ui/ErrorState.tsx`, `apps/web/src/ui/ScreenState.tsx` (stale-while-revalidate: refetch keeps rows visible, data-model.md)
- [X] T015 Add shell, state, dialog and palette translation keys (and the greeting/subtitle and development-login labels currently hard-coded in `Navigation.tsx` and `App.tsx`) to `apps/web/src/i18n/es-ES.json`; keep `i18n-coverage.test.ts` green
- [X] T016 Run `npm run build && npm run check:bundle` in `apps/web`; confirm fonts are emitted as same-origin assets, `dist/index.html` has no third-party hosts, JS within budget, and T006 now passes

**Checkpoint**: Foundation ready — user stories can begin. Existing screens still render with legacy classes.

---

## Phase 3: User Story 1 - Find and reach any screen quickly (Priority: P1) 🎯 MVP

**Goal**: Grouped, role-aware, responsive-ready navigation with shareable addresses, quick-jump to screens, skip link and no-access handling.

**Independent Test**: With a synthetic session per role, reach every permitted screen using only navigation and the palette; reload, bookmark and use back/forward; unauthorised sections are not offered and show "sin acceso" when opened directly.

### Tests for User Story 1 (write first)

- [X] T017 [P] [US1] Unit tests for the route/navigation registry in `apps/web/tests/unit/routes.test.ts`: unique ids and paths, every label/description key exists in `es-ES.json`, every icon exists, every group non-empty, roles known, `administracion` requires `admin`
- [X] T018 [P] [US1] Component tests for the palette in `apps/web/tests/unit/CommandPalette.test.tsx`: opens on Ctrl/Cmd+K and button, combobox/listbox roles, accent- and case-insensitive match, role filtering, Enter navigates, Esc closes and returns focus, screens only
- [X] T019 [P] [US1] e2e `apps/web/tests/e2e/navigation.spec.ts`: each role reaches every permitted screen in ≤ 2 interactions, `aria-current="page"` on the current item, deep link/reload/back/forward, `?almacen=` reproduces the dashboard warehouse, skip link first in tab order, viewer opening `/administracion` sees no-access, unknown path shows not-found (SC-001, FR-001–004, FR-020)

### Implementation for User Story 1

- [X] T020 [US1] Create the route table and navigation registry in `apps/web/src/app/routes.ts` per contracts §1 and data-model.md (ids/paths `panel, calidad, propuestas, escenarios, costes, proveedores, importaciones, configuracion, administracion`; groups seguimiento, compras, configuracion, administracion)
- [X] T021 [P] [US1] Create `apps/web/src/app/NoAccess.tsx` and `apps/web/src/app/NotFound.tsx` using `ScreenState`/`EmptyState`, each linking to an allowed screen
- [X] T022 [US1] Rewrite `apps/web/src/app/Navigation.tsx` as the grouped left rail (design.md §5) driven by the registry (roles filter, `aria-current`, icons, role-gated administration group); move development-login labels to i18n and replace the emoji user chip with an icon
- [X] T023 [US1] Create `apps/web/src/app/AppShell.tsx`: skip-to-content link, header with logo, navigation (sidebar layout at ≥ 1024 px; narrow behaviour finished in US3), user menu, `<main id>` landmark, router `Outlet`
- [X] T024 [US1] Implement `apps/web/src/app/CommandPalette.tsx` on native `<dialog>` with combobox/listbox semantics, visible trigger button in the header and Ctrl/Cmd+K shortcut (depends on T020, T023)
- [X] T025 [US1] Refactor `apps/web/src/app/App.tsx` to session handling plus `<Routes>`; remove tab `useState`; move the selected warehouse into the `almacen` query parameter and update `apps/web/src/features/dashboard/DashboardScreen.tsx` and `apps/web/tests/unit/DashboardScreen.test.tsx` accordingly; wrap in `BrowserRouter` in `apps/web/src/main.tsx`
- [X] T026 [P] [US1] Add `PageHeader` (title, context line from registry, primary actions slot) and remove the "Hola…" greeting block to i18n keys in `apps/web/src/features/dashboard/DashboardScreen.tsx` and `apps/web/src/features/quality/QualityScreen.tsx` *(Done centrally: `AppShell` renders the page header from the registry, so no per-screen edit was needed.)*
- [X] T027 [P] [US1] Add `PageHeader` in `apps/web/src/features/proposals/ProposalsScreen.tsx`, `apps/web/src/features/scenarios/ScenariosScreen.tsx`, `apps/web/src/features/costs/CostsScreen.tsx` *(Done centrally: `AppShell` renders the page header from the registry, so no per-screen edit was needed.)*
- [X] T028 [P] [US1] Add `PageHeader` in `apps/web/src/features/suppliers/SuppliersScreen.tsx`, `apps/web/src/features/imports/ImportScreen.tsx`, `apps/web/src/features/policies/PoliciesScreen.tsx` *(Done centrally: `AppShell` renders the page header from the registry, so no per-screen edit was needed.)*
- [X] T078 [P] [US1] Apply the brand logo rules in the shell: white logo plate in the rail with free margin ≥ the height of the "M" on every side, original colours, no effects (no recoloured or reversed variant); keep `Favicon.png` (the isotipo in the narrow header is done in T049); add a development-only sign-in strip at the foot of the rail labelled "Entorno de desarrollo" in an amber tone, shown only where development sign-in is enabled today, labels via `es-ES.json` (design.md §2, §5)
- [X] T084 [US1] Verify how the development sign-in (`/auth/dev-login`, `api.devLogin` in `apps/web/src/api/client.ts`) is exposed in `apps/web/src/app/Navigation.tsx` today; ensure the buttons render only in development builds (for example `import.meta.env.DEV`) and are absent from the production build, with a unit test; T078 builds the strip on this result
- [X] T029 [P] [US1] Add `PageHeader` to the single `/administracion` page and stack the status section above the roles section in `apps/web/src/features/admin/AdminStatusScreen.tsx` and `apps/web/src/features/admin/RolesScreen.tsx` *(Done centrally: `AppShell` renders the page header from the registry, so no per-screen edit was needed.)*
- [X] T030 [US1] Handle expired sessions (HTTP 401) in `apps/web/src/api/client.ts` and `apps/web/src/app/AppShell.tsx`: show a Spanish explanation with a route to sign in again instead of a blank screen (FR-020)
- [X] T031 [US1] *(Every-route third-party check lives in `navigation.spec.ts`.)* Update existing e2e specs that navigate by clicking tabs (`apps/web/tests/e2e/*.spec.ts`) to use the new addresses/navigation, keeping their assertions unchanged (FR-027), and extend `no-third-party.spec.ts` (T006) to load every route
- [X] T032 [US1] Lower `apps/web/tests/unit/hardcoded-strings.baseline.json` for `Navigation.tsx` and `App.tsx` to zero; run unit, lint, typecheck and e2e for the story

**Checkpoint**: US1 is releasable alone — new shell, shareable addresses, palette.

---

## Phase 4: User Story 2 - Read and act on data with less effort (Priority: P1)

**Goal**: Consistent tables, status vocabulary and loading/empty/error states on every data screen; charts adopt the visual system.

**Independent Test**: On dashboard and proposals with synthetic data, sort and scan tables, trigger loading, empty and error conditions, and confirm designed states and identical status presentation everywhere.

> **Implementation note (US2)**: the shared look reaches every screen through the restyled table, badge, button and form classes in `index.css` and `styles/components.css`. `DataTable` (sort, density, pagination, sticky first column) is used where lists can be long: the dashboard risk table, the drill-down and the quality list. Tables with inline expansion or editing (proposal lines, costs, imports, roles, policies) keep their markup inside the new scroll-region wrapper. Every data screen uses `ScreenState`/`EmptyState` and a retry for load failures. The policies and administration screens have skeletons and states but no dedicated end-to-end states test.

### Tests for User Story 2 (write first)

- [X] T033 [P] [US2] Unit tests for the status vocabulary in `apps/web/tests/unit/ui/status-vocabulary.test.ts`: every code of every domain has label key, tone and icon; unknown codes render neutral; token pairs ≥ 4.5:1
- [X] T034 [P] [US2] Component tests for `DataTable` in `apps/web/tests/unit/ui/DataTable.test.tsx`: sticky header class, `aria-sort` toggling and announcement, sort kept while mounted, density from preference, pagination labels and row count, scroll region focusable and labelled, empty state, a 5,000-row dataset renders the first page without noticeable delay (FR-012)
- [X] T035 [P] [US2] e2e `apps/web/tests/e2e/states.spec.ts`: for each data screen, delayed response shows skeleton without layout shift, empty response shows the empty state, failed response shows error with retry and the rest of the screen stays usable, and very long product/supplier names truncate or wrap without breaking layout (SC-008, FR-013)

### Implementation for User Story 2

- [X] T079 [P] [US2] Component test for the stockout-severity ruler in `apps/web/tests/unit/ui/SeverityRuler.test.tsx`: proportional segment widths from per-severity counts, zero-count segments omitted, segments are buttons named with count and label with `aria-pressed`, activating a segment filters and activating it again clears, icon present, empty state when no stockout risk, no animation under reduced motion
- [X] T080 [US2] Implement `apps/web/src/ui/SeverityRuler.tsx` per design.md §6 and use it in `apps/web/src/features/dashboard/DashboardScreen.tsx`: group existing `risks` (stockout items) by `explanation_key` severity, filter the risk table client-side, keep the other four figures with their drill-downs as a quieter figures row. Verified fact: `/dashboard/risk` is uncapped but filtered by warehouse only, while `summary.stockout_risk` also respects category and family; so show the severity split only when the list's stockout total equals `summary.stockout_risk`, otherwise show the summary count alone; one-time 600 ms growth on first load only (depends on T036, T038; same file as T038 and T081, not parallel)
- [X] T036 [P] [US2] Implement the status vocabulary in `apps/web/src/ui/statusVocabulary.ts` and `apps/web/src/ui/StatusBadge.tsx` (risk, cost freshness, quarantine, approval, import; text plus icon, never colour only), add label keys to `apps/web/src/i18n/es-ES.json`
- [X] T037 [P] [US2] Implement `apps/web/src/ui/DataTable.tsx` (sticky header, sortable columns, scroll region with sticky identifying column, pagination default 50, server-paged mode that reuses only the shell) and `apps/web/src/ui/DensityToggle.tsx`
- [X] T038 [US2] Migrate the dashboard to the new primitives in `apps/web/src/features/dashboard/DashboardScreen.tsx`, `SupplierPanel.tsx`, `DrillDownPanel.tsx`, `ProductDetail.tsx`: `ScreenState`, `DataTable`, `StatusBadge`, cards; keep `dashboardModel.ts` logic untouched; update `apps/web/tests/unit/DashboardScreen.test.tsx`
- [X] T039 [P] [US2] Restyle `apps/web/src/features/dashboard/ChartWithTable.tsx` to tokens (colours from CSS variables), keeping keyboard operation, table alternative and text summary (FR-014)
- [X] T040 [P] [US2] Migrate `apps/web/src/features/quality/QualityScreen.tsx` (quarantine list) to `ScreenState`, `DataTable`, `StatusBadge`; move its remaining hard-coded string to `es-ES.json` and lower `hardcoded-strings.baseline.json` accordingly
- [X] T041 [P] [US2] Migrate `apps/web/src/features/proposals/ProposalsScreen.tsx`, `ProposalLineExplanation.tsx`, `VersionsUsed.tsx` to `ScreenState`, `DataTable`, `StatusBadge`; update `apps/web/tests/unit/ProposalsScreen.test.tsx`
- [X] T042 [P] [US2] Migrate `apps/web/src/features/costs/CostsScreen.tsx` to `ScreenState`, `DataTable`, `StatusBadge` (stale/jump indicators); update `apps/web/tests/unit/CostsScreen.test.tsx`
- [X] T043 [P] [US2] Migrate `apps/web/src/features/scenarios/ScenariosScreen.tsx` results/changes tables and states
- [X] T044 [P] [US2] Migrate `apps/web/src/features/suppliers/SuppliersScreen.tsx` list and `apps/web/src/features/imports/ImportScreen.tsx` datasets/validation tables and states
- [X] T045 [P] [US2] Migrate `apps/web/src/features/policies/PoliciesScreen.tsx` and section components (`DemandSection.tsx`, `ForecastSection.tsx`, `SafetyStockSection.tsx`, `PurchasingSection.tsx`, `CategoryHistory.tsx`) and `apps/web/src/features/admin/AdminStatusScreen.tsx`, `RolesScreen.tsx` tables and states
- [X] T081 [US2] Replace native-looking filter controls on the dashboard with a new `apps/web/src/ui/FilterBar.tsx` primitive (grouped bar, removable chips, "Quitar filtros"; design.md §7) used in `apps/web/src/features/dashboard/DashboardScreen.tsx`, keeping filter semantics unchanged; US4's `FormField` later reuses its styles (depends on T080, same file, not parallel)
- [X] T082 [US2] Add `apps/web/tests/e2e/a11y-all-routes.spec.ts`: axe with tags `wcag2a`, `wcag2aa`, `wcag21aa`, `wcag22aa` on every route in the light appearance with synthetic mocks (no serious or critical violations), plus a keyboard-only run of the three reference tasks (find a product at risk, review and submit the weekly proposal, edit one supplier term); update the tags in `apps/web/tests/e2e/a11y.spec.ts` and `a11y-screens.spec.ts` (SC-003, FR-026 for light; T070 adds the dark run)
- [X] T083 [US2] Measure the dashboard first meaningful view and layout shift in `apps/web/tests/e2e/dashboard-perf.spec.ts` (currently asserts under 3000 ms): record the current baseline, then assert ≤ 2000 ms on the reference throttled profile and no layout shift on data arrival; if 2 s cannot be met without backend changes, record the measurement and amend SC-005 through a spec change, not silently (SC-005)
- [X] T046 [US2] Remove replaced legacy per-screen status colours/classes from `apps/web/src/index.css`, update `hardcoded-colors.baseline.json` (T003), run unit and e2e including `apps/web/tests/e2e/dashboard-perf.spec.ts` (SC-005)

**Checkpoint**: US1 + US2 are the core release; tables, statuses and states consistent on all screens.

---

## Phase 5: User Story 3 - Tablet, narrow windows and large screens (Priority: P2)

**Goal**: Every screen usable from 768 px up with no horizontal page scroll; compact navigation on narrow viewports; good use of wide screens; touch-friendly targets.

**Independent Test**: Open every screen at the four reference viewports and at 200 % zoom; no horizontal page scroll, no clipped controls, primary actions reachable.

> **Implementation note (US3)**: the layout audits (T050, T051) found no horizontal page overflow on any of the nine screens at 768, 1024, 1280 and 1920 px (and at 200 % zoom), so the only fixes needed were the drawer shell and the touch-size rules. Print is checked with print-media emulation (no manual preview was done).

### Tests for User Story 3 (write first)

- [X] T047 [P] [US3] e2e `apps/web/tests/e2e/responsive.spec.ts`: for every route at each viewport in `ui-helpers.ts`, assert no horizontal page scroll, wide tables scroll inside their region with the first column visible, drawer opens/closes with the same destinations and closes after choosing, 200 % zoom and an enlarged base text size have no clipped content, and with `prefers-reduced-motion` emulated no transition or ruler growth runs (SC-004, FR-021, FR-022, FR-025)
- [X] T048 [P] [US3] e2e touch check in `apps/web/tests/e2e/touch-targets.spec.ts`: with a coarse-pointer emulation, interactive elements on the shell and one table/form meet the target-size rule (FR-023)

### Implementation for User Story 3

- [X] T049 [US3] Use the existing `apps/web/public/isotipo.png` in the narrow-viewport header (brand rule: isotipo when the full logo is too small) and finish responsive shell in `apps/web/src/app/AppShell.tsx`, `Navigation.tsx` and `apps/web/src/styles/components.css`: sidebar ≥ 1024 px, header button and drawer (focus trap via `<dialog>`, `Esc`) below, content max-width and multi-column cards on wide screens
- [X] T050 [P] [US3] Audit and fix layouts at 768 px for dashboard, quality, proposals in their screen files and `apps/web/src/styles/components.css` (stacked cards, filters wrap, scroll regions)
- [X] T051 [P] [US3] Audit and fix layouts at 768 px for scenarios, costs, suppliers (including `SupplierTermsEditor.tsx`, `OverrideEditor.tsx`), imports, policies sections, admin
- [X] T052 [P] [US3] Add coarse-pointer target sizes (≥ 44 px) and minimum 24 px elsewhere, and reduced-motion/print checks (navigation hidden, no sticky) in `apps/web/src/styles/base.css`; verify print preview of a proposal manually (quickstart §4)

**Checkpoint**: US1–US3 complete the layout work.

---

## Phase 6: User Story 4 - Consistent forms, actions and feedback (Priority: P2)

**Goal**: Uniform forms with field-level validation, unsaved-change protection, non-blocking notices and explicit confirmation for hard-to-reverse actions, with every server-side safeguard unchanged.

**Independent Test**: Edit and save a supplier term, submit a proposal for approval and attempt an action needing fresh authentication (synthetic data): validation beside fields, focus on first error, unsaved-change prompt, notices, and a confirmation naming object and effect.

> **Implementation note (US4)**: `FormField` replaced the old supplier `Field` in every form of the app (supplier terms and exceptions, policies, costs, imports, scenarios). Field-level messages cover format only (numbers, whole numbers, HH:MM); business rules stay on the server. The unsaved-changes prompt guards supplier terms, supplier exceptions, the purchasing policy form and the scenario parameters; it needs the data router, so `main.tsx` now uses `createBrowserRouter` (a router supports one blocker, so a form registers it only while it has edits to lose). Confirmations wrap proposal submit and approve, cost release, import activation and rollback, scenario promotion and role changes; there is no delete action in the app today. Notices come from `useActionNotice`, which falls back to inline text where no provider is mounted. Existing unit and end-to-end specs gained a confirmation click; their assertions are unchanged.

### Tests for User Story 4 (write first)

- [X] T053 [P] [US4] Component tests in `apps/web/tests/unit/ui/forms.test.tsx`: `FormField` label/hint/error wiring and `aria-invalid`, first-invalid focus on submit helper, `useUnsavedChanges` blocks in-app navigation and registers `beforeunload`
- [X] T054 [P] [US4] Component tests in `apps/web/tests/unit/ui/ConfirmDialog.test.tsx` and `NoticeProvider.test.tsx`: focus in/return, `Esc` cancels, danger tone focuses cancel, object/effect rendered; notices polite live region, ≥ 6 s, pause on hover/focus, `Esc` dismiss, no focus steal
- [X] T055 [P] [US4] e2e `apps/web/tests/e2e/forms-feedback.spec.ts`: supplier term invalid value, unsaved-change prompt, save notice; approval, cost release, import activation and delete each show a confirmation whose confirm sends the identical request as before (assert request body unchanged) and cancel sends none (FR-016–019, FR-027)

### Implementation for User Story 4

- [X] T056 [P] [US4] Implement `apps/web/src/ui/FormField.tsx` and `apps/web/src/ui/useUnsavedChanges.ts`
- [X] T057 [P] [US4] Implement `apps/web/src/ui/ConfirmDialog.tsx` (native `<dialog>`, translated templates for object and effect) and `apps/web/src/ui/NoticeProvider.tsx`; mount the provider in `apps/web/src/app/AppShell.tsx`; add keys to `es-ES.json`
- [X] T058 [P] [US4] Migrate supplier forms to `FormField` and unsaved guard: `apps/web/src/features/suppliers/Field.tsx` (replace with the shared field), `SupplierTermsEditor.tsx`, `OverrideEditor.tsx`; update `apps/web/tests/unit/SuppliersScreen.test.tsx`
- [X] T059 [P] [US4] Migrate policy forms in `apps/web/src/features/policies/` (all section components) and scenario parameters in `apps/web/src/features/scenarios/ScenariosScreen.tsx` to `FormField`, unsaved guard and notices; update `apps/web/tests/unit/PoliciesScreen.test.tsx`
- [X] T060 [US4] Add `ConfirmDialog` to proposal submit/approve in `apps/web/src/features/proposals/ProposalsScreen.tsx` and cost release in `apps/web/src/features/costs/CostsScreen.tsx`; do not change request construction, separation-of-duties or fresh-authentication handling
- [X] T061 [P] [US4] Add `ConfirmDialog` and notices to import activation/removal in `apps/web/src/features/imports/ImportScreen.tsx`, role changes in `apps/web/src/features/admin/RolesScreen.tsx` and scenario deletion; update `ImportScreen.test.tsx`, `RolesScreen.test.tsx`
- [X] T062 [US4] Replace remaining ad-hoc success/error text for completed actions with notices and inline errors across screens; run unit and e2e for the story

**Checkpoint**: US1–US4 complete; all interactions consistent.

---

## Phase 7: User Story 5 - Light, dark and system appearance (Priority: P3)

**Goal**: Dark appearance and an appearance control; default follows the device; choice persists. May slip to a later release without blocking US1–US4 (then the interface ships light-only and FR-026 applies to light alone).

**Independent Test**: Switch device preference and the in-app setting; every screen, chart and status badge stays legible and passes axe in both appearances; the choice survives reload.

> **Implementation note (US5)**: the dark appearance re-maps the colour roles only; the brand colours and the white logo plate never change. Contrast of both themes is computed from `tokens.css` by a unit test, which also caught a light-theme defect: control borders were 2.6:1 and are now `#6B8288` (≥ 3:1). `public/theme-init.js` sets `data-theme` before first paint; `startThemeSync` keeps it current, including live changes of the device preference. Charts read their colours from tokens. Axe runs in both appearances on all nine routes and on the data-heavy screens.

### Tests for User Story 5 (write first)

- [X] T063 [P] [US5] Unit contrast test in `apps/web/tests/unit/ui/theme-contrast.test.ts`: parse `tokens.css`, assert every declared text/background and status-tone pair ≥ 4.5:1 (text) and ≥ 3:1 (meaningful graphics) in light and dark
- [X] T064 [P] [US5] Component test for `ThemeToggle` in `apps/web/tests/unit/ui/ThemeToggle.test.tsx`: three options, labelled, persists, applies `data-theme`, "system" follows `prefers-color-scheme`
- [X] T065 [P] [US5] e2e `apps/web/tests/e2e/appearance.spec.ts`: default follows emulated colour scheme, override persists across reload, no flash of the wrong theme at first paint, reduced-motion respected; the axe runs in both appearances are in T070 (FR-024, FR-025)

### Implementation for User Story 5

- [X] T066 [US5] Add the `[data-theme="dark"]` token set (surfaces, text, borders, brand, status tones, chart series) to `apps/web/src/styles/tokens.css`
- [X] T067 [P] [US5] Create `apps/web/public/theme-init.js` (reads `mmi.ui.appearance`, applies `data-theme` before paint; same-origin, no inline script) and reference it from `apps/web/index.html`; confirm the CSP in `nginx.conf.template` allows it without `unsafe-inline` for scripts
- [X] T068 [P] [US5] Implement `apps/web/src/ui/ThemeToggle.tsx` and place it in the header of `apps/web/src/app/AppShell.tsx`; add labels to `es-ES.json`
- [X] T069 [US5] Make chart colours (`ChartWithTable.tsx` and any Recharts usage) read from CSS variables so charts follow the theme; fix any remaining literal colours reported by T003's guard
- [X] T070 [US5] Extend `apps/web/tests/e2e/a11y-all-routes.spec.ts` (T082), `a11y.spec.ts` and `a11y-screens.spec.ts` to also run in the dark appearance with the same WCAG 2.2 tags; fix findings (SC-003, FR-026)

**Checkpoint**: All five stories complete.

---

## Phase 8: Polish & cross-cutting

- [X] T071 [P] Remove unused legacy classes and dead styles from `apps/web/src/index.css`; empty `hardcoded-colors.baseline.json` for migrated files and confirm `hardcoded-strings.baseline.json` only shrank *Done: the two unused legacy badge classes were removed; the colour and string baselines are empty. The rest of the compatibility layer is still used by screens with inline editing and is kept.*
- [X] T072 [P] Update the PR checklist notes in `.github/pull_request_template.md` only if needed, and add a short "Interface conventions" section (tokens, primitives, routes, preferences) to `apps/web/README.md` (create if absent) with no real data *Done as `apps/web/README.md` (interface conventions); the PR template itself did not need changes.*
- [X] T073 Run `npm run typecheck && npm run lint && npm test && npm run build && npm run check:bundle && npm run e2e` in `apps/web`; confirm bundle budgets unchanged or document and justify any change in plan.md (FR-029); confirm every screen listed in contracts §1 uses the shared primitives (SC-007) and that no screenshot or recording is committed (FR-028) *Done: typecheck, lint, 380 unit tests, build and bundle budget (248 of 350 kB), 156 end-to-end tests with 4 skipped (the screenshot-evidence spec, which needs CAPTURE_EVIDENCE=1).*
- [X] T074 Build the web image from `apps/web/Dockerfile` and verify quickstart §6 (deep link `/costes` returns the SPA, CSP has no third-party font hosts, fonts served from the same origin) *Done with the real image on a spare port: `/costes` returns the app shell, the CSP lists no third-party host, `theme-init.js` is served, 4 font files ship, nothing references Google hosts; the temporary container and image were removed.*
- [ ] T075 Walk quickstart §4 manually with synthetic data across all four development roles; record deviations as follow-up tasks *Open: needs a person. The automated suites cover steps 2 to 8 on mocked data (navigation, palette, sorting and density, validation and unsaved-change prompt, confirmations, appearance, reduced motion, print media); a human pass with the four development roles and a real print preview is still to be done.*
- [ ] T076 Run the team clarity check (quickstart §5, SC-002) and record the result in the pull request without screenshots of real data *Open: needs the purchasing team (quickstart §5, SC-002). Not something the code can show.*
- [X] T077 Mark completed tasks `[X]` in this file and note in the PR template the data, security (CSP tightened), cost (none) and contract (none) impact *Done: completed tasks are marked and the PR text, with data, security, cost and contract impact, is drafted in `pull-request.md`.*

---

## Dependencies & Execution Order

- **Phase 1 → Phase 2** (T001 before T009; T002–T003 independent). **Phase 2 blocks all stories.** Within Phase 2: tests T004–T006 first; T007/T008/T011/T012/T013/T014 in parallel; T009 needs T001, T007, T008; T010 can follow T009; T015 anytime; T016 last.
- **US1** needs Phase 2. T020 → T022/T023 → T024; T025 needs T020, T023. T026–T029 are parallel but need T013 (PageHeader) and T020. T031 needs T025.
- **US2** needs Phase 2 and the US1 shell (routes) only for e2e; component work (T036, T037) can start right after Phase 2. Screen migrations T038–T045 are independent of each other and need T036, T037, T014.
- **US3** needs US1 (shell) and benefits from US2 tables (scroll region); T050–T051 follow the screen migrations they audit.
- **US4** needs Phase 2 and US1 shell (notice provider mount); form migrations T058–T061 touch the same files as US2 migrations, so run them after the matching US2 task to avoid conflicts.
- **US5** needs Phase 2 tokens; T069 follows US2 chart restyle (T039). Can be deferred entirely.
- **T078–T084**: T084 (dev sign-in check) precedes T078; T082 and T083 follow the US2 screen migrations; T080 follows T036 and T038.
- **Polish** after all desired stories.

### Same-file caution

`DashboardScreen.tsx` (T025, T026, T038, T080, T081; order T038 → T080 → T081), `ProposalsScreen.tsx` (T027, T041, T060), `CostsScreen.tsx` (T027, T042, T060), `SuppliersScreen.tsx` and supplier editors (T028, T044, T058), `ImportScreen.tsx` (T028, T044, T061), `RolesScreen.tsx` (T029, T045, T061), `AppShell.tsx` and `Navigation.tsx` (T022, T023, T030, T049, T057, T068, T078, T084) are edited by several tasks: do not run those in parallel.

## Parallel Examples

- **Phase 2**: T004, T005, T006, then T007, T008, T011, T012, T013, T014 together.
- **US1**: T017, T018, T019 together; later T026, T027, T028, T029 together.
- **US2**: T033, T034, T035, T079 together; T036 and T037 together; then T040–T045 together; T080 → T081 sequential after T038; T082 and T083 after the screens are migrated.
- **US4**: T053, T054, T055 together; T056 and T057 together.

## Implementation Strategy

1. **MVP = Phases 1–3 (US1)**: fonts self-hosted, tokens, shell, routes, palette. Ship and gather feedback.
2. **Core release = + US2**: tables, statuses and states on all screens (both P1 stories).
3. **Then US3 → US4** in order, each as its own PR.
4. **US5 last**; if time is short, skip it and ship light-only (spec clarification), keeping the token structure ready.
5. After each story run the quickstart checks for that story; keep every screen fully on one styling system per release.

---

## Phase 9: Convergence

**Purpose**: Remaining work found by comparing the code with the spec, plan, design and constitution after the first implementation pass. Each task traces to its source; completing them is the job of `/speckit-implement`. T075 and T076 (people) stay open above.

- [X] T085 Add `ConfirmDialog` confirmations for the remaining hard-to-reverse actions: the admin cost-value override in `apps/web/src/features/costs/CostsScreen.tsx`, "ignore" and "release" of a quarantined movement in `apps/web/src/features/quality/QualityScreen.tsx` (name the movement and say it is recorded and cannot be undone from this screen), and rejecting an uploaded dataset in `apps/web/src/features/imports/ImportScreen.tsx`; add keys to `apps/web/src/i18n/es-ES.json` and end-to-end checks in `apps/web/tests/e2e/forms-feedback.spec.ts` that confirm sends the same request as before and cancel sends none per FR-019 and Constitution III (partial) *Done: confirmations for the cost-value override, quality release and ignore, and rejecting an upload; unit and end-to-end checks that confirm sends the same request and cancel sends none.*
- [X] T086 Move screens onto the shared primitives: replace the legacy `.mmi-btn`, `.mmi-btn-primary`, `.mmi-btn-secondary`, `.mmi-btn-sm` buttons with `Button` and raw `.mmi-card` wrappers with `Card` across `apps/web/src/features/**`, then delete the matching compatibility rules from `apps/web/src/index.css`; keep behaviour and test assertions unchanged per FR-007, SC-007 and plan: no half-migrated screens (partial) *Done: every screen uses `Button` and `Card`; the legacy button and card classes are deleted and a unit guard keeps them out.*
- [X] T087 Replace the remaining inline `style={{ … }}` props (about 70, mostly in `apps/web/src/features/suppliers/SupplierTermsEditor.tsx`, `OverrideEditor.tsx`, `apps/web/src/features/scenarios/ScenariosScreen.tsx`, `apps/web/src/features/admin/RolesScreen.tsx`, `apps/web/src/features/policies/PurchasingSection.tsx`) with token-based classes in `apps/web/src/styles/components.css`, and add a unit guard in `apps/web/tests/unit/tokens-usage.test.ts` that fails on new inline style props in `src/features` per FR-006 (partial) *Done: about 60 inline styles became token-based classes; a unit guard allows only the ruler's data-driven width.*
- [X] T088 Render every remaining label-like tag through the status vocabulary: add domains or codes for supplier flags (preferred, disabled), terms source, forecast-basis estimate and similar to `apps/web/src/ui/statusVocabulary.ts` with label keys, use `StatusBadge` in `apps/web/src/features/suppliers/SuppliersScreen.tsx`, `SupplierTermsEditor.tsx`, `OverrideEditor.tsx`, `apps/web/src/features/policies/SafetyStockSection.tsx`, `apps/web/src/features/dashboard/ProductDetail.tsx`, `apps/web/src/features/proposals/ProposalsScreen.tsx`, remove the legacy `.mmi-badge*` classes, and extend `apps/web/tests/unit/ui/status-vocabulary.test.ts` per FR-008 (partial) *Done with a new `tag` domain in the status vocabulary; the legacy badge classes are deleted.*
- [X] T089 Use `DataTable` (sortable columns, density, pagination, sticky first column) for the remaining list tables where ordering is meaningful: suppliers list, registered costs, scenarios list, import datasets and jobs, roles, proposal supplier groups, administration tables; keep tables with inline expansion or editing in the scroll-region wrapper and make that wrapper keep its first column visible; verify with `apps/web/tests/e2e/responsive.spec.ts` per FR-010, FR-011, FR-012 (partial) *Done for 11 list tables (suppliers, costs, scenarios, import datasets and jobs, roles, proposal groups, three admin tables); tables with inline expansion or editing keep the scroll-region wrapper, which now keeps its first column visible.*
- [X] T090 Add field-level validation messages (format only, beside the field, focus on the first invalid field on save) to the remaining forms: scenario parameters in `apps/web/src/features/scenarios/ScenariosScreen.tsx`, policy forms in `apps/web/src/features/policies/`, cost opening in `apps/web/src/features/costs/CostsScreen.tsx`, import mapping in `apps/web/src/features/imports/ImportScreen.tsx`; put the pure checks in each feature's model file with unit tests per FR-016 (partial) *Done with `useFieldErrors` for scenarios, policies (purchasing, safety stock, demand, forecast) and cost opening; the import mapping keeps its summary message, now linked to the disabled validate button.*
- [X] T091 Add `UnsavedChangesPrompt` to the forms that lack it: `apps/web/src/features/policies/SafetyStockSection.tsx`, `DemandSection.tsx`, `ForecastSection.tsx`, the cost opening and override fields in `apps/web/src/features/costs/CostsScreen.tsx`, and the import wizard in `apps/web/src/features/imports/ImportScreen.tsx` (only while edits exist); extend `apps/web/tests/e2e/forms-feedback.spec.ts` per FR-017 (partial) *Done for safety stock, demand, forecast, cost opening and override; the import wizard is guarded while an upload is pending (not covered by an end-to-end test).*
- [X] T092 Put each screen's primary action in the `PageHeader` actions slot so it sits in the same place on every screen: add a header-actions portal in `apps/web/src/app/AppShell.tsx` and use it for proposal submit, approve and exports, scenario create, supplier save where applicable, and import upload, without changing handlers or test assertions per FR-005 and ui-contracts §5 (partial) *Done through a header-actions slot (`PageActions`) used by proposals, scenarios, suppliers and imports; outside the shell the actions render in place.*
- [X] T093 Add end-to-end states coverage (skeleton, empty, error with retry) for the policies and administration screens in `apps/web/tests/e2e/states.spec.ts` with synthetic mocks per SC-008 and FR-013 (partial) *Done for policies and administration (loading and error with retry); they have no empty state to show.*
- [X] T094 Apply the screen layouts of design.md §8 to proposals and scenarios: proposal lines grouped per supplier with the supplier subtotal at the foot of each group in `apps/web/src/features/proposals/ProposalsScreen.tsx`, and a two-column scenario form and comparison (stacked below 1024 px) in `apps/web/src/features/scenarios/ScenariosScreen.tsx`; keep every existing assertion and add a responsive check per design §8 (partial) *Done: proposal lines grouped per supplier with the server's subtotal (one table, a body per supplier, so the table name is unchanged) and a two-column scenarios layout.*
- [X] T095 Apply the screen layouts of design.md §8 to suppliers, configuration and imports: master list beside the term editor in `apps/web/src/features/suppliers/SuppliersScreen.tsx`, in-page section navigation in `apps/web/src/features/policies/PoliciesScreen.tsx`, and numbered import steps (a real sequence) in `apps/web/src/features/imports/ImportScreen.tsx`; keep every existing assertion per design §8 (partial) *Done: suppliers list beside the editor, configuration sections as a column of tabs, import steps were already numbered 1 to 6.*
- [X] T096 Make loading placeholders match the final layout: add table-shaped and bar-shaped variants to `apps/web/src/ui/Skeleton.tsx` and use them in the dashboard, quality, proposals, costs and suppliers screens; assert no layout jump in `apps/web/tests/e2e/dashboard-perf.spec.ts` per FR-013 (partial) *Done: table-shaped and dashboard-shaped skeletons; layout shift 0.006 when data arrives after a delay.*
- [X] T097 Verify the remaining edge cases in `apps/web/tests/e2e/responsive.spec.ts`: print media on `/propuestas` (navigation hidden, table not clipped) and a page load with font requests blocked still shows legible text and a stable layout per spec edge cases (partial) *Done: print on the proposals screen and a page load with the font files blocked.*
- [X] T098 Use the shared date formatter instead of `toLocaleString("es-ES")` in `apps/web/src/features/quality/QualityScreen.tsx` (`formatDateTime` in `apps/web/src/i18n/formatters.ts`) and add a unit test per FR-015 (partial) *Done with the shared date formatter and a unit test.*

---

## Phase 10: Convergence

**Purpose**: Remaining work found by a second comparison of the code with the spec, plan and design after Phase 9. T075 and T076 (people) stay open above.

- [X] T099 Render long proposal lines incrementally or in pages: paginate (about 50 lines per page, keeping a supplier's header and subtotal rows with its lines) in `apps/web/src/features/proposals/ProposalsScreen.tsx`, with labelled page controls and a unit test for the paging of grouped lines in `apps/web/tests/unit/proposal-model.test.ts` and a 500-line end-to-end check per FR-012 (partial) *Done: 50 lines per page with the supplier header (marked as continued) and the server's subtotal on the page where the supplier ends; a 500-line proposal is checked end to end.*
- [X] T100 Move the long, orderable legacy tables to `DataTable` (sorting, density, pagination, sticky first column): product demand series and forecast table in `apps/web/src/features/dashboard/ProductDetail.tsx`, policy history in `apps/web/src/features/policies/PurchasingSection.tsx`, supplier term history in `apps/web/src/features/suppliers/SupplierTermsEditor.tsx`, and forecast accuracy in `apps/web/src/features/dashboard/DashboardScreen.tsx`; keep every existing accessible table name and assertion per FR-010, FR-011 (partial) *Done for the product demand and forecast tables, policy history, supplier term history and forecast accuracy. The sort buttons now take their name from the column header and carry the hint in `title`, so label lookups on a column name still find the input.*
- [X] T101 Show a clear Spanish no-access explanation with a way forward when the server refuses an action or a screen with HTTP 403 mid-session: map 403 in `apps/web/src/api/client.ts` to a typed error, render it through `ScreenState` `no_access` (with the link to the dashboard) in the screens' load paths and as an inline message for actions, add keys to `apps/web/src/i18n/es-ES.json`, and test with `apps/web/tests/unit/api-errors.test.ts` and `apps/web/tests/e2e/navigation.spec.ts` per FR-020 (partial) *Done: any 403 gets the no-permission sentence; screens that show a load error through `ScreenState` explain the refusal with a link to the dashboard instead of a retry (costs, scenarios and imports now use it too).*
- [X] T102 Add an end-to-end check that leaving the import wizard with a pending upload asks first (keep editing stays, discard leaves) in `apps/web/tests/e2e/forms-feedback.spec.ts` per FR-017 (partial) *Done: end-to-end check for the import wizard.*
- [X] T103 Put the remaining screens' primary actions in the page header with `PageActions`: save buttons in `apps/web/src/features/policies/` sections, the opening-cost save in `apps/web/src/features/costs/CostsScreen.tsx`, and the roles retry in `apps/web/src/features/admin/RolesScreen.tsx` where a screen has one clear primary action; extend the header check in `apps/web/tests/e2e/forms-feedback.spec.ts` per FR-005 (partial) *Done for the purchasing policy (preview and save) and the opening cost; the roles retry stays in place because it only appears when something failed.*
- [X] T104 Mark each unmapped required column in the import mapping step with `aria-invalid`, a message beside its select, and a link from the disabled validate button, in `apps/web/src/features/imports/ImportScreen.tsx` and `apps/web/src/features/imports/importsModel.ts`, with a unit test per FR-016 (partial) *Done as a per-field list (one line for each required field without a column, a "required" tag on mapped columns, the disabled validate button linked to the message); a required field has no column of its own to mark, so the markers sit on the list.*

---

## Phase 11: Convergence

**Purpose**: Documentation that still describes the first design. T075 and T076 (people) stay open above.

- [X] T105 Bring the design documents in line with what was built: add the new files (`apps/web/src/app/Drawer.tsx`, `DevLoginStrip.tsx`, `apps/web/src/ui/PageActions.tsx`, `useFieldErrors.ts`, `theme.ts`, `UnsavedChangesPrompt.tsx`) to the structure in `specs/003-modern-frontend-ui/plan.md`; add the `tag` status domain and the no-access screen state to `specs/003-modern-frontend-ui/data-model.md`; add the header-actions slot, the 403 no-access behaviour, the drawer, the theme sync and the sort-button hint (`title`, not part of the accessible name) to `specs/003-modern-frontend-ui/contracts/ui-contracts.md`; and correct design.md §8 to say proposal lines are one table with a body per supplier (so the table name is stable) per plan: project structure, ui-contracts §5 (partial) *Done: plan structure, data-model (tag domain, no-access state), ui-contracts (drawer, confirmations, header slot, sort hint, 403, theme sync, field errors) and design §8 (proposal grouping and paging, confirmation wording) now describe the code.*
- [X] T106 Update `apps/web/README.md` (add `PageActions`, `useFieldErrors`, the drawer, and the rule that hard-to-reverse actions use `ConfirmDialog`) and extend the manual walk in `specs/003-modern-frontend-ui/quickstart.md` §4 with steps for proposal line paging, the 403 explanation, every confirmation (approve, release, override, ignore, reject, activate, roll back, promote, role change), and the header actions per T072 and quickstart §4 (partial) *Done: README conventions and quickstart §4 steps 9 to 14 (the manual walk of T075 now covers them).*

## Phase 12: Sign-in page

**Purpose**: People without a session could not sign in (the role buttons were hidden in production builds and the BFF had no Entra flow).

- [X] T107 Add `GET /api/auth/config`, `GET /api/auth/login` and `GET /api/auth/callback` (Entra ID code flow with PKCE, id_token validation, roles and MFA time) in `services/api-bff/src/auth/entra.py` and `routes/api.py`, with tests in `services/api-bff/tests/test_entra_login.py`
- [X] T108 Replace the build-flag dev strip with a `LoginScreen` shown whenever there is no session: role chooser when the server says `dev`, "Iniciar sesión con Microsoft" when `entra` (`apps/web/src/app/LoginScreen.tsx`, `App.tsx`, `AppShell.tsx`, `es-ES.json`, `tests/unit/LoginScreen.test.tsx`)
- [X] T109 Pass the Entra settings to the BFF in `infra/bicep/main.bicep` and the parameter example; document the app registration in `docs/runbooks/azure-bootstrap.md` §6
