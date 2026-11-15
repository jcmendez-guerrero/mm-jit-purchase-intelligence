# UI & Localization Contract

Interface commitments this feature makes to users, other features and CI. No API or schema contract changes. Extends `specs/003-modern-frontend-ui/contracts/ui-contracts.md`.

## 1. Navigation and access

- The route registry is the only source for the rail, the quick-jump and the route table.
- For each role (viewer, buyer, approver, admin) the set of offered screens equals the registry filtered by role and reported capability; the test matrix pins it.
- A direct address the role may not use shows the no-access screen; an unknown address shows the not-found screen; both are Spanish and offer a way back.
- Opening a screen from the quick-jump with the keyboard moves focus to the page heading.

## 2. Text and catalogue

- Every user-visible string (text, titles, accessible names, placeholders, tooltips, notices, export headers) resolves through the es-ES catalogue.
- CI fails on new or changed code that adds user text outside the catalogue, on missing or empty keys, and on a catalogue value containing a forbidden glossary variant.
- Every stable error code in `packages/contracts/errors/error_codes.json` has `errors.<code>`, a Spanish message with a next step; unknown codes use the generic message; codes are never shown as the message.

## 3. Formats

- Amounts in euros, `1.234,56 €`; dates `DD/MM/AAAA` in the local time zone; numbers with dot grouping and comma decimals; percentages with comma decimals. The same formatters serve screens and exports.
- Stored times are UTC; the browser does not recompute money.

## 4. Screen states

- Each data screen presents loading, empty, error (with retry) and success through the shared state components. The layout reserves space for incoming data.

## 5. Accessibility and responsiveness

- No serious or critical axe violations on every route at 1280, 768 and 375 px, in light and dark appearance.
- Dialogs, drawers and the palette trap and restore focus; Escape closes them. Charts have a table alternative; status is never colour-only.
- No horizontal page scroll at 375 px or 200% zoom, except inside data tables.

## 6. Contextual help

- A help control is a button with an accessible name; it opens a short Spanish explanation from the glossary, closes with Escape and returns focus to the control. It never shows free-text ERP notes.

## 7. Cross-feature changes

- Shared component or style changes land first and are recorded in `docs/architecture/integration/` for Agent 00. Screen-level fixes in other features are limited to wording, states and accessibility, are listed by feature and file, and keep the owning feature's tests passing.
