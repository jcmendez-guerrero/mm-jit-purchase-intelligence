# Quickstart: validating the Dashboard completion

Synthetic data only. Never point these steps at a real Siweb host or load real exports. This guide covers what feature 014 adds; the card checks (006 Scenario 1) are re-run from `specs/006-executive-dashboard-analytics/quickstart.md`.

## Prerequisites

- Docker available, `infra/compose.yaml` stack started with the seed loader in `scripts/live-stack/` and the fixture `packages/testing/fixtures/dashboard_reference/` (no Azure credentials).
- Web dependencies installed and Playwright browsers available.
- Signed in with the local development issuer as a buyer, then as a viewer.

## Scenario 1 - Closure report (US1, SC-001)

1. Open `specs/014-dashboard-analytics-completion/closure-report.md`.
2. Expected: every unchecked 006 task and requirement has a start status with file evidence and a final status; deferred items name reason, owner and follow-up; the 006 `tasks.md` boxes match.

## Scenario 2 - Filters and shared link (US2, SC-002)

1. Apply date range, supplier, category and warehouse; copy the address; open it in a second session as buyer and as viewer.
2. Edit the address with an invalid supplier and an out-of-range date.
3. Expected: same figures for the buyer; viewer receives no cost or capital fields; invalid values are ignored with a Spanish notice; a no-match combination shows the empty state with a clear action.

## Scenario 3 - Drill-down to SKU page (US3, SC-003)

1. From each card and chart, open the drill-down (including demand, forecast, capital, budget, expiry band); sort and page by keyboard.
2. Open a SKU; reload; open an unknown SKU address.
3. Expected: totals equal the figure, rows show SKUs only, the SKU page has its own address and title, an unknown SKU shows the not-found state, a viewer response has no cost fields.

## Scenario 4 - Charts (US4, SC-004, SC-008)

1. Confirm at least five charts render from live data; toggle each to its table; compare numbers with the reference totals.
2. Force loading, empty and error states; use a date range beyond the history; run the axe scan on the new elements.
3. Expected: chart and table equal; unsupported views say why; the history range is stated; no serious axe violations; everything reachable by keyboard.

## Scenario 5 - Export (US5, SC-005)

1. Export cards, a chart table and a drill-down with filters active; open in a Spanish-locale spreadsheet.
2. Run the hostile-cell test data (`=`, `+`, `-`, `@`, tab, carriage return); export above the size limit; try as a viewer.
3. Expected: rows and totals equal the screen; header with filters, period, freshness and generation time; hostile cells stay text; refusals are clear and audited; allowed exports audited too.

## Scenario 6 - Trust and failure drills (US6, SC-006)

1. Make one source stale, one fail and one empty; load figures through the local loader; publish newer data while the page is open.
2. Expected: stale banner and per-card age; only dependent cards show an error with retry; no silent zero; local-load labelled and not mixed; the notice offers newer data and values change only after acceptance; excluded records counted and linked to the review list.

## Scenario 7 - Evidence and gates (US7, SC-007, SC-009, SC-010)

| Check | How |
|-------|-----|
| Live-stack journey | `apps/web` Playwright live project (`dashboard-live.spec.ts`) against the seeded stack |
| Performance | `dashboard-perf.spec.ts` and `services/api-bff/tests/perf`; record first meaningful view and filter change |
| Keyboard-only pass and Spanish screenshots | manual, recorded in the closure report |
| Gates | `python -m gates run` from `scripts/` with `MMI_GATES_DATABASE=1` and, with Docker, `MMI_GATES_LIVE_STACK=1`; record all six results |
| Cost | confirm no new container, job or schedule; note in the PR cost section |

Evidence for the pull request: Spanish screenshots of each scenario, test and gate output, the closure report and the cost note; the PR links MMI-3, MMI-1, PR 19 and MMI-11.
