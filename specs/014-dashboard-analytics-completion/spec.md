# Feature Specification: Dashboard & Analytics Completion (Agent 01B)

**Feature Branch**: `claude/speckit-jira-mmi-11-93e5e3`

**Created**: 2026-11-16

**Status**: Draft

**Input**: Jira MMI-11 ("AGENT 01B | Complete Dashboard & Analytics feature 006 after PR #19", epic MMI-1), a continuation of MMI-3 and merged PR 19. The original spec, plan and tasks stay in `specs/006-executive-dashboard-analytics/`; this directory (014, the next free number after 013) holds only the completion work, so spec numbers stay unique.

## Context

PR 19 delivered the first part of feature 006: the ten dashboard indicator cards, the v2 contracts and the SKU-first drill-down basics. Jira counts 43 of 97 tasks as delivered; `specs/006-executive-dashboard-analytics/tasks.md` on the current main still lists 48 unchecked tasks (the counts differ because tasks were added after the ticket was written). What the owner needs now is the rest of feature 006 **finished and proven**: filters that survive a page reload and can be shared by link, drill-downs that reach a SKU detail page, analytical charts fed by real data, trustworthy freshness, safe exports, and evidence from a full live run.

This is a **verify-then-close-gaps** feature. It starts by checking every unchecked 006 task against the code on main and classifying it as completed, remaining or unverified. It builds only the verified gaps, keeps the ten indicators and the v2 contracts as they are, and does not rebuild anything that works. Siweb360 stays the source of truth; the dashboard is read-only and this feature adds no ERP request of any kind.

Out of scope: rebuilding the ten indicator cards or changing their definitions; any ERP write; sending orders to suppliers; production deployment or merge to main; changes to files owned by other agents (shared contracts and gates go through Agent 00, MMI-2); new always-on services.

## Clarifications

### Session 2026-11-16

- Q: Is the spec of record for each requirement the original 006 spec or this one? → A: The original `specs/006-executive-dashboard-analytics/spec.md`. This spec adds the closure rules, the verification step and the evidence needed; where the two differ, 006 wins and the difference is raised with Agent 00.
- Q: What happens to a remaining 006 requirement that cannot be delivered now? → A: It is documented with its reason, an owner and a follow-up, and shown in the closure report; it is never left silent. This is allowed only when the cause is outside this feature (for example a missing source of data).
- Q: Does the 006 audit file get rewritten? → A: No. It is updated in place with the new status of each capability, so one audit tells the whole story.

### Session 2026-11-17

- Q: Should the browser-facing gateway API use only the SKU, with `variant_id` kept only between services and in machine-to-machine calls? → A: Yes (option A). Browser and gateway routes and payloads identify products by SKU only; the gateway resolves the SKU to `variant_id` for calls to services; service APIs and events keep `variant_id`. The app is not in production, so the change is made in one pass with no compatibility layer and no old routes kept.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Know exactly what is done and what is left (Priority: P1)

The owner opens the closure report and sees every unchecked 006 task and requirement classified as completed, remaining or unverified, each with file evidence, before any new work starts. At the end, the same report shows each item either delivered and tested, or documented with reason, owner and follow-up.

**Why this priority**: Without an honest starting inventory, work gets duplicated or skipped. Jira acceptance criterion 1 depends on it.

**Independent Test**: Compare the report with the code on main for a sample of tasks; confirm each classification matches the evidence and that no 006 requirement is missing from the report.

**Acceptance Scenarios**:

1. **Given** the 48 unchecked 006 tasks, **When** the report is produced, **Then** each has a status (completed, remaining, unverified) and file evidence, and tasks found already done are marked done instead of redone.
2. **Given** a 006 requirement with no implementation, **When** the feature closes, **Then** it is either implemented and tested or listed with reason, owner and follow-up.
3. **Given** the ten indicator cards and the v2 contracts from PR 19, **When** the feature closes, **Then** they are unchanged in definition and values, and their existing tests still pass.

---

### User Story 2 - Filter by date range and share the view by link (Priority: P1)

An executive filters the dashboard by date range, supplier, category and warehouse, copies the address, and a colleague who opens it sees the same filtered view. Options for supplier, category and warehouse come from current data, and each person sees only what their role allows.

**Why this priority**: Filtering is the first remaining scope item and the basis for every chart, drill-down and export.

**Independent Test**: With synthetic data covering several suppliers, categories and warehouses, apply each filter alone and combined, reload the page and open the link in a second session with another role; confirm identical figures where allowed and no leaked data where not.

**Acceptance Scenarios**:

1. **Given** a selected date range, **When** the page is reloaded or the link is opened elsewhere, **Then** the same filters are applied and every card, chart, drill-down and export reflects them.
2. **Given** new suppliers, categories or warehouses in the data, **When** the filter options load, **Then** they appear without any code change, and removed ones disappear.
3. **Given** a link with an invalid or tampered filter value, **When** it is opened, **Then** the value is ignored with a visible Spanish notice and the rest of the view still loads.
4. **Given** a viewer role, **When** the dashboard loads, **Then** cost and capital figures are not requested, shown or exported, even if the link asks for them.
5. **Given** a filter combination with no matches, **When** applied, **Then** an explanatory empty state offers a clear way to remove the filters.

---

### User Story 3 - Drill from any figure down to a SKU detail page (Priority: P1)

From a card or chart, an executive opens the list of SKUs behind the figure, then opens one SKU and sees its stock, coverage, demand, forecast, supplier and expiry lots on a page with its own address. The page title and every row use the SKU, never an internal id.

**Why this priority**: Jira acceptance criterion 2 requires drill-downs to reach SKU detail; a number nobody can trace to a product is not actionable.

**Independent Test**: Open each drill-down type from its card or chart, check the total reconciles with the figure, open a SKU, then reload and share that SKU page address.

**Acceptance Scenarios**:

1. **Given** any indicator or chart, **When** the user opens its drill-down, **Then** the listed SKUs are ordered by contribution (ties by SKU), and their total equals the figure shown.
2. **Given** the drill-down kinds still missing from PR 19 (demand, forecast, capital, budget and expiry band), **When** each is opened, **Then** it works like the existing kinds, with paging, sorting and keyboard use.
3. **Given** a SKU in a list, **When** the user opens it, **Then** a page with its own address shows stock, coverage, demand, forecast, supplier and expiry lots, titled by the SKU.
4. **Given** a role without permission to see costs, **When** the SKU page opens, **Then** cost fields are absent from what is received, not just hidden.
5. **Given** an unknown or out-of-scope SKU in the address, **When** it is opened, **Then** a Spanish not-found state is shown, with no data from other products.

---

### User Story 4 - Real analytical charts with a table for each (Priority: P2)

An executive sees charts for demand versus forecast, inventory trend, stockout and expiry exposure, ABC/XYZ classification and forecast accuracy (where the data supports it). Each chart is built from real figures, has a table with the same numbers, and shows clear loading, empty and error states. Clicking a chart element opens its drill-down.

**Why this priority**: Visual trends are what executives read first, but cards and drill-down already give value on their own.

**Independent Test**: With the synthetic reference dataset, confirm each chart's values equal independently computed figures, the table matches the chart, and each of the three states can be forced and read.

**Acceptance Scenarios**:

1. **Given** the reference dataset, **When** the dashboard loads, **Then** at least five charts show values that match independently computed figures, and none uses static or placeholder numbers.
2. **Given** a chart, **When** its table is opened, **Then** it holds exactly the same rows as the chart, and keyboard and screen-reader users can reach the chart, its legend and the table toggle.
3. **Given** a chart whose data does not exist yet (for example forecast accuracy before enough history), **When** the dashboard loads, **Then** it shows a Spanish note saying why, never an empty or zero-filled chart.
4. **Given** active filters, **When** they change, **Then** every chart updates and the ABC/XYZ chart honours them.
5. **Given** the data history that exists, **When** a date range goes beyond it, **Then** the available range is stated rather than padded.

---

### User Story 5 - Export what is on screen, safely (Priority: P2)

A buyer, approver or admin exports a card set, a chart table or a drill-down to CSV or Excel with the active filters and a header showing filters, period, freshness and generation time. The file never lets a spreadsheet run a formula from the data and never contains what the user's role may not see.

**Why this priority**: Executives share numbers outside the app; it is secondary to seeing them.

**Independent Test**: Export each kind with filters on, compare the file with the screen, open it with hostile cell values, and attempt it as a viewer.

**Acceptance Scenarios**:

1. **Given** an export request, **When** the file is produced, **Then** its rows and totals equal the screen, it carries the filter header and Spanish number formats, and it contains no free-text notes, tax identifiers or internal ids.
2. **Given** a cell value starting with `=`, `+`, `-`, `@`, a tab or a carriage return, **When** it is exported, **Then** it is neutralised so no spreadsheet program treats it as a formula.
3. **Given** a viewer, **When** they try to export, **Then** it is refused with a stable reason and the refusal is audited; allowed exports are audited too (who, what, when, filters).
4. **Given** a result larger than the export limit, **When** requested, **Then** it is refused with a clear "too large, narrow the filters" message, never cut off silently.
5. **Given** a format that cannot be offered for some data, **When** the user looks for it, **Then** only the supported formats are shown.

---

### User Story 6 - Trust the data: freshness, newer-data notice and failures (Priority: P2)

A prominent banner tells the user how fresh the data is and when it is stale. Each card shows its origin and age; a failing source shows an error with a retry, never a zero; and a notice offers newer data without changing the numbers under the user's eyes. Records left out of a figure are counted and linked to the review list.

**Why this priority**: Executives act on these numbers; hiding stale or partial data would be worse than showing nothing.

**Independent Test**: Simulate a stale source, a failing source and an empty source; confirm affected figures flag it, the rest stay correct, and nothing silently shows zero.

**Acceptance Scenarios**:

1. **Given** data older than the freshness limit, **When** the dashboard loads, **Then** a prominent banner says so and every affected card shows its age.
2. **Given** newer data becomes available while the page is open, **When** it is detected, **Then** a notice offers a refresh and the displayed values change only after the user accepts.
3. **Given** one failing source, **When** the dashboard loads, **Then** only the affected cards show an error with a retry, and the others stay correct.
4. **Given** records excluded for being malformed or ambiguous, **When** a figure is shown, **Then** the count is visible and links to the review list.
5. **Given** figures loaded from local exports, **When** they appear, **Then** they are labelled and never added to ERP-collected figures.

---

### User Story 7 - Proven on the live stack, performance, cost and gates (Priority: P2)

The owner has evidence that the dashboard works end to end on the real stack with synthetic data: a browser journey, a speed check, an accessibility scan, a cost note, the quickstart walk-through and the full gate runner, with screenshots and results ready for review in one pull request.

**Why this priority**: Jira acceptance criteria 4 and 5 demand evidence, but it builds on Stories 2 to 6.

**Independent Test**: Start the stack with the synthetic reference data, run the live journey and the gates, and confirm each result is recorded and every failure is fixed or blocked with an owner.

**Acceptance Scenarios**:

1. **Given** the live stack seeded with synthetic data, **When** the browser journey runs, **Then** it covers filters, cards, charts, drill-down to a SKU, export and the stale and failure states, and passes.
2. **Given** the reference dataset, **When** the speed check runs, **Then** the first meaningful view and a filter change meet the targets, and the result is recorded.
3. **Given** the quickstart, **When** every scenario is run, **Then** each is recorded, together with a keyboard-only pass over every chart, drill-down and export and Spanish screenshots.
4. **Given** the full gate runner (contracts, isolation, integration, end to end, security, cost), **When** it runs, **Then** every result is recorded; any failure is fixed or blocked with an owner, coordinated with Agent 00.
5. **Given** the feature is complete, **When** the pull request is prepared, **Then** it links MMI-3, MMI-1, PR 19 and MMI-11, includes screenshots and test results, and states the cost impact.

### Edge Cases

- A 006 task is marked unchecked but its code already exists: it is verified, ticked with evidence, and not rebuilt.
- A filter link names a supplier, category or warehouse that no longer exists: the value is ignored with a visible notice; nothing is guessed.
- Two filters conflict (a supplier that does not sell in the chosen category): the empty state explains it instead of showing zeros.
- A date range crosses a Madrid daylight-saving change: days, snapshots and trend buckets stay correct (23- and 25-hour days).
- A SKU has no demand history, negative stock or an estimated cost: the SKU page and drill-down show an explicit state and the figure's definition, not a blank.
- An export is requested while newer data is pending: it uses the data on screen and says so in its header.
- A role loses cost access while a page is open: the next request is refused and cost figures disappear, with no stale copy left on screen.
- Two people export the same view at once, or one double-clicks: each request is independent, audited once, and neither corrupts the other.
- A chart has a single data point or a very long series: it renders readably and its table stays complete.

## Requirements *(mandatory)*

### Functional Requirements

**Verification and closure**

- **FR-001**: Before any build work, the feature MUST classify every unchecked 006 task and requirement as completed, remaining or unverified with file evidence, and MUST build only the verified gaps.
- **FR-002**: Every remaining 006 requirement MUST end either implemented and tested, or documented with reason, owner and follow-up in the closure report.
- **FR-003**: The ten indicator cards, their definitions and the v2 contracts MUST stay unchanged; changes to shared contracts MUST go through Agent 00.

**Filters and sharing**

- **FR-004**: The dashboard MUST support filtering by date range, supplier, category and warehouse, applied consistently to cards, charts, drill-downs and exports (006 FR-006).
- **FR-005**: The active filters MUST be stored in the page address, so a reload or a shared link restores the same view; invalid values MUST be ignored with a visible Spanish notice.
- **FR-006**: Filter options MUST come from current data, and every request MUST respect the user's role, so a viewer never receives cost or capital figures.

**Drill-down and SKU detail**

- **FR-007**: Every indicator and chart MUST open a drill-down whose total reconciles with the figure; the missing kinds (demand, forecast, capital, budget and expiry band) MUST be added, sortable, paginated and keyboard accessible.
- **FR-008a**: No gateway route, payload or page address used by the browser MUST carry `variant_id`; products are identified by SKU only, and the gateway resolves the SKU to `variant_id` through the synced catalogue for calls to services. Service-to-service APIs and events keep `variant_id`. No compatibility routes are kept (the app is not in production).
- **FR-008**: A SKU detail page with its own address MUST show stock, coverage, demand, forecast, supplier and expiry lots, identified by SKU only; cost fields MUST be sent only to roles allowed to see costs.

**Charts**

- **FR-009**: The dashboard MUST show real, filter-aware charts for demand versus forecast, inventory trend, stockout and expiry exposure, ABC/XYZ classification and forecast accuracy where the data supports it, alongside the existing trend and ABC/XYZ charts.
- **FR-010**: Every chart MUST have an equivalent table, a title, a text summary, non-colour cues and defined loading, empty and error states; unsupported views MUST say why.

**Export**

- **FR-011**: Buyers, approvers and admins MUST be able to export cards, chart tables and drill-downs to CSV or Excel, with a header of filters, period, freshness and generation time, in es-ES number formats; viewers MUST be refused.
- **FR-012**: Exports MUST neutralise spreadsheet-formula injection, MUST exclude free-text notes, tax identifiers and internal ids, MUST reproduce the on-screen rows and totals, and MUST be refused above a stated size limit rather than truncated.
- **FR-013**: Every export attempt, allowed or refused, MUST be audited with who, what, when and filters, and without secrets or personal data.

**Freshness and trust**

- **FR-014**: The system MUST expose data freshness and show a prominent banner when data is stale, with each card showing its origin and age.
- **FR-015**: A notice MUST offer newer data when it appears and MUST NOT change displayed values until the user accepts.
- **FR-016**: A failing or empty source MUST show an explicit state with a retry, never a silent zero; excluded or quarantined records MUST be counted and linked to the review list; local-load figures MUST be labelled and never mixed with ERP figures.

**Evidence and operations**

- **FR-017**: The feature MUST include a live-stack browser journey, a performance check with its record, an accessibility scan of the new elements, a cost note and a run of every quickstart scenario, all using synthetic data only.
- **FR-018**: The full gate runner MUST be run, with each result recorded and any failure fixed or blocked with an owner, in coordination with Agent 00.
- **FR-019**: The dashboard MUST stay read-only: no ERP request, no purchasing state change; tests MUST prove it.
- **FR-020**: All user-facing text MUST be Spanish (es-ES) from the translation catalogue, with EUR and Spanish date and number formats; no literal numbers may be rendered as data.
- **FR-021**: Money MUST be exact decimal; timestamps UTC with the original value preserved; products shown by SKU; the business logic MUST stay in the domain services, not in the gateway.
- **FR-022**: The feature MUST add no always-on service and stay within the shared monthly cost budget; operational signals MUST NOT log notes or secrets.
- **FR-023**: One pull request MUST present the work, linking MMI-3, MMI-1, PR 19 and MMI-11, with screenshots and test results.

### Key Entities

- **Dashboard filter set**: date range, supplier, category and warehouse chosen by a user, carried in the page address and applied to every figure, chart, drill-down and export.
- **Drill-down list**: the SKUs behind a figure, with a contribution per SKU, a kind (demand, forecast, capital, budget, expiry band and the existing ones) and a total that equals the figure.
- **SKU detail**: one product's stock, coverage, demand, forecast, supplier and expiry lots, with costs only for allowed roles.
- **Chart series**: the real figures behind one chart plus its table, its available history range and its supported state.
- **Export file**: a CSV or Excel file of one view, with a filter header, safe cell values and an audit entry.
- **Freshness status**: age and origin of each data source, the stale limit and the count of excluded records.
- **Closure report**: the classification of every unchecked 006 task and requirement, with evidence, final status and follow-ups.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % of the unchecked 006 tasks and requirements appear in the closure report with a status and file evidence, and each ends delivered and tested or documented with reason, owner and follow-up.
- **SC-002**: A shared filter link reproduces the same figures for the same role in 100 % of tested combinations, and 0 cost or capital figures reach a viewer.
- **SC-003**: A buyer can go from the dashboard to a SKU detail page for any indicator in three interactions or fewer, and drill-down totals reconcile with the figure in 100 % of tested cases.
- **SC-004**: At least five analytical charts render from live data, 100 % of their values match independently computed figures on the reference dataset, and each has a matching table.
- **SC-005**: 100 % of exports reproduce the on-screen rows and totals, 0 contain prohibited fields or active formulas in the hostile-input tests, and 100 % of attempts, allowed or refused, are audited.
- **SC-006**: In failure drills (stale, failed, empty source), 100 % of affected figures show an explicit state and 0 % silently show zero.
- **SC-007**: The first meaningful view appears within 2 seconds and a filter change updates every figure within 2 seconds on the reference dataset, with the measurement recorded.
- **SC-008**: Every chart, drill-down and export can be completed with the keyboard alone, and the automated accessibility scan reports no serious violations on the new elements.
- **SC-009**: The live-stack journey and all six gates (contracts, isolation, integration, end to end, security, cost) have recorded results, and every failure is fixed or blocked with a named owner.
- **SC-010**: Added running cost stays within the shared monthly budget with no new always-on service.

## Assumptions

- Feature 006 on main (PR 19) is the starting point and its ten indicators and v2 contracts are correct; gaps are found by verification, not assumed.
- The synthetic reference dataset in `packages/testing` and the local compose stack are enough for the live journey; no real data and no Azure credentials are used.
- Roles, MFA and the audit trail come from the administration feature (010); who may see costs follows the existing role rules.
- Forecast accuracy, expiry and similar views depend on history that may be short; a view that the data cannot support yet is shown with a reason, not faked.
- Excel and CSV remain the only export formats.
- If supplier commercial management (PR 17, MMI-6) lands on main first, shared web files are merged again and conflicts resolved before the pull request.
- Shared gates and contract changes are coordinated with Agent 00 (MMI-2); this feature does not edit files owned by other agents.
