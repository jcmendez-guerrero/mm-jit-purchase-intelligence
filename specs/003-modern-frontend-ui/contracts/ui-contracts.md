# UI Contracts: MMI 003 — Modern Web Interface

This feature adds no HTTP API, event or JSON Schema (`packages/contracts` is untouched). The interfaces below are the contracts the interface exposes to its users and between its own parts. They are checked by unit and end-to-end tests.

## 1. Route table

| Path | Screen (es-ES label) | Group | Roles offered | Notes |
|---|---|---|---|---|
| `/` | — | — | any | Redirects to `/panel` |
| `/panel` | Panel de control | seguimiento | any signed-in | Query: `almacen` (warehouse id, optional) |
| `/calidad` | Calidad y datos | seguimiento | any signed-in | |
| `/propuestas` | Propuestas de compra | compras | any signed-in | |
| `/escenarios` | Escenarios | compras | any signed-in | |
| `/costes` | Costes y proveedores | compras | any signed-in | |
| `/proveedores` | Proveedores | configuracion | any signed-in | |
| `/importaciones` | Datos predictivos | configuracion | any signed-in | |
| `/configuracion` | Configuración | configuracion | any signed-in | |
| `/administracion` | Administración (estado y roles) | administracion | `admin` | Other roles reaching it directly see the no-access state |
| `*` | Not found | — | any | Offers a link to `/panel` |

Rules: each path loads the same screen on reload and on back/forward; the offered set only controls what the navigation and palette show — the backend remains the authority on permissions. Paths are stable once released (bookmarks).

## 2. Navigation and palette behaviour

- Navigation lists groups in order seguimiento, compras, configuracion, administracion; empty groups are not rendered.
- Current item has `aria-current="page"`.
- Palette: opens on `Ctrl/Cmd+K` and via a visible button; input has `role="combobox"`, results `role="listbox"`; matching is case- and accent-insensitive on translated label; `Enter` navigates, `Esc` closes and returns focus to the opener; lists only items allowed for the role; searches screens only.
- First focusable element on every page is the "skip to content" link targeting the main landmark.
- Below 1024 px the rail is replaced by a menu button that opens the same grouped list in a native modal drawer: it closes after a choice, on `Esc` and on a click outside, returns focus to the menu button, and closes itself when the window becomes wide. The header then shows the isotipo instead of the horizontal logo.
- Hard-to-reverse or externally visible actions (approve, release or override a cost, ignore or release a quarantined movement, reject, activate or roll back an import, promote a scenario, change a role) ask through `ConfirmDialog` before the existing call; confirm sends the request the screen always sent, cancel sends nothing.

## 3. Browser storage keys

| Key | Values | Default | Notes |
|---|---|---|---|
| `mmi.ui.appearance` | `system` \| `light` \| `dark` | `system` | Read by `public/theme-init.js` before first paint; invalid → `system` |
| `mmi.ui.density` | `comfortable` \| `compact` | `comfortable` | Invalid → default |

No other browser storage is introduced. Keys hold no personal or business data.

## 4. Theme and design tokens

- `public/theme-init.js` sets the attribute before first paint; `startThemeSync` (from `main.tsx`) keeps it current when the choice or, for "system", the device preference changes.
- The theme is the `data-theme` attribute (`light` | `dark`) on the document root; absence of a stored choice resolves from `prefers-color-scheme`.
- Tokens are CSS custom properties prefixed `--mmi-` grouped as colour (surface, text, border, brand, status tones), type scale, spacing scale, radius, elevation, motion, layout (sidebar width, content max width). Screens use tokens, not literal colours (lint rule or test over `src/**/*.css` and inline styles for hex colours outside `tokens.css`).
- Each text/background pair used by primitives meets WCAG 2.2 AA contrast in every shipped theme.

## 5. Primitive component contracts (behavioural)

| Primitive | Must guarantee |
|---|---|
| `PageHeader` | One `h1` per page; title, context line and primary actions in fixed positions |
| `PageActions` | Renders a screen's primary actions in the page header's actions slot through a portal; handlers stay with the screen; outside the app shell (isolated tests) the actions render where they are written |
| `DataTable` | `<table>` semantics; sticky header; `aria-sort` on sortable columns; scroll region is keyboard focusable and labelled; row count announced; pagination controls labelled; density from preference; a sort button's accessible name is the column header and the "sort by" hint is its `title`, so label lookups on a column name find the input and not the button |
| `StatusBadge` | Always text plus icon; tone from the status vocabulary; no colour-only meaning |
| `ScreenState` | Renders exactly one of loading / empty / error / no-access; error includes retry; a load error that is the no-permission sentence (HTTP 403) is shown as an access explanation with a link to the dashboard and no retry; loading uses a skeleton shaped like the final content (lines, table or dashboard) |
| `FormField` | Label bound to control; hint and error linked with `aria-describedby`; `aria-invalid` when in error; `useFieldErrors` shows format messages beside fields, moves focus to the first invalid field and clears a message when its field changes |
| `ConfirmDialog` | Native modal; focus moves in and returns on close; `Esc` cancels; initial focus on the safe (cancel) action for danger tone; states object and effect |
| `NoticeProvider` | Polite live region; no focus steal; dismissible by keyboard; does not cover primary actions |
| `Skeleton` | `aria-hidden`; wrapper sets `aria-busy`; no animation under reduced motion |

## 6. Translation contract

Every user-facing string introduced by this feature is a key in `src/i18n/es-ES.json`; the existing i18n coverage and hard-coded-string tests must pass, with `hardcoded-strings.baseline.json` reduced to zero for the shell files (`Navigation.tsx`, `App.tsx`). Numbers, currency and dates use the existing es-ES formatters.

## 7. Network contract

The built application and its nginx configuration make no request to any host other than the same origin. The content security policy no longer lists third-party font hosts. Verified by an end-to-end test that fails on any cross-origin request.
