# Feature Specification: MMI 003 — Modern Web Interface

**Feature Branch**: `feat/azure-deployment` (current working branch; a dedicated branch may be cut at planning time)

**Created**: 2026-11-08

**Status**: Draft

**Input**: User description: "it is required to optimize the web frontend UI to be a modern interface"

## Context

Features 001 and 002 delivered the buyer web app: dashboard, quality, suppliers, costs, proposals, scenarios, imports, configuration and administration screens, all in Spanish (es-ES). It works, but it was built screen by screen and it shows: a flat row of nine top-level tabs, screens that differ in layout and density, tables that are hard to scan, little visual feedback while data loads or an action runs, and a layout designed for a wide desktop only.

This feature modernises the look, structure and feel of the existing interface so the small purchasing team can find things faster, read the data with less effort and trust what they see. It changes presentation and interaction only. It does not change what the system decides, stores or sends to the ERP.

Out of scope: any new business capability, any change to purchasing rules, proposals, approvals, forecasting or the single permitted ERP write; any change to backend contracts or data; a native mobile app; additional languages (the UI stays Spanish only); marketing or public pages.

### Current-state gap inventory (from the existing app)

| Area | Current state | Gap |
|---|---|---|
| Navigation | Nine tabs in one horizontal bar; admin tab appended by role | Does not scale, no grouping, no indication of where the buyer is in a workflow, no way to jump quickly |
| Layout | Fixed top banner plus tab bar; wide-desktop assumptions | Cramped or broken on tablets and narrow windows; no use of space on large screens |
| Visual language | Brand colours and two typefaces, but per-screen styling in one shared sheet | Inconsistent spacing, cards, buttons, form fields and status colours between screens |
| Data tables | Plain tables | No sticky headers, sorting, density options, empty/loading states or row-level status emphasis |
| Feedback | Mostly text messages | No skeleton loading, no non-blocking confirmations, uneven error presentation |
| Typography source | Fonts requested from a third-party font host at load time | Privacy and offline/slow-network risk; flash of unstyled text |
| Appearance | Light theme only | No dark theme or respect for the user's system preference |
| Accessibility | Charts have table alternatives; axe checks exist | No consistent focus treatment, skip link, reduced-motion handling or contrast guarantee across the new look |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find and reach any screen quickly (Priority: P1)

A buyer opens the app and needs to go from the dashboard to the weekly proposal, then to supplier terms, then back. They want a clear, grouped navigation that shows where they are, works with keyboard and touch, and lets them jump straight to a screen or a product without hunting through tabs.

**Why this priority**: Navigation is used in every session and every other improvement is reached through it. A grouped, persistent navigation with a quick-jump command is a complete, valuable slice on its own.

**Independent Test**: With a synthetic session for each role, open the app, reach every screen the role may see using only navigation and the quick-jump, and confirm the current location is always indicated and unauthorised sections are not offered.

**Acceptance Scenarios**:

1. **Given** a signed-in buyer, **When** the app loads, **Then** the navigation shows screens grouped by purpose (for example daily monitoring, weekly purchasing, configuration, administration), highlights the current screen and shows only the sections the role may use.
2. **Given** any screen, **When** the user opens the quick-jump (keyboard shortcut or a visible search control) and types part of a screen name or a product name, **Then** matching destinations are listed and choosing one navigates there.
3. **Given** a browser reload or a shared link to a screen, **When** it opens, **Then** the same screen is shown (the location is part of the address) and the browser back and forward buttons behave as expected.
4. **Given** a keyboard-only user, **When** they press Tab from page load, **Then** a "skip to content" control is first, and focus order follows the visual order with a clearly visible focus indicator.

---

### User Story 2 - Read and act on data with less effort (Priority: P1)

A buyer reviews the dashboard and the proposal lines. They want tables and cards that are easy to scan: consistent spacing, sticky headers, sortable columns, status shown by colour plus text and icon, readable numbers (EUR, Spanish format) and clear empty, loading and error states.

**Why this priority**: Reading data is the core job of the product. Better tables, cards and states deliver value on every screen and can be released screen by screen.

**Independent Test**: On the dashboard and proposals screens with synthetic data, sort and scan the tables, trigger loading, empty and error conditions, and confirm each shows a designed state rather than a blank area or raw message.

**Acceptance Scenarios**:

1. **Given** a table with more rows than fit on screen, **When** the user scrolls, **Then** the header row stays visible and the row being acted on is visually distinct.
2. **Given** a sortable column, **When** the user activates its header, **Then** rows re-order, the sort direction is announced and shown, and the choice is kept while the user stays on the screen.
3. **Given** data is loading, **When** the screen renders, **Then** placeholder shapes with the final layout appear instead of a blank page or a spinner-only view, and layout does not jump when data arrives.
4. **Given** a request fails or returns no rows, **When** the screen renders, **Then** a designed message in Spanish explains what happened and offers the next step (retry, clear filters, or import data) without hiding other parts of the screen.
5. **Given** a risk, stale-cost or quarantine status, **When** shown anywhere in the app, **Then** it uses the same label, colour and icon everywhere and is never conveyed by colour alone.

---

### User Story 3 - Use the app on tablet, narrow windows and large screens (Priority: P2)

The team sometimes checks stock from a tablet in the shop or works in a half-width window next to the ERP. They want every screen to remain usable and readable at those sizes, and to make good use of a wide monitor.

**Why this priority**: Matters daily for some users, but the desktop experience (Stories 1 and 2) is the main path. Small-phone use remains out of scope.

**Independent Test**: Open every screen at tablet portrait, tablet landscape, a half-width desktop window and a large monitor; confirm no horizontal page scroll, no clipped controls and that primary actions remain reachable.

**Acceptance Scenarios**:

1. **Given** a viewport of 768 px width or more, **When** any screen renders, **Then** content reflows without horizontal page scrolling, and wide tables scroll inside their own region with the first identifying column kept visible.
2. **Given** a narrow viewport, **When** the navigation renders, **Then** it collapses to a compact control that opens the same grouped destinations and closes after a choice.
3. **Given** a very wide viewport, **When** a screen renders, **Then** content uses a sensible maximum width or a multi-column layout so lines and tables stay readable.
4. **Given** a touch device, **When** the user taps controls, **Then** each interactive target is large enough to hit reliably without accidental neighbouring actions.

---

### User Story 4 - Consistent forms, actions and feedback (Priority: P2)

A buyer edits supplier terms, policies or scenario parameters and releases a cost. They want forms that look and behave the same everywhere, validation that appears next to the field, confirmations that do not block the screen, and a clear, deliberate step for risky actions.

**Why this priority**: Improves trust and reduces errors on configuration and approval flows, but depends on the shared visual foundation delivered in Stories 1 and 2.

**Independent Test**: Edit and save a supplier term, submit a proposal for approval and attempt an action that needs fresh authentication, with synthetic data; verify field-level validation, unsaved-change protection, non-blocking confirmations and a distinct confirmation step for irreversible or externally visible actions.

**Acceptance Scenarios**:

1. **Given** an invalid field value, **When** the user leaves the field or submits, **Then** a Spanish message appears beside the field, focus moves to the first invalid field on submit, and the message is available to assistive technology.
2. **Given** a form with unsaved changes, **When** the user tries to leave, **Then** they are asked to keep editing or discard, and nothing is lost silently.
3. **Given** an action completes, **When** the system confirms it, **Then** a brief notice appears without blocking the page, stays available long enough to read, and can be dismissed by keyboard.
4. **Given** an action that approves, releases a cost to the ERP or is otherwise hard to reverse, **When** the user triggers it, **Then** a clear confirmation step states what will happen and to what (item, supplier, amount), and the safeguards from earlier features (separation of duties, fresh authentication) remain exactly as they are.

---

### User Story 5 - Choose an appearance that suits the environment (Priority: P3)

A user working in a dim storeroom or late in the evening wants a dark appearance; others prefer light. The app follows the device preference by default and lets the user override it.

**Why this priority**: A comfort improvement that rounds off a modern interface; no business flow depends on it.

**Independent Test**: Switch the device preference and the in-app setting; confirm all screens, charts and status colours remain legible and meet contrast requirements in both appearances, and the choice persists across reloads.

**Acceptance Scenarios**:

1. **Given** no saved choice, **When** the app loads, **Then** it uses the device's light or dark preference.
2. **Given** the user selects light, dark or "system" in the appearance control, **When** they reload, **Then** the choice is kept for that browser.
3. **Given** either appearance, **When** any screen, chart or status badge is shown, **Then** text and meaningful graphics meet the contrast requirements of the accessibility target.

---

### Edge Cases

- A very long product name, supplier name or note flag in a table cell or card: it truncates or wraps predictably, the full text remains reachable, and layout does not break.
- A very large result set (thousands of rows): the table remains responsive and navigable (pagination or virtual scrolling), without freezing the browser.
- A slow or interrupted network: loading states persist honestly, failed requests can be retried, and the app never shows stale data as if it were fresh.
- Session expiry or loss of permission while on a screen: the user sees a clear explanation and a route to sign in again, without a blank or broken page.
- A user who prefers reduced motion: animations and transitions are removed or minimised.
- A user who zooms to 200 % or enlarges the base text size: content reflows and nothing is clipped or overlaps.
- Fonts or icons fail to load: a legible fallback is used and layout stays stable.
- Printing or exporting a proposal view: printed output stays legible and omits navigation chrome.
- A role without access to a section opens its address directly: they see a clear "no access" message, not an empty page.

## Requirements *(mandatory)*

### Functional Requirements

**Navigation and structure**

- **FR-001**: The interface MUST present navigation grouped by purpose, indicate the current location, and show only sections the signed-in role is allowed to use.
- **FR-002**: Each screen MUST have its own shareable address; reloading, bookmarking, and browser back/forward MUST return the user to the same screen.
- **FR-003**: Users MUST be able to open a quick-jump control by keyboard shortcut and by a visible control, search screens by name, and navigate to the chosen result.
- **FR-004**: The interface MUST provide a "skip to content" control and a logical focus order on every screen.
- **FR-005**: Each screen MUST show a consistent page header with title, short context line and primary actions in the same place.

**Visual system and consistency**

- **FR-006**: The interface MUST use one shared visual system (colour, type scale, spacing, radius, elevation, iconography) applied to all existing screens, preserving the Mundo Mascotix brand colours and logo.
- **FR-007**: Buttons, form fields, cards, badges, tabs, dialogs and notices MUST look and behave identically across screens, with defined default, hover, focus, disabled, loading and error states.
- **FR-008**: Status information (risk level, stale cost, quarantine, approval state, import state) MUST use a single set of labels, colours and icons throughout, and MUST never rely on colour alone.
- **FR-009**: The interface MUST ship its typefaces and icons with the application rather than loading them from third-party hosts at runtime.

**Data presentation**

- **FR-010**: Data tables MUST support a sticky header, sortable columns where ordering is meaningful, and a user-selectable row density (comfortable and compact).
- **FR-011**: Tables with many columns MUST scroll within their own region while keeping the identifying column visible.
- **FR-012**: Large result sets MUST remain responsive through pagination or incremental rendering.
- **FR-013**: Every screen that loads data MUST show a loading placeholder matching the final layout, a designed empty state, and a designed error state with a retry action.
- **FR-014**: Charts MUST adopt the shared visual system, remain keyboard operable, and keep their table and text-summary alternatives.
- **FR-015**: Numbers, currency and dates MUST continue to use Spanish (es-ES) formats with EUR; no user-facing text may be hard-coded outside the translation resources.

**Interaction and feedback**

- **FR-016**: Validation messages MUST appear next to the affected field in Spanish, move focus to the first invalid field on submit, and be exposed to assistive technology.
- **FR-017**: Forms MUST warn before the user leaves with unsaved changes.
- **FR-018**: Completed actions MUST be confirmed with a non-blocking notice that is dismissible by keyboard and does not obscure controls.
- **FR-019**: Hard-to-reverse or externally visible actions (approval, cost release, deletion, import activation) MUST require an explicit confirmation step that names the object and effect. Existing safeguards (separation of duties, fresh authentication, audit) MUST be unchanged.
- **FR-020**: Session expiry, lost permission and "no access" conditions MUST show a clear Spanish explanation and a way forward.

**Responsiveness and appearance**

- **FR-021**: All screens MUST be usable without horizontal page scrolling from a 768 px viewport width upward, and MUST make sensible use of very wide screens.
- **FR-022**: Navigation MUST collapse to a compact control on narrow viewports and offer the same destinations.
- **FR-023**: Interactive targets MUST be large enough for reliable touch use.
- **FR-024**: The interface MUST offer light, dark and "system" appearances, default to the device preference, and persist the user's choice in the browser.
- **FR-025**: The interface MUST respect the user's reduced-motion preference and remain usable at 200 % zoom and with enlarged text.

**Quality and constraints**

- **FR-026**: The interface MUST meet WCAG 2.2 level AA on every screen in both appearances.
- **FR-027**: The modernisation MUST NOT change the business logic, data shown, API contracts, role rules or audit behaviour of any existing screen; every existing end-to-end flow MUST continue to pass.
- **FR-028**: Tests and demonstrations MUST use synthetic data only; screenshots or recordings kept in the repository MUST contain no real data.
- **FR-029**: The interface MUST stay within the existing front-end size budgets (total and charts) or the budgets MUST be changed explicitly and justified in the plan.

### Key Entities *(include if feature involves data)*

- **Navigation item**: A destination in the app: label (Spanish), group, address, roles allowed to see it, and an optional keyboard shortcut.
- **User interface preference**: Per-browser choices — appearance (light, dark, system) and table density. Stored locally, contains no personal or business data.
- **Status vocabulary**: The single agreed set of statuses (risk, cost freshness, quarantine, approval, import) with label, colour role and icon, shared by all screens.
- **Screen state**: The loading, empty, error, no-access and ready states every data screen must provide.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A buyer can reach any permitted screen in at most 2 interactions from any other screen (one with quick-jump), measured on the synthetic role scenarios.
- **SC-002**: In a moderated check with the purchasing team, at least 80 % of participants rate the new interface "clearer" or "much clearer" than the current one, and none report a task that became harder.
- **SC-003**: Task completion time for three reference tasks (find a product at risk, review and submit the weekly proposal, edit one supplier term) is at least 20 % shorter than the current interface, or not longer for any individual task.
- **SC-004**: 100 % of screens pass automated accessibility checks with no serious or critical violations in both light and dark appearances, and a keyboard-only run completes every reference task.
- **SC-005**: Every screen is usable without horizontal page scrolling at 768 px width and above, verified on tablet portrait, tablet landscape, half-width desktop and large monitor sizes.
- **SC-006**: On a typical office connection, the first meaningful view of the dashboard appears within 2 seconds and layout does not visibly shift when data arrives.
- **SC-007**: The app loads no fonts, icons or scripts from third-party hosts; a page load with outbound third-party access blocked looks and works identically.
- **SC-008**: All pre-existing automated suites (unit, end-to-end, accessibility, bundle budget) pass unchanged in behaviour, and the visual system is applied to 100 % of existing screens.
- **SC-009**: Every data screen demonstrably provides loading, empty and error states (verified per screen in automated tests).

## Assumptions

- Users are the small purchasing team on modern desktop browsers, plus occasional tablet use; small-phone layouts (below 768 px) are out of scope but the navigation should not break there.
- The existing brand colours, logo and Spanish-only language are retained; this is a refinement of the identity, not a rebrand.
- No backend, contract, database or infrastructure change is needed; where a screen needs data it does not yet receive, the gap is recorded and handled outside this feature.
- Where a front-end library would speed up delivery (components, icons, fonts), its use is a planning decision and must satisfy the shared-cost, bundle-size, licensing and public-repository constraints; the specification does not mandate one.
- The charts delivered in feature 002, with their table alternatives, remain the charting approach; only their styling changes.
- Table density, appearance and similar preferences are stored in the browser only; no server-side user profile is introduced.
- Rollout can be incremental, screen by screen behind the same deployment, as long as no screen is left half-migrated in a release.
- Constitution rules continue to apply: Spanish (es-ES) only, no hard-coded user-facing strings, synthetic data only, no secrets, humans decide purchases.
