# PR: Business policy configuration: SKU keys, revisions, MFA, audit and rule versions (feature 011, MMI-8)

Jira: [MMI-8](https://mundomascotix.atlassian.net/browse/MMI-8) (epic MMI-1). Spec page: MMI 003 / Agent 06, Business Policy Configuration. Spec: `specs/011-business-policy-configuration/`.

## Summary

Completion and verification of the policy console from feature 002. A first audit found five gaps and this PR closes the ones marked done in `tasks.md`:

1. Budget caps, exclusions and censoring rules had no stale-save protection: they now take the revision they edited (428 / 412), and budget caps have a unique revision index.
2. Policy and budget writes did not need a fresh second factor: budget caps and global-scope values now do.
3. Product scope was keyed and shown by the ERP variant id: people now use the SKU everywhere in the console; unknown or ambiguous SKUs are refused.
4. Forecast runs recorded parameter versions but not exclusion and censoring-rule versions: they now do; proposals also record budget-cap revisions.
5. No admin audit view, no default-versus-saved display: both added.

Also fixed: exclusion reasons were written to the audit as free text (project rule 7); they are now a pick list and the audit carries only the code.

## Data, security, cost, contract impact

- **Data**: synthetic fixtures only; no real export, SKU, supplier or price.
- **Security**: fresh MFA on budget caps and global policies; refusals recorded; admin-only audit; no free text in the audit; ERP ids removed from console responses; no request to the ERP from any policy action.
- **Cost**: no new service or always-on resource.
- **Contract**: see `agent-00-contract-note.md`. Migrations: procurement 0013, inventory 0008, forecast 0006. One renamed gateway route (criticality by SKU). Matrix entries are `draft` and need Agent 00 review.

## Test evidence

Python suites (SQLite stand-in): procurement 867, gateway 235, inventory 270 (1 skipped), forecast 218 (3 skipped), contracts 237 (5 skipped); all pass. `python -m gates run`: contracts, isolation, security, cost pass. Web: `tsc` and eslint clean on changed files; policy screens, policy model and i18n checks 176 passed; mocked Playwright `policies.spec.ts`, `safety-stock.spec.ts` 8 passed.

## Known limitations

- PostgreSQL integration tests were not run (SQLite stand-in only); migrations 0013, 0008 and 0006 were exercised on SQLite.
- No API-backed Playwright journey (T047) and no screenshots yet; the mocked browser specs do not prove persistence.
- The safety-stock override and always-stocked screens still take a typed variant id (FR-018 not met there).
- Not done: stockout-censoring and forecast-effect end-to-end tests (T036), explicit security-abuse additions (T029), preview timing test (T049), a11y check of the new tab (T050), fixtures (T007), JSON schemas for `policy_set` (only `demand_rule` was extended).
- The full web vitest run has 24 failures in `ui/DataTable`, `ui/ThemeToggle`, `ui/forms`, `ui/preferences` (`localStorage` and `AbortSignal` under Node 26 and jsdom), untouched by this PR and not compared against main.
- Migration 0013 stops on a database that already holds duplicate budget-cap revisions.
