# Research: UX, Navigation & Spanish Localization

All Technical Context items are resolved from the existing repository; no open clarifications.

## R1. Reuse the existing untranslated-text check, extend it

- **Decision**: Keep `apps/web/tests/unit/i18n-coverage.test.ts` (error-code coverage plus a per-file hard-coded-text counter against `hardcoded-strings.baseline.json`) and extend it. The baseline is already empty (`{}`), so the check is a hard failure today (FR-007, Clarification 3).
- **Rationale**: The scanner only sees JSX text and four attributes in `.tsx` files. It misses user text built in `.ts` models (labels, notices, export headers) and text passed through helper functions. Extending beats rewriting.
- **Alternatives**: A lint rule for i18n (adds a dependency and configuration); a runtime pseudo-locale (useful but does not fail CI by itself). Rejected as extra for the same result; a pseudo-locale pass may be used by the audit only.

## R2. Glossary as data, enforced by test

- **Decision**: Add `apps/web/src/i18n/glossary.json` (concept key → preferred es-ES term, forbidden variants, short definition). A unit test fails when a catalogue value contains a forbidden variant. Contextual help text reads the same definitions.
- **Rationale**: One source for consistency (FR-009) and help (FR-012) without a separate help system.
- **Alternatives**: Wiki-only glossary (not enforceable); per-screen wording (the current state, which drifts).

## R3. Role-by-route navigation matrix

- **Decision**: Generate the expected route list per role from `routes.ts` and assert it in a unit test and one end-to-end pass per role (viewer, buyer, approver, admin), including direct links to forbidden and unknown addresses.
- **Rationale**: `routes.ts` is already the single source for the rail, the palette and the route table; `routes.test.ts` exists. This closes SC-001 without new structure.
- **Alternatives**: Manual review (not repeatable).

## R4. Screen-state coverage

- **Decision**: A unit test renders each screen with mocked loading, empty and error responses through the shared `ScreenState` component and asserts the Spanish content and a working retry. Screens that bypass `ScreenState` are listed by the audit and migrated.
- **Rationale**: `ScreenState`, `EmptyState`, `ErrorState` and `Skeleton` already exist; the gap is proof of use on every screen (FR-011, SC-006).
- **Alternatives**: End-to-end only (slow, harder to force failures).

## R5. Accessibility and responsive matrix

- **Decision**: Run the existing axe suites (`a11y-all-routes.spec.ts`, `a11y-screens.spec.ts`) at 1280, 768 and 375 px in light and dark (Clarification 4); extend `responsive.spec.ts` and `touch-targets.spec.ts` to the same sizes. Larger and smaller sizes already covered by existing tests stay.
- **Rationale**: Reuses `@axe-core/playwright` and the existing Playwright projects.
- **Alternatives**: Add a visual-regression tool (new dependency, flaky); rejected.

## R6. Money and dates in the browser

- **Decision**: Keep the `Intl`-based formatters in `formatters.ts` for display only. The audit checks that amounts arrive from the API as decimal strings and are formatted, never summed or rounded in the browser; any such case is recorded, and fixed only if display-related. Dates are stored UTC upstream; the browser formats to the local zone with the existing date formatter, plus a test around a daylight-saving boundary.
- **Rationale**: `formatCurrencyEUR` parses strings to JavaScript numbers for display, which is acceptable for display of two-decimal amounts but must not become arithmetic.
- **Alternatives**: A decimal library in the browser (new dependency, outside this feature's scope).

## R7. Cross-feature screen fixes

- **Decision**: Fix wording, state and accessibility gaps directly in any feature's screen (Clarification 1), in small commits grouped by feature, shared components first. Each cross-feature change is recorded in `docs/architecture/integration/` as a note for Agent 00, and the other feature's existing tests must still pass.
- **Rationale**: The completion gate demands no untranslated text on any screen; the project's integration rules route shared-surface changes through Agent 00.
- **Alternatives**: Report only (cannot meet the gate); fix only via catalogue (cannot fix hard-coded or structural gaps).

## R8. Contextual help

- **Decision**: A small accessible disclosure component in `ui/` (button plus popover that closes with Escape and returns focus), fed by glossary definitions, used next to terms such as stock de seguridad and plazo de entrega. Added only if the audit confirms no equivalent exists.
- **Rationale**: Keyboard-operable help without a new system (FR-012).
- **Alternatives**: Native `title` tooltips (not keyboard or touch friendly).

## R9. Evidence and screenshots

- **Decision**: Screenshots are captured by Playwright against the mock API with synthetic data and stored under the feature's `evidence/` folder; the audit inventory lives there too.
- **Rationale**: Satisfies FR-018 and the Jira completion gate without any real data.
