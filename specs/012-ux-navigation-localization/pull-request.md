# UX, navigation and Spanish localization (MMI-10, feature 012)

Jira: [MMI-10](https://mundomascotix.atlassian.net/browse/MMI-10). Spec: `specs/012-ux-navigation-localization/`. Confluence: page 3080459.

## What changed

An audit of the web app first (`evidence/audit-inventory.md`), then only the gaps it found. Presentation, wording and interaction only; no API, contract, ERP, migration or business-rule change.

- **Navigation:** after a screen change focus moves to the page heading (rail and quick-jump); the redirect from `/` is ignored. `PageHeader` headings are focusable (`tabIndex=-1`).
- **Spanish text:** a missing catalogue key now shows "Texto no disponible" instead of the raw key; development logs which key. New checks fail on Spanish sentences in `.ts` files, empty keys and newly unused keys. 37 dead keys were removed; 33 keys that the server builds with f-strings stay in a documented baseline that may only shrink.
- **Glossary:** `glossary.json` (preferred term, forbidden variants) with definitions in `es-ES.json`; a test fails on forbidden variants. Fixed "plazo de reposición" → "plazo de entrega".
- **Formats:** service level in the policy history uses `formatPercent` (comma decimals); the history date uses `formatDate`. `formatPercent` gained an optional `minDecimals`.
- **Product journey:** the product detail heading shows the SKU and name, not the Siweb variant id; the detail links to the proposal lines of that SKU and back to the same product (`?producto=`, `?sku=`, `?volver=`); proposals no longer fall back to the variant id.
- **Supplier journey:** a validation message goes away when the value is corrected; help on lead time; permissions per role are tested.
- **Error messages:** every `errors.*` message now says what to do next (52 were rewritten); a test enforces it.
- **Roles:** a 403 re-reads the person's roles so a removed role leaves the menu.
- **Layout:** the administration screen no longer shifts when its data arrives; every screen is checked for a layout shift of 0.1 or less.
- **States:** `AuditScreen` now has a loading placeholder and an error state with retry. A test requires every `*Screen.tsx` to use `ScreenState` (one documented exception: the local-only loader).
- **Help:** new `HelpHint` (button + glossary definition, closes with Escape) beside "nivel de servicio" and "stock de seguridad".
- **Accessibility and responsive:** axe now runs on every route at 1280, 768 and 375 px, light and dark; no horizontal scroll at 375 px; palette focus check.
- **Tests:** unit tests 552 → 745; browser tests 217 → 268 passing (navigation focus, 27 route accessibility cases, 375 px, layout shift, role change, product and supplier journeys, 500 rows and nine-digit amounts, a failed save keeping the typed input).

## Cross-feature changes

Listed in `agent-00-contract-note.md`. Shared: `PageHeader`, `AppShell`, `App.tsx`, `api/client.ts`, `formatters.ts`, `i18n/index.ts`, `HelpHint`, `components.css`. Screen-level: 002 `ProposalsScreen`, 006 `DashboardScreen`, `ProductDetail` and `IndicatorCard`, 007 `SupplierTermsEditor`, 010 `AuditScreen` and `AdminStatusScreen`, 011 `PurchasingSection` and `SafetyStockSection`. Owning features' tests still pass.

## Evidence

Screenshots in `evidence/screenshots/` (synthetic data): dashboard at 1280, 768 and 375 px, product detail with SKU, quick-jump, error state, narrow menu. Test results in `evidence/verification.md`.

## Risks and known limitations

- **Siweb variant id still typed by users** in the override editor, the safety-stock queue and the demand exclusions. Rule 5 says users enter the SKU. This needs a SKU-to-variant lookup in the gateway (a contract change for Agent 00); recorded in the note and guarded in `glossary.test.ts`.
- **Audit CSV** has English headers, ISO timestamps and a comma delimiter, unlike the proposal exports (a server change, requested in the Agent 00 note).
- **Not done in this PR:** T054 (waits for `sku` in six payloads, Agent 00), T045 (the moderated usability run needs a person; the script is in `evidence/usability.md`), T050 (SKU entry in three screens needs a lookup endpoint from Agent 00).
- **Variant id still shown** on six screens (quality, administration policy history, safety-stock queue, demand exclusions, policy preview, scenarios) because their payloads carry only `variant_id`; they need a `sku` field (see `agent-00-contract-note.md`). A guard test stops new ones.
- **Register:** the owner chose tú (T064). The catalogue now addresses the person as tú; `register.json` records the choice and `register.test.ts` fails on usted forms. Server-built messages are not covered.
- Two browser tests that were intermittent on the unchanged code now wait for the supplier terms to load before typing (test-only change; 100 of 100 repeated runs pass).
- Gates `contracts`, `isolation`, `security` and `cost` pass locally with Python 3.12. The `e2e` gate's mocked browser suite passes; its live-stack journey was not run (needs the compose stack).

## Checklist

- Data: synthetic only. Security: no secret, no ERP request, no free-text note shown. Cost: no new service. Contract impact: none.
