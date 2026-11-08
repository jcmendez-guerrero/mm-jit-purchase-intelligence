# Feature Specification: Executive Dashboard & Analytics

**Feature Branch**: `006-executive-dashboard-analytics`

**Created**: 2026-11-08

**Status**: Draft

**Input**: User description: "get the specification from https://mundomascotix.atlassian.net/browse/MMI-3" (Jira MMI-3, "AGENT 01 | Executive Dashboard & Analytics", epic MMI-1; scope and acceptance criteria from the linked Confluence page "MMI 003 — Agent 01 — Executive Dashboard & Analytics").

## Background

The buyer web app already has a dashboard screen with some charts and drill-down panels. This feature turns it into an executive dashboard in which every figure is a real, traceable number computed from the data the system holds, with filters, SKU-level drill-down, visible freshness, charts with an accessible table alternative, and exports. The first activity is an audit of what the current dashboard really does (complete, partial, broken, missing, unverified), with file and line evidence, so that working parts are reused rather than rebuilt. The audit result is a deliverable of this feature.

## Clarifications

### Session 2026-11-08

- Numbering: the Jira page names the folder `specs/003-agent-01/`, but numbers 001-004 are taken, so this feature uses the next free number (006), because 005 is being developed in parallel. The Jira issue and Confluence page remain the source of scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read the business at a glance (Priority: P1)

A buyer or manager opens the dashboard and sees headline indicator cards: stock value, coverage (days of stock), demand, forecast, stockout risk, expiry exposure, capital tied up, purchasing budget, and forecast quality (WAPE and bias). Each card shows a real value in Spanish number and EUR formats, the period it covers, and when its underlying data was last refreshed.

**Why this priority**: This is the core of the feature and the reason the dashboard exists. Without trustworthy cards, nothing else matters.

**Independent Test**: Load synthetic data with known totals, open the dashboard, and confirm every card equals the value computed independently from that data, shows its period and refresh time, and shows an explicit "no data" state when the source is empty.

**Acceptance Scenarios**:

1. **Given** synthetic inventory, movement and forecast data with known totals, **When** the buyer opens the dashboard, **Then** each of the ten indicators (stock value, coverage, demand, forecast, stockout risk, expiry exposure, capital tied up, purchasing budget, WAPE and bias as separate indicators) shows the value matching the known total, formatted in es-ES.
2. **Given** a card whose source data has never been loaded, **When** the dashboard renders, **Then** that card shows a clear "sin datos" state instead of zero or a placeholder number.
3. **Given** a card whose source data is older than the staleness threshold, **When** the dashboard renders, **Then** the card shows a stale warning with the age of the data, in text and not by colour alone.
4. **Given** no code path or fixture ships numbers in the interface, **When** the source data changes, **Then** the displayed values change accordingly without any interface change.

---

### User Story 2 - Filter by date, warehouse, supplier and category (Priority: P1)

The buyer narrows every card and chart by date range, warehouse, supplier and product category. Filters apply to the whole dashboard consistently, are visible as active chips, can be cleared in one action, and survive a page refresh and can be shared as a link.

**Why this priority**: Executives ask "for this supplier / this warehouse / this month". Unfiltered totals are of limited use.

**Independent Test**: With synthetic data covering two warehouses, three suppliers and several categories, apply each filter alone and in combination and confirm every card and chart equals the independently computed subset.

**Acceptance Scenarios**:

1. **Given** data across two warehouses, **When** the buyer selects one warehouse, **Then** all cards and charts recompute for that warehouse only.
2. **Given** several active filters, **When** the buyer clears them, **Then** the unfiltered totals return and no stale filtered values remain.
3. **Given** a filter combination that matches nothing, **When** the dashboard renders, **Then** an empty-result state explains that no data matches and offers to clear the filters.
4. **Given** active filters, **When** the buyer copies the page link and opens it in another session, **Then** the same filters are applied.

---

### User Story 3 - Drill down from a figure to the SKUs behind it (Priority: P1)

From any card or chart element the buyer opens a drill-down that lists the SKUs contributing to that figure, ordered by contribution, with the same filters applied. From a SKU the buyer sees its detail: stock, coverage, demand, forecast, supplier, expiry lots. The user always sees and supplies the SKU, never internal ERP identifiers.

**Why this priority**: A number nobody can trace to products is not actionable. Drill-down is an explicit acceptance criterion.

**Independent Test**: Click a stockout-risk card with synthetic data, confirm the listed SKUs are exactly those flagged, and that their count and total equal the card; open one SKU and confirm its detail matches the data.

**Acceptance Scenarios**:

1. **Given** a card showing N items at risk, **When** the buyer opens its drill-down, **Then** exactly N SKUs are listed and their sum equals the card's value.
2. **Given** an open drill-down, **When** the buyer changes a filter, **Then** the list updates to match.
3. **Given** a SKU in the list, **When** the buyer opens it, **Then** its detail shows only fields available to the buyer's role and identifies the product by SKU.
4. **Given** a very long list, **When** the buyer scrolls or pages, **Then** the list stays responsive and keyboard navigable.

---

### User Story 4 - Visualizations backed by live data, with a table alternative (Priority: P2)

The dashboard offers at least five distinct visualizations, each fed by live data (for example: stock value over time, coverage distribution, demand versus forecast, expiry exposure by period, capital by category or supplier, forecast error over time). Each chart has an equivalent accessible table, a text summary, and does not rely on colour alone.

**Why this priority**: Visual trends are what executives read first, but the cards and drill-down already give value on their own.

**Independent Test**: Open the dashboard with synthetic data and confirm five or more charts render values matching the data, each has a table view with the same numbers, and a screen reader announces a meaningful title and summary for each.

**Acceptance Scenarios**:

1. **Given** synthetic data, **When** the dashboard loads, **Then** at least five different visualizations render from live data.
2. **Given** any chart, **When** the buyer switches to its table view, **Then** the table contains the same figures as the chart.
3. **Given** a chart with no data for the current filters, **When** it renders, **Then** it shows an empty state rather than an empty axis.
4. **Given** a keyboard-only user, **When** they navigate the charts, **Then** every chart, legend entry, and data point detail is reachable without a mouse.

---

### User Story 5 - Export what is on screen (Priority: P2)

The buyer exports the current view (cards, or any chart/drill-down table) with the active filters, in a spreadsheet-friendly format, for use in meetings. The export states the filters, the period, the data freshness and the generation time (UTC and local).

**Why this priority**: Executives share numbers outside the app; it is explicitly in scope but secondary to seeing the numbers.

**Independent Test**: Apply filters, export a drill-down, and confirm the file contains exactly the rows shown, the filter summary and the timestamps, with Spanish headers and decimal formatting that opens correctly in a Spanish-locale spreadsheet.

**Acceptance Scenarios**:

1. **Given** an active filtered view, **When** the buyer exports, **Then** the file contains the same rows and totals as the screen plus a header with filters and freshness.
2. **Given** a role without export permission, **When** the buyer tries to export, **Then** the action is unavailable or refused and the attempt is not silent.
3. **Given** a large result, **When** the buyer exports, **Then** the export completes without freezing the screen and reports success or failure clearly.
4. **Given** any export, **When** it is created, **Then** it contains no free-text notes, no tax identifiers and no internal ERP identifiers.

---

### User Story 6 - Trust the data: freshness, provenance and errors (Priority: P2)

Every figure shows when its data was last refreshed and where it came from (ERP sync, local load, or computed forecast). If part of the data is missing, late or failed, the dashboard says so for that part and keeps showing the rest.

**Why this priority**: Executives will act on these numbers; hiding stale or partial data would be worse than showing nothing.

**Independent Test**: Simulate one stale source and one failing source; confirm the affected cards flag it, the unaffected cards stay correct, and no failure silently shows zero.

**Acceptance Scenarios**:

1. **Given** the latest sync is older than the threshold, **When** the dashboard loads, **Then** a visible banner and per-card timestamps show the age.
2. **Given** one data source fails, **When** the dashboard loads, **Then** only the dependent cards show an error state with a retry action.
3. **Given** data loaded locally from exports (not from the real ERP), **When** it is shown, **Then** it is labelled as such and never combined with ERP-collected data in the same figure.

---

### Edge Cases

- A new store/warehouse or supplier with no history: cards show "sin datos", not zero or errors.
- Products with no forecast, no cost, or no supplier: counted in an explicit "incomplete" bucket, not dropped silently.
- Negative or zero stock, returns, and adjustments are reflected consistently in stock value and coverage.
- Division by zero in coverage (no demand) shows "sin demanda", not infinity or an error.
- Expired and soon-to-expire lots are separated by clear time bands.
- Very large catalogues: dashboard first view stays within the response targets.
- Filters selecting a supplier that no longer exists, or a date range in the future.
- Concurrent data refresh while the user is looking at the dashboard: the user is told that newer data exists, and values do not change under their cursor.
- Roles without access to costs or capital: monetary cards are hidden, not blanked.
- Daylight-saving transitions at period boundaries.
- Records that cannot be classified go to the review list and are surfaced as a count on the dashboard.

## Requirements *(mandatory)*

### Functional Requirements

**Indicators**

- **FR-001**: The dashboard MUST show real indicator cards for stock value, coverage, demand, forecast, stockout risk, expiry exposure, capital tied up, purchasing budget, and forecast quality (WAPE and bias).
- **FR-002**: Every figure MUST be computed from stored data; the interface MUST NOT contain hard-coded or placeholder numbers, including in demo or error paths.
- **FR-003**: Each card MUST show its period, its refresh time and its data origin, and MUST show an explicit state for no data, stale data and error.
- **FR-004**: Monetary values MUST be exact decimals shown in EUR with es-ES formatting; dates and numbers MUST follow es-ES conventions.
- **FR-005**: Each indicator MUST have a documented definition (what is counted, period, exclusions) reachable from the card.

**Filters**

- **FR-006**: The dashboard MUST support filters for date range, warehouse, supplier and product category, applied consistently to all cards, charts, drill-downs and exports.
- **FR-007**: Active filters MUST be visible, individually removable, clearable at once, preserved on refresh and shareable by link.
- **FR-008**: A filter combination with no matches MUST show an explanatory empty state.

**Drill-down**

- **FR-009**: Every card and chart MUST open a drill-down listing the contributing SKUs, ordered by contribution (ties broken by SKU, ascending), whose total reconciles with the figure shown.
- **FR-010**: The SKU detail MUST show stock, coverage, demand, forecast, supplier and expiry lots, identifying products by SKU only.
- **FR-011**: Drill-down lists MUST be sortable, paginated or virtualised, and keyboard accessible.

**Visualizations**

- **FR-012**: The dashboard MUST provide at least five distinct visualizations backed by live data (not static content).
- **FR-013**: Every chart MUST have an equivalent table view, a title, a text summary and non-colour cues for status.
- **FR-014**: Charts MUST show defined loading, empty and error states.

**Export**

- **FR-015**: Users with permission MUST be able to export any card set, chart table or drill-down with the active filters, including a header with filters, period, freshness and generation time.
- **FR-016**: Exports MUST exclude free-text notes, tax identifiers and internal ERP identifiers, and MUST be audited (who, what, when, filters).

**Trust, security and operations**

- **FR-017**: Access MUST follow existing role rules; cost and capital figures MUST be limited to roles allowed to see costs.
- **FR-018**: Data from local exports MUST be labelled and never mixed with ERP-collected data in the same figure.
- **FR-019**: Records excluded from a figure because they are malformed or ambiguous MUST be counted and linked to the review list, never dropped silently.
- **FR-020**: The dashboard MUST NOT modify ERP data or any purchasing state; it is read-only.
- **FR-021**: All user-facing text MUST be in Spanish (es-ES) and come from the translation catalogue.
- **FR-022**: Timestamps MUST be stored in UTC with the original value preserved, and shown in the local time zone.
- **FR-023**: Analytics MUST NOT require always-on services beyond the existing platform and MUST stay within the shared monthly cost budget.
- **FR-024**: The feature MUST include a written audit of the current dashboard (complete, partial, broken, missing, unverified, with file and line evidence), and working parts MUST be reused.

### Key Entities

- **Indicator**: A named business figure (e.g., stock value) with a definition, value, unit, period, freshness and origin.
- **Filter Set**: The combination of date range, warehouse, supplier and category currently applied; shareable and exportable.
- **Contribution Row**: One SKU's share of an indicator for a filter set; the basis for drill-down and export.
- **SKU Detail**: Stock, coverage, demand, forecast, supplier and expiry lots for one product.
- **Visualization**: A chart with title, summary, data series, equivalent table and states.
- **Data Freshness**: The refresh time, origin and staleness status of each data source feeding a figure.
- **Export Record**: An audited export with who, what, when, filters and row count.
- **Audit Finding**: A status (complete / partial / broken / missing / unverified) with file and line evidence for one existing dashboard capability.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least five visualizations render from live data, and 100% of displayed indicator values match independently computed values on the synthetic reference dataset.
- **SC-002**: A buyer can go from the dashboard to the SKUs behind any indicator in two interactions or fewer, and drill-down totals reconcile with the indicator in 100% of tested cases.
- **SC-003**: The first meaningful view of the dashboard appears within 2 seconds, and a filter change updates every figure within 2 seconds, on the reference dataset.
- **SC-004**: Zero hard-coded figures (literal numbers rendered as data) and zero user-facing strings outside the translation catalogue in the dashboard, verified by automated checks.
- **SC-005**: Every chart is fully usable by keyboard and screen reader, with an equivalent table; the dashboard passes an automated accessibility scan with no serious violations, and a manual keyboard-only pass of every chart, drill-down and export is recorded.
- **SC-006**: Exports reproduce 100% of on-screen rows and totals and contain no prohibited fields in any tested case.
- **SC-007**: In failure drills (stale source, failed source, empty source), 100% of affected figures show an explicit state and 0% silently show zero.
- **SC-008**: The audit lists every existing dashboard capability with a status and evidence, and at least the working parts are reused rather than rewritten.
- **SC-009**: Added running cost stays within the shared monthly budget with no new always-on service.

## Assumptions

- The existing dashboard screens, drill-down panels and the analytics data already held by the system are the starting point; the audit decides what is reused, repaired or replaced.
- Data comes from the already-synced catalogue, stock, movements, forecasts, policies and scenarios; this feature does not add new ERP reads or writes.
- Staleness thresholds follow the values already used elsewhere in the app unless the audit shows otherwise.
- Forecast quality uses the project's existing definitions of WAPE and bias.
- Exports are spreadsheet-friendly files; a printable/PDF layout is out of scope for this version.
- Roles and permissions already exist; this feature adds no new roles.
- Shared API contracts with other parallel work are coordinated by the integration owner (Agent 00); this feature does not change another agent's owned files.
- Delivery is by a single reviewable change with tests, screenshots in Spanish and no production deployment or ERP write.
- Tests use synthetic data only; no real exports or identifiers are committed.
