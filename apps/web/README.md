# MMI web app

React and TypeScript single-page app for the purchasing team. Spanish (es-ES) only. Tests and local development use synthetic data only; never point the app at a real Siweb host.

## Commands

```bash
npm ci
npm run dev        # Vite dev server on :5173, proxies /api to :8081
npm run typecheck && npm run lint && npm test
npm run e2e        # Playwright, with mocked backends
npm run build && npm run check:bundle
```

## Interface conventions

The visual direction is in `specs/003-modern-frontend-ui/design.md` and follows the brand identity manual (colours, Bricolage Grotesque for titles, Inter for text, logo rules). What the code must follow:

- **Tokens.** Colours, type, spacing, radius and motion are CSS custom properties in `src/styles/tokens.css`, the only file allowed to contain colour literals (a unit test guards this). The dark appearance re-maps the colour roles in the same file; brand colours never change.
- **Primitives** live in `src/ui/` and never import from `src/features/`: `Button`, `Card`, `PageHeader`, `PageActions` (a screen's primary actions in the page header), `DataTable`, `StatusBadge`, `FormField` and `useFieldErrors` (field-level messages), `FilterBar`, `SeverityRuler`, `ScreenState` (loading, empty, error, no access), `ConfirmDialog`, `NoticeProvider`, `UnsavedChangesPrompt`, `ThemeToggle`. Statuses are rendered only through `StatusBadge` and the vocabulary in `src/ui/statusVocabulary.ts`, so they always carry an icon and a word.
- **Routes and navigation** come from one registry, `src/app/routes.ts` (Spanish paths such as `/panel`). The navigation rail, the drawer (below 1024 px), the quick-jump and the route table all read it. The registry only decides what is offered; the backend decides what is allowed.
- **Preferences** (appearance, table density) are stored in this browser only, under `mmi.ui.appearance` and `mmi.ui.density`. `public/theme-init.js` sets the theme before first paint.
- **Text.** Every user-facing string is a key in `src/i18n/es-ES.json`; numbers, euros and dates use the formatters in `src/i18n/formatters.ts`.
- **No third-party hosts at runtime.** Fonts and icons are served from this origin, and the content security policy in `nginx.conf.template` allows no other host.
- **Risky actions** (approve or submit a proposal, release or override a cost, release or ignore a quarantined movement, reject, activate or roll back an import, promote a scenario, change roles) ask first through `ConfirmDialog`; a new hard-to-reverse action must do the same. The dialog only wraps the existing call; separation of duties, fresh authentication and the audit stay on the server.
- **Accessibility.** WCAG 2.2 AA in both appearances; the end-to-end suite runs axe on every route in light and dark.

## Development sign-in

The development sign-in strip is shown in development builds only (or when a build sets `VITE_ENABLE_DEV_LOGIN=1`). The server separately refuses it unless `MMI_ENABLE_DEV_LOGIN=1` and `MMI_ENV` is not `prod`.
