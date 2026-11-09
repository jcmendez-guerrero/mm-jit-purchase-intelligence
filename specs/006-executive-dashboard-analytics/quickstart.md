# Quickstart: validating the Executive Dashboard

Synthetic data only. Never point these steps at a real Siweb host or load real exports. Commands are the repository's existing ones; exact script names are confirmed in the first task.

## Prerequisites

- Local stack running in the local environment with the synthetic seed from `packages/testing` (the same one the other features use).
- Web app dependencies installed and Playwright browsers available.
- Signed in with the local development issuer as a buyer (and later as a viewer).

## Scenario 1 - Cards match the data (US1, SC-001)

1. Load the reference synthetic dataset whose totals are documented with the fixture.
2. Open the dashboard. Confirm the ten indicator families show the documented values in es-ES format, each with period, refresh time and origin.
3. Empty one source (for example forecasts) and reload: only the dependent cards show "sin datos".
4. Expected: values equal the fixture totals; no card shows a placeholder or a silent zero.

### Capital and budget checks (FR-025, FR-026)

1. Open the capital tied up card: its value equals stock at cost plus confirmed unreceived orders, and the two parts are listed.
2. Choose a range spanning a week with a weekly cap, a week covered only by a monthly cap and a week with none: the budget card lists each cap used with its period and compares it with the spend of those weeks; a range with no cap shows "sin presupuesto" and still shows the spend.

## Scenario 2 - Filters (US2, SC-003)

1. Apply warehouse, then supplier, then category, then a date range; then all together.
2. Expected: every card, chart, drill-down and export changes consistently; chips show each filter; "limpiar" restores totals; copying the address into a new session reproduces the view; a filter combination with no matches shows the empty state.

## Scenario 3 - Drill-down reconciles (US3, SC-002)

1. Click the stockout-risk card, the expiry card and a chart bar.
2. Expected: rows are identified by SKU (no `#id`), the total of rows equals the card value, pagination and sorting work with the keyboard, opening a SKU shows its detail.

## Scenario 4 - Charts and tables (US4, SC-005)

1. Confirm at least five distinct charts render from live data.
2. Switch each to its table view and compare figures; run the accessibility scan.
3. Expected: same numbers in chart and table, meaningful title and summary, no colour-only status, no serious axe violations.

## Scenario 5 - Export (US5, SC-006)

1. Export cards, a chart table and a drill-down with filters active.
2. Expected: CSV opens correctly in a Spanish-locale spreadsheet (semicolons, decimal comma), contains the same rows and totals, a header with filters/period/freshness/generation time, and no notes, tax ids or internal ids. As a viewer the action is unavailable; the attempt is audited.

## Scenario 6 - Trust and failure drills (US6, SC-007)

1. Make one source stale, then make one source fail, then load data through the local loader.
2. Expected: stale banner and per-card age; only dependent cards show an error with retry; local-load figures are labelled and not combined with ERP figures; excluded records are counted and link to the review list.

## Automated runs

| Check | Where |
|-------|-------|
| Figures, filters, drill-down reconciliation | inventory-service pytest, PostgreSQL integration |
| Role and export refusals, abuse inputs | inventory-service and BFF pytest |
| Orchestration and downstream failures | BFF pytest |
| Contract validation | `packages/contracts` tests (v2 schema, v1 unchanged) |
| States and formatting | web Vitest and mocked Playwright specs |
| API-backed journey, export, axe | live-stack Playwright project |
| Performance (2 s targets) | existing dashboard perf specs on the reference dataset |
| Strings and colours baselines | existing hard-coded strings/colours checks (must not grow) |

Evidence for the pull request: Spanish screenshots of each scenario, test output, audit table from [research.md](research.md), and the cost note (no new always-on resource).
