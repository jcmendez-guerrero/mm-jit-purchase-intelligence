# PR: Business policy configuration: every rule reaches the calculation, safely and auditably (feature 011, MMI-8)

Jira: [MMI-8](https://mundomascotix.atlassian.net/browse/MMI-8) (epic MMI-1). Spec page: MMI 003 / Agent 06, Business Policy Configuration. Spec: `specs/011-business-policy-configuration/`. Contract changes for Agent 00: `specs/011-business-policy-configuration/agent-00-contract-note.md`.

## Summary

Completion and verification of the policy console from feature 002. A first audit found gaps between what the console lets a person change and what happens next; this PR closes them and proves the acceptance criteria with tests.

- **Every rule changes the next calculation**, shown by a test per rule. One did not: the **replenishment cadence** was stored, audited and shown but no calculation read it; it is now the product's review period.
- **Safe edits**: revisions on budget caps, exclusions, censoring rules and removal of an override (stale or simultaneous saves answer with a conflict, never an overwrite or a server error); fresh second factor for budget caps, global policy values, forecast parameters and censoring rules; viewer and approver refused and recorded.
- **People see SKUs, never ERP ids**: product policies, exclusions, criticality, stocking, overrides, previews and the audit view.
- **Budgets that bind**: when a cap binds, the weekly proposal defers the least urgent non-critical needed lines, lists them with the cap that bound, never defers a critical product or a line the buyer fixed, and shows the excess for a person to decide. Supplier weekly caps now apply. Category caps are refused (`budget_scope_unsupported`) because proposals carry no category.
- **Censoring rules by scope** (global, segment, product), most specific first; **removal of an override** as a new revision.
- **Audit**: admin view with who, what, before and after, scope and outcome, refusals included, filtered by what changed, outcome and dates (Madrid days, applied in each service before its row limit; a notice shows when a source hit its limit), 50 rows a page; no ERP ids, no typed text.
- **Explanations** cite the scope and revision behind every rule; the proposal screen shows the budget effect and the rules applied; previews say which forecast run they used.
- Also fixed: exclusion reasons were written to the audit as typed text (now a pick list code); older typed reasons are shown as "other" to non-admins.

## Data, security, cost, contract impact

- **Data**: synthetic fixtures only; no real export, SKU, supplier or price.
- **Security**: fresh MFA as above; refusals recorded; admin-only audit; no ERP id or typed text in the audit view; no request to the ERP from any policy action.
- **Cost**: no new service or always-on resource.
- **Migrations** (all additive, reversible): procurement 0013 (unique budget-cap revision; stops on a database that already holds duplicates), inventory 0008 (exclusion detail), 0009 (censoring scope; existing rows stay global), forecast 0006 (rule versions on runs).
- **Contract**: renamed gateway routes (criticality, stocking, override recommendation by SKU; request bodies use `sku`), new draft endpoints, `demand_rule.v1` extended additively; the matrix entries are `draft` and need Agent 00 review.

## Test evidence (synthetic data, SQLite stand-in)

| Suite | Result |
|-------|--------|
| procurement | 897 passed |
| gateway | 246 passed |
| forecast | 223 passed, 3 skipped |
| contracts | 237 passed, 5 skipped |
| inventory | 261 passed, 1 skipped, with `test_dashboard_filter_matrix` and `test_dashboard_indicators` deselected: they compare against today's date and fail the same way without this branch's changes |
| web (policies, proposals, i18n) | 196 passed; `tsc` and eslint clean on the changed files |
| Playwright (policies, safety stock, proposals export, roles) | 16 passed |
| `python -m gates run` | contracts, isolation, security, cost passed before the last audit change; not rerun after it (the e2e gate hangs without Docker) |

## Known limitations

- The test suites run on a SQLite stand-in. The four migrations were also run on a local PostgreSQL 18 (up, down to the revision before this feature, up again): procurement 0013, inventory 0008 and 0009, forecast 0006 all pass. On PostgreSQL, 0013's unique index refuses a second global cap with the same revision, the upgrade stops cleanly on a database that holds duplicates (stays at 0012, data untouched), and a real two-connection race on a budget-cap save ends with one saved and one `PolicyConflict`. The service concurrency tests themselves were not rerun on PostgreSQL.
- No browser journey runs against a real stack (T047): the Playwright specs mock the backend, so persistence is covered by the service tests, not the browser.
- The `e2e` gate runs the docker-compose pipeline test, which needs Docker and could not run here. The full web unit run also has 24 failures in `ui/DataTable`, `ui/ThemeToggle`, `ui/forms`, `ui/preferences` (`localStorage` and `AbortSignal` under Node 26 and jsdom) in files this branch does not touch.
- Not built: re-proposal after a save and the failure notice of a re-forecast (T018), previews for budget, criticality, exclusion, censoring and parameter saves (FR-006 narrowed to policy values by decision), removal of a scoped censoring rule, applying budget caps by category, extra abuse cases (T029), preview timing (T049), accessibility check of the audit tab (T050), new DTO schemas for the new endpoints (T064).
- A true simultaneous pair of censoring-rule saves is not caught by the database (needs a uniqueness migration); policy sets, budget caps and exclusion toggles are.
- The dashboard still calls `GET /api/segments/{variant_id}/history` with an id taken from its own rows; it is never displayed.
