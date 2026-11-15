# UX, navigation and Spanish localization (MMI-10, feature 012)

Jira: [MMI-10](https://mundomascotix.atlassian.net/browse/MMI-10). Spec: `specs/012-ux-navigation-localization/`. Confluence: page 3080459.

## What changed

An audit of the web app first (`evidence/audit-inventory.md`), then only the gaps it found. Presentation, wording and interaction only; no API, contract, ERP, migration or business-rule change.

- **Navigation:** after a screen change focus moves to the page heading (rail and quick-jump); the redirect from `/` is ignored. `PageHeader` headings are focusable (`tabIndex=-1`).
- **Spanish text:** a missing catalogue key now shows "Texto no disponible" instead of the raw key; development logs which key. New checks fail on Spanish sentences in `.ts` files, empty keys and newly unused keys (a baseline of 95 existing unused keys may only shrink).
- **Glossary:** `glossary.json` (preferred term, forbidden variants) with definitions in `es-ES.json`; a test fails on forbidden variants. Fixed "plazo de reposición" → "plazo de entrega".
- **Formats:** service level in the policy history uses `formatPercent` (comma decimals); the history date uses `formatDate`. `formatPercent` gained an optional `minDecimals`.
- **Product journey:** the product detail heading shows the SKU and name, not the Siweb variant id.
- **States:** `AuditScreen` now has a loading placeholder and an error state with retry. A test requires every `*Screen.tsx` to use `ScreenState` (one documented exception: the local-only loader).
- **Help:** new `HelpHint` (button + glossary definition, closes with Escape) beside "nivel de servicio" and "stock de seguridad".
- **Accessibility and responsive:** axe now runs on every route at 1280, 768 and 375 px, light and dark; no horizontal scroll at 375 px; palette focus check.
- **Tests:** unit tests 552 → 600; browser tests extended (navigation focus, 27 route accessibility cases, 375 px).

## Cross-feature changes

Listed in `agent-00-contract-note.md`. Shared: `PageHeader`, `AppShell`, `formatters.ts`, `i18n/index.ts`, `HelpHint`, `components.css`. Screen-level: 006 `ProductDetail`, 010 `AuditScreen`, 011 `PurchasingSection` and `SafetyStockSection`. Owning features' tests still pass.

## Evidence

Screenshots in `evidence/screenshots/` (synthetic data): dashboard at 1280, 768 and 375 px, product detail with SKU, quick-jump, error state, narrow menu. Test results in `evidence/verification.md`.

## Risks and known limitations

- **Siweb variant id still typed by users** in the override editor, the safety-stock queue and the demand exclusions. Rule 5 says users enter the SKU. This needs a SKU-to-variant lookup in the gateway (a contract change for Agent 00); recorded in the note and guarded in `glossary.test.ts`.
- **Not done in this PR:** role-change-while-open end-to-end test (T013), proposal step indicator check (T015), a dedicated product journey spec (T016) and the supplier journey work (T020–T024), per-code "next step" check for error messages (T026), forced-state end-to-end test for every screen (T033), the moderated usability run (T045).
- One keyboard test (`reference task 3`) is intermittent and was before this change.
- Gates `e2e`, `security`, `cost` could not run locally (no `pytest`); `contracts` and `isolation` pass.

## Checklist

- Data: synthetic only. Security: no secret, no ERP request, no free-text note shown. Cost: no new service. Contract impact: none.
