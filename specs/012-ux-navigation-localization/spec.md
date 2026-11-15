# Feature Specification: UX, Navigation & Spanish Localization (Agent 08)

**Feature Branch**: `claude/speckit-specify-mmi-10-ccce8a`

**Created**: 2026-11-13

**Status**: Draft

**Input**: User description: "from MMI-10" — Jira MMI-10 ("AGENT 08 | UX, Navigation & Spanish Localization", epic MMI-1) and its Confluence page 3080459. The Jira text names `specs/003-agent-08/`; number 003 is already taken by the modern-interface feature, and 011 is reserved on another branch, so this spec is **012**.

## Context

Feature 003 already modernised the buyer web app: grouped navigation, a quick-jump palette, shared components (tables, cards, forms, states), light and dark appearance, a skip link, and accessibility and responsive checks. Features 004–011 then added screens (dashboard analytics, supplier commercial management, predictive seed import, administration, policy configuration). The interface has grown screen by screen again, so the owner needs the **whole experience proven consistent**: a buyer or approver can find any task from the navigation, finish the two main journeys (product and supplier) without help, read every message in correct Spanish, and use the app with keyboard and assistive technology.

This is an **audit-then-close-gaps** feature. It starts with an evidence-backed inventory of the current main branch (each item marked complete, partial, broken, missing or unverified, with file and line evidence), reuses what works, and builds only what the inventory shows missing. It changes presentation, wording and interaction only. It adds no business capability, no ERP request of any kind, and no change to purchasing rules, approvals, forecasting or the permitted ERP writes. Siweb360 stays the system of record.

Out of scope: new business capabilities; changes to backend data or decisions; additional languages (the UI stays Spanish es-ES only); a native mobile app; product search inside the quick-jump (screens only, as decided in feature 003); production deployment or merge to main; behaviour, contract or business-rule changes inside other features' screens (presentation, wording and accessibility fixes there are allowed and coordinated through Agent 00).

## Clarifications

### Session 2026-11-13

- Q: When the audit finds a Spanish-text or accessibility gap inside a screen owned by another feature, fix it there or only report it? → A: Fix it directly in any screen (Option B), then record each cross-feature change and coordinate it with Agent 00 afterwards.
- Q: Which roles get the full product and supplier journeys and the usability check? → A: The buyer role (Option A); viewer, approver and admin get automated checks of what is offered, hidden or read-only on those screens.
- Q: Is the untranslated-text check a hard CI failure or a report? → A: Hard failure (Option A) for new or changed code; gaps found by the audit are fixed in this feature so the check starts from a clean baseline.
- Q: Which window sizes must the automated accessibility and responsive checks cover? → A: Three sizes (Option A): desktop 1280 px, tablet 768 px and narrow 375 px, each in light and dark appearance.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find any task from the navigation (Priority: P1)

A signed-in user (viewer, buyer, approver or admin) opens the app and can reach every screen their role allows through a consistent, grouped navigation and the quick-jump, always sees where they are, and never lands on a dead end. Screens their role cannot use are not offered, and a direct link to one shows a clear "no access" explanation.

**Why this priority**: Navigation is the entry to every other journey; if a user cannot find a screen, no other improvement matters.

**Independent Test**: Sign in as each role, list the offered screens, open each from the navigation and from the quick-jump, and confirm the active location is indicated; open a forbidden and an unknown address and confirm the explanation screens.

**Acceptance Scenarios**:

1. **Given** each role, **When** the user opens the navigation, **Then** exactly the screens allowed for that role are offered, grouped by purpose, with the current screen indicated.
2. **Given** any offered screen, **When** the user opens it from the quick-jump using the keyboard only, **Then** it opens and focus lands on the page heading.
3. **Given** an address the role may not use or that does not exist, **When** it is opened, **Then** the user sees a Spanish explanation with a way back, not a blank page.
4. **Given** a narrow window or tablet, **When** the user navigates, **Then** all screens remain reachable and no content is cut off horizontally.
5. **Given** a multi-step workflow (for example reviewing a proposal), **When** the user is in the middle of it, **Then** the screen shows the step they are on and how to return to the list.

---

### User Story 2 - Complete the product journey end to end (Priority: P1)

A buyer follows one product from the dashboard signal to a decision: sees a product at risk, opens its detail (stock, demand, supplier terms, quality warnings), reaches the related proposal or scenario, and understands the next step, using the product's SKU throughout.

**Why this priority**: The product journey is the daily purchasing task; it is a named completion gate.

**Independent Test**: With synthetic data, start from the dashboard, open a product by SKU, follow the links to its supplier and proposal lines, and return, using keyboard only and then with a screen reader's accessible names checked.

**Acceptance Scenarios**:

1. **Given** a product flagged at risk on the dashboard, **When** the buyer opens it, **Then** the detail shows the SKU, stock position, supplier terms and any data-quality warning with a plain explanation.
2. **Given** a product detail, **When** the buyer follows a link to its supplier or to a proposal line, **Then** the destination opens with the context preserved and a way back to the same product.
3. **Given** a product with missing or ambiguous data, **When** it is shown, **Then** the screen says what is missing and what the user can do, never a blank or a raw error.
4. **Given** any product screen, **When** it is shown, **Then** users see and enter the SKU, never an internal ERP identifier.

---

### User Story 3 - Complete the supplier journey end to end (Priority: P1)

A buyer finds a supplier, reviews its commercial terms and linked products, edits them or imports them, and sees the effect of the change, with clear confirmation, validation messages and protection against losing unsaved edits.

**Why this priority**: Supplier conditions drive purchase quantities; the journey is the second named completion gate.

**Independent Test**: With synthetic data, search a supplier, open its terms, edit with a validation error, correct it, leave with and without unsaved changes, and import a terms file with a rejected row.

**Acceptance Scenarios**:

1. **Given** the suppliers screen, **When** the buyer searches, filters and opens a supplier, **Then** its terms, linked products and review state are shown consistently with other detail screens.
2. **Given** an invalid entry, **When** the buyer saves, **Then** the message names the field and the rule in Spanish and focus moves to the first error.
3. **Given** unsaved edits, **When** the buyer navigates away, **Then** they are asked to confirm before losing them.
4. **Given** an import with rejected rows, **When** it finishes, **Then** the rejected rows and reasons are listed and nothing is dropped silently.

---

### User Story 4 - Every visible word is correct Spanish (es-ES) with Spanish formats (Priority: P1)

Every label, button, message, tooltip, table header, empty state, error, page title, accessible name and exported header the user can see is Spanish (es-ES), uses one consistent vocabulary for the same concept, and shows money in euros and dates and numbers in Spanish format.

**Why this priority**: "No untranslated user text" is an explicit completion gate and a project rule.

**Independent Test**: Run the automated check that scans screens for text not coming from the translation catalogue and for catalogue entries that are missing, empty or unused; then open every screen in each state and review the text.

**Acceptance Scenarios**:

1. **Given** any screen in any state (loading, empty, error, success), **When** it is displayed, **Then** all user-visible text comes from the Spanish catalogue and none is hard-coded or in another language.
2. **Given** an amount, a date and a quantity, **When** they are shown or exported, **Then** the amount is in euros with Spanish separators, the date in Spanish format in the local time zone, and the quantity with Spanish number format.
3. **Given** a server error with a stable code, **When** it reaches the user, **Then** it appears as a Spanish message with a next step, never as a raw code or technical text.
4. **Given** the same concept (for example "propuesta", "proveedor", "cobertura"), **When** it appears on different screens, **Then** it uses one agreed term from a shared glossary.

---

### User Story 5 - Clear loading, empty, error and help states everywhere (Priority: P2)

Every data screen shows a loading indicator that matches the layout, a helpful empty state that says why it is empty and what to do, an error state with a retry, and contextual help (short explanations of key terms and rules) next to the controls that need it.

**Why this priority**: It removes guesswork and support calls, but each screen already has a basic version.

**Independent Test**: For each screen, force each state with synthetic data or simulated failures and check the content, the retry, and that help text opens and closes by keyboard.

**Acceptance Scenarios**:

1. **Given** a screen whose data is loading, **When** it takes longer than a moment, **Then** a placeholder of the same shape is shown and the layout does not jump when data arrives.
2. **Given** a screen with no data, **When** it is shown, **Then** it explains the reason (nothing loaded yet, filters too narrow, no permission) and offers the relevant action.
3. **Given** a failed request, **When** the error is shown, **Then** it keeps the user's input, offers a retry and does not expose technical details.
4. **Given** a control with a business term (for example safety stock or lead time), **When** the user opens its help, **Then** a short Spanish explanation appears and can be dismissed with the keyboard.

---

### User Story 6 - Usable with keyboard, screen reader, zoom and different screens (Priority: P2)

A person using only a keyboard, a screen reader, 200% zoom, reduced motion or a high-contrast need can complete the core journeys on desktop, tablet and a narrow window.

**Why this priority**: It is a completion gate (automated accessibility checks) and a quality bar, and builds on what feature 003 started.

**Independent Test**: Run the automated accessibility checks on every route in light and dark appearance and at three window sizes, then perform the core journeys with keyboard only.

**Acceptance Scenarios**:

1. **Given** any route, **When** the automated accessibility check runs, **Then** it reports no serious or critical violations.
2. **Given** any dialog, drawer or palette, **When** it opens and closes, **Then** focus moves into it, stays inside while open and returns to the trigger on close.
3. **Given** a chart, **When** shown, **Then** an equivalent data table is available and status is never conveyed by colour alone.
4. **Given** 200% zoom or a narrow window, **When** a journey is completed, **Then** no information or control is lost and no horizontal scroll appears except inside data tables.

---

### Edge Cases

- A role changes while a screen is open: the navigation and the screen update to the new permissions without a stale offer.
- A translation entry is missing at runtime: the user sees a readable Spanish fallback, and the automated check fails the build.
- Very long product or supplier names, many rows, or very large amounts: text wraps or truncates with the full value available, and the layout does not break.
- A server error with an unknown code: a generic Spanish message with a next step is shown and the code is kept for support only.
- Free-text notes from the ERP are never displayed (only a "has note" indicator), including in help, tooltips and exports.
- Dates near a daylight-saving change: the Spanish local date shown matches the stored UTC instant.
- A shared component change would affect another feature's screen, or a screen-level fix touches another feature's files: the change is listed in the delivery notes and coordinated with Agent 00, and the other feature's existing tests must still pass.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST begin with an inventory of the current main branch, classifying each navigation, journey, localisation, state and accessibility item as complete, partial, broken, missing or unverified, with file and line evidence, and MUST reuse what already works.
- **FR-002**: Users MUST be offered exactly the screens their role allows, grouped consistently, with the current location always indicated and a quick-jump available by keyboard.
- **FR-003**: Opening a screen the role may not use, or an unknown address, MUST show a Spanish explanation with a way back; the backend remains the authority on permissions.
- **FR-004**: The product journey (dashboard signal → product detail → supplier/proposal → return) MUST be completable with context preserved and the SKU shown and entered throughout; internal ERP identifiers MUST NOT be shown or requested.
- **FR-005**: The supplier journey (search → terms → edit or import → confirmation) MUST be completable with field-level Spanish validation, focus moved to the first error, unsaved-change protection and a visible list of rejected import rows.
- **FR-006**: All user-visible text, including titles, accessible names, tooltips, placeholders, empty and error states, notices and export headers, MUST come from the single Spanish (es-ES) catalogue; no hard-coded or non-Spanish user text.
- **FR-007**: An automated check MUST run in CI as a hard failure (blocking the change) and MUST fail when a screen contains user text outside the catalogue, or when the catalogue has missing, empty, duplicate-meaning or unused entries.
- **FR-008**: Amounts MUST be shown and exported in euros with Spanish formatting; dates and times in Spanish format in the user's local time zone while the stored value stays UTC; quantities and percentages in Spanish number format; money MUST never pass through binary floating point in the interface.
- **FR-009**: A shared glossary of business terms MUST define one Spanish term per concept, and every screen MUST use it.
- **FR-010**: Server errors MUST be translated by stable code into Spanish messages with a next step; unknown codes MUST fall back to a generic message; technical details MUST NOT be shown.
- **FR-011**: Every data screen MUST provide loading, empty, error (with retry) and success states with the content defined in User Story 5, and the layout MUST NOT shift when data arrives.
- **FR-012**: Contextual help MUST be available next to controls and terms that need it, keyboard-operable, in Spanish, and MUST NOT show free-text ERP notes.
- **FR-013**: The interface MUST meet WCAG 2.2 AA for the core journeys: keyboard operation, visible focus, focus management in dialogs/drawers/palette, accessible names, contrast, reduced motion, text alternatives for charts, and no colour-only status.
- **FR-014**: The interface MUST work at desktop (1280 px wide), tablet (768 px) and narrow (375 px) window sizes, in light and dark appearance, and at 200% zoom without loss of information or function.
- **FR-015**: Shared interface components and styles MUST keep one consistent look and behaviour across screens. Gaps in wording, states, navigation or accessibility MAY be fixed directly in any screen, including screens introduced by other features; every such cross-feature change MUST be limited to presentation, wording and interaction (no behaviour, contract or business-rule change), be listed in the delivery notes by feature and file, and be coordinated with Agent 00 (shared components first, before the screen-level fixes that depend on them).
- **FR-016**: The feature MUST NOT add or change any request to Siweb360, any backend contract, purchasing rule, approval rule, or stored business data; the interface MUST NOT expose secrets, tokens or free-text notes in any text, log or export.
- **FR-017**: The core journeys (navigation, product, supplier) and the accessibility and localisation checks MUST be covered by automated browser tests and unit tests using synthetic fixtures only. The product and supplier journeys MUST be completed end to end as the buyer role; for the viewer, approver and admin roles, automated checks MUST confirm which actions on those screens are offered, hidden or read-only.
- **FR-018**: The delivery MUST include screenshots or equivalent evidence of the Spanish interface for each core journey, the audit inventory, and a list of known limitations.

### Key Entities *(include if feature involves data)*

- **Navigation entry**: A screen the user can open; has a Spanish label and description, a group, an icon, the roles allowed, and an optional capability that must be reported by the application.
- **Translation catalogue entry**: A key with its Spanish text, grouped by area; used by screens, accessible names, errors and exports.
- **Glossary term**: The agreed Spanish term for a business concept, with a short definition reused by contextual help.
- **Screen state**: Loading, empty, error or success presentation of a screen, with its message, cause and available action.
- **Audit inventory item**: A feature element with its status (complete, partial, broken, missing, unverified), evidence and the decision taken (reuse, fix, build).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of routes are reachable from the navigation or quick-jump for the roles that may use them, and 0 routes are offered to roles that may not.
- **SC-002**: A buyer (the only role in the usability check) unfamiliar with the app completes the product journey and the supplier journey, each in under 5 minutes, without help, in a moderated check with synthetic data.
- **SC-003**: 0 untranslated or hard-coded user-visible strings across all screens and states, verified by the automated check on every build.
- **SC-004**: 0 serious or critical accessibility violations on 100% of routes, in light and dark appearance, at desktop, tablet and narrow sizes.
- **SC-005**: 100% of server error codes in the shared list map to a Spanish message with a next step; unknown codes show the generic message.
- **SC-006**: 100% of screens present loading, empty and error states with a working retry, verified by automated tests.
- **SC-007**: Amounts, dates and numbers match Spanish format in 100% of sampled screens and exports.
- **SC-008**: All automated unit and browser tests pass in CI with synthetic data, and no existing test regresses.

## Assumptions

- The existing web app, route table, Spanish catalogue, shared components and test suites are the baseline; this feature extends them rather than rebuilding.
- Spanish (es-ES) is the only language; no language switcher is built.
- Roles are viewer, buyer, approver and admin as already defined; no new role is introduced.
- Backend permission checks stay authoritative; the navigation only decides what is offered.
- Contextual help is short static text per term, not a separate help site or chat assistant.
- A moderated usability check (SC-002) uses a small number of people from the owner's team and synthetic data; it is reported, not a build gate.
- Dependencies: feature 003 (shared components and navigation), features 006, 007, 008, 010 and 011 (screens to be covered), and Agent 00 for any shared interface contract change.
- No production deployment, merge to main, destructive operation or real ERP write is part of this feature.
