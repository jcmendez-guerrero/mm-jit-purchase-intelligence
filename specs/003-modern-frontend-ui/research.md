# Research: MMI 003 — Modern Web Interface

All unknowns from the Technical Context are resolved below. Baseline facts come from `apps/web` at the start of this feature: JS 67 kB gzip total (budget 350), React 18.3, `react-router-dom` 6 installed but unused (tab state is `useState`), fonts requested from Google Fonts in both `index.html` and `index.css`, CSP allows those hosts, nginx already falls back to `index.html` for unknown paths, and `tests/unit/hardcoded-strings.baseline.json` lists 7 hard-coded strings (Navigation 6, Quality 1) plus a hard-coded greeting in `App.tsx`.

## R1. Component foundation: library or in-house primitives

- **Decision**: Build small in-house primitives in `src/ui/` on CSS custom properties; use the native `<dialog>` element for confirmations and the palette. No component library.
- **Rationale**: The team is small and the needed set is limited (header, card, button, badge, table, field, dialog, notice, skeleton, palette). Headless libraries (Radix, React Aria) would help with focus management but add dependency surface, licence review and upgrade work for a public repo; native `<dialog>` already gives focus trapping, Escape handling and inert background. Existing bundle (67 kB) leaves ample budget either way, so size is not the driver; maintenance is.
- **Alternatives considered**: shadcn/ui + Radix (good defaults, but pulls Tailwind and many packages); Material UI / Ant Design (heavy, hard to match brand, large CSS-in-JS); Headless UI (React-only, fine, but little needed beyond native elements). Revisit if the combobox/palette proves costly to make accessible.

## R2. Routing and shareable addresses

- **Decision**: Use the already-installed `react-router-dom` 6 with `BrowserRouter` and Spanish path segments: `/panel`, `/calidad`, `/proveedores`, `/costes`, `/propuestas`, `/escenarios`, `/importaciones`, `/configuracion`, `/administracion`. `/` redirects to `/panel`. The selected warehouse moves from lifted state into a query parameter (`?almacen=`), so a link reproduces the view. Unknown paths show a not-found state.
- **Rationale**: Meets FR-002 with no new dependency. nginx `try_files … /index.html` already serves deep links. Spanish slugs match the Spanish-only rule and are readable in the address bar. Roles only decide what is offered; screens keep their own internal checks and the backend still enforces permissions.
- **Alternatives considered**: Hash routing (works without server config but ugly, breaks anchors); keeping tab state and mirroring to `history` by hand (re-implements the router); English slugs (inconsistent with the Spanish-only UI).

## R3. Navigation information architecture

- **Decision**: Four groups — *Seguimiento* (panel, calidad), *Compras semanales* (propuestas, escenarios, costes), *Configuración* (proveedores, importaciones, configuración), *Administración* (administración, admin role only). Sidebar from 1024 px; below that a header button opens the same list in a drawer. The current item uses `aria-current="page"`.
- **Rationale**: Mirrors the buyer's weekly workflow: look → decide → configure. Keeps every screen within two interactions (SC-001) even without the palette.
- **Alternatives considered**: Keep the top tab bar with overflow menu (does not scale, poor on tablets); mega-menu (too heavy for nine items).

## R4. Quick-jump (command palette)

- **Decision**: A `<dialog>`-based palette opened by `Ctrl/Cmd+K` and a visible search button; ARIA combobox/listbox pattern; filters the navigation registry (screens only, filtered by role); `Enter` navigates; `Esc` closes and restores focus.
- **Rationale**: Per clarification, screens only — no server calls, no new data. The registry is the single source for nav, palette and not-found handling.
- **Alternatives considered**: Product search in the palette (rejected in clarification: needs backend work); third-party palette library (`cmdk`) — unnecessary for ≤ 10 entries.

## R5. Fonts and icons without third-party hosts

- **Decision**: Self-host Bricolage Grotesque (titles) and Inter (body, tables), the typefaces the brand identity manual fixes, as variable fonts via `@fontsource-variable/*` packages (see design.md §2 and §4) (woff2 emitted by Vite into `dist/assets`, `font-display: swap`, Latin and Latin-ext subsets only, which covers Spanish). Remove the `<link>`s and `@import`, and drop `fonts.googleapis.com`/`fonts.gstatic.com` from the CSP. Icons are an in-repo set of inline SVG components drawn on a 24 px grid using `currentColor`.
- **Rationale**: Meets FR-009 / SC-006, improves privacy (Principle II), removes a render-blocking cross-origin request and the flash of unstyled text, and tightens the CSP. Fontsource packages are OFL-licensed and version-pinned in the lockfile. Fonts are not JS, so they do not count towards the JS budget; woff2 files are cached by the browser and served by nginx with long-lived caching.
- **Alternatives considered**: Committing woff2 files manually into `public/` (no update path); an icon package such as `lucide-react` (tree-shakes well, but adds a dependency for ~25 glyphs); emoji (current user chip uses one — inconsistent across platforms, fails contrast control).

- **Typeface note**: the faces are brand-mandated, not a free choice. Inter provides tabular figures (`tabular-nums`) for table columns; Bricolage's optical-size and width axes are used if the Fontsource variable build includes them (verify at implementation; otherwise use weight only).

## R6. Theming (light / dark / system)

- **Decision**: Tokens as CSS variables under `:root` (light) and `:root[data-theme="dark"]`; default follows `prefers-color-scheme`; user choice (`light` | `dark` | `system`) stored in `localStorage`. A tiny same-origin script `public/theme-init.js`, loaded before the stylesheet, applies `data-theme` before first paint. Charts read colours from CSS variables.
- **Rationale**: The existing CSP forbids inline scripts, so the usual inline "no flash" snippet cannot be used; a same-origin file is CSP-compliant. Deriving everything from tokens keeps dark mode a token swap rather than a restyle, which is why the foundation phase designs the palette for both even if dark ships last (clarification).
- **Alternatives considered**: Class toggled after React mounts (visible flash); relaxing CSP with a hash (extra maintenance); two separate stylesheets (duplicated rules).

## R7. Tables: sorting, density, large lists

- **Decision**: A single `DataTable` primitive: sticky header, optional sortable columns (`aria-sort`), horizontal scroll inside a focusable region with a sticky first column, density toggle (comfortable/compact, stored), and client-side pagination (default 50 rows) for lists that can exceed a few hundred rows. Server-paginated screens keep their server paging and only reuse the visual shell.
- **Rationale**: One implementation guarantees consistent behaviour and one place to test accessibility. Pagination is simpler and more predictable for assistive technology than virtual scrolling, and the data volumes (a pet shop catalogue, tens of thousands of rows at most) are adequate. The existing dashboard performance spec guards regressions.
- **Alternatives considered**: Virtualised rows (`react-window`): fast but complicates keyboard navigation, find-in-page and screen-reader row counts; TanStack Table: powerful but more than needed.

## R8. Status vocabulary

- **Decision**: One module maps each status code (risk level, cost freshness, quarantine, approval state, import state) to Spanish label key, colour role and icon, rendered only through `StatusBadge`. Colour roles exist as tokens for light and dark and meet 4.5:1 text contrast.
- **Rationale**: FR-008; removes per-screen ad-hoc colours; one unit test asserts every status has label, icon and a non-colour cue.
- **Alternatives considered**: Colour-only dots (fails WCAG 1.4.1).

## R9. Forms, validation, unsaved changes, notices, confirmations

- **Decision**: `FormField` wires label, hint and error via `aria-describedby`/`aria-invalid`; submit handlers move focus to the first invalid field. `useUnsavedChanges` blocks in-app route changes (router blocker) and warns on tab close (`beforeunload`). Notices render in a polite `aria-live` region, auto-dismiss after ≥ 6 s, pause on hover/focus, close with `Esc`. `ConfirmDialog` names the object and effect using translated templates and is applied to approval, cost release, delete and import activation; it only wraps the existing call, never alters the request or the server-side safeguards.
- **Rationale**: Satisfies FR-016–019 without touching business rules. Errors that need attention stay inline, not in transient toasts.
- **Alternatives considered**: Toast-only errors (easy to miss, fails WCAG 3.3.1 expectations); `window.confirm` (unstyled, not translatable per message, no context).

## R10. Responsive strategy

- **Decision**: Breakpoints at 768 and 1024 px (container-width based where practical): sidebar ≥ 1024, drawer < 1024; content max-width ~1440 px with multi-column cards on wide screens; touch targets ≥ 44 px on coarse pointers (`@media (pointer: coarse)`), 32 px otherwise (WCAG 2.2 target size AA minimum is 24 px).
- **Rationale**: Matches the 768 px floor in the spec and tablet use; large monitors get density rather than stretched lines.
- **Alternatives considered**: Mobile-first phone layouts (out of scope); fluid-only without breakpoints (tables and nav still need structural change).

## R11. Motion, print and zoom

- **Decision**: All transitions use motion tokens and are disabled under `prefers-reduced-motion`; a print stylesheet hides navigation and header and removes sticky positioning; layouts use `rem`/`ch` units and are tested at 200 % zoom.
- **Rationale**: FR-025 and the print edge case.

## R12. Test strategy

- **Decision**: (1) Vitest/Testing Library for each primitive (roles, keyboard, states), the route/nav registry (every route has a label key, group and roles; no duplicates), the status vocabulary and the preference store; (2) Playwright: navigation and deep links per role, palette, viewports (768×1024, 1024×768, 1280×800, 1920×1080) with a "no horizontal page scroll" assertion, 200 % zoom, reduced motion, third-party request blocking (assert zero external requests), loading/empty/error per screen using the existing mocked-backend helpers; (3) axe (WCAG 2.2 AA tags) on every screen in light and, once shipped, dark; (4) existing i18n/hard-coded-string tests with the baseline reduced; (5) existing bundle budget check. Visual snapshot images are not committed (avoid noise and any risk of real data in a public repo); the quickstart lists a manual screenshot review with synthetic data.
- **Rationale**: Covers every success criterion automatically except SC-002 (team clarity rating), which is a short moderated check.

## R13. Rollout and risk

- **Decision**: Ship foundation first (low risk), then per-screen migrations behind the same deployment. Roll back by reverting the screen's migration; no data or API coupling. Risks: CSS regressions between legacy classes and new tokens (mitigated by migrating a screen fully at once and axe/e2e per screen); font file size (variable Latin subset ≈ 100–150 kB total, cached); CSP change breaking fonts (verified by the zero-external-requests test against the built container config).
