# Verification (feature 012)

Run on 2026-11-15 from `apps/web` and `scripts`, synthetic data only, no Siweb host contacted.

| Check | Command | Result |
|---|---|---|
| Unit tests | `npx vitest run` | 52 files, 745 tests pass (baseline was 46 files, 552 tests) |
| Lint | `npm run lint` | clean |
| Types | `npx tsc --noEmit` | clean |
| Build and bundle budget | `npm run build && npm run check:bundle` | JS gzip total 273.2 kB (budget 350), charts chunk 154.6 kB (budget 160) |
| Browser tests, whole suite | `npx playwright test` | 268 pass, 14 skipped (evidence capture and earlier skips), 0 failed |
| Accessibility, every route | `npx playwright test a11y-all-routes` | 27 route cases (9 routes × 1280, 768, 375 px), each in light and dark: no serious or critical violations |
| No horizontal scroll at 375 px | `npx playwright test responsive.spec` | 9 routes pass; palette focus check passes |
| Heading focus after a screen change | `npx playwright test navigation.spec` | 15 pass |
| Repository gates | `python -m gates run` from `scripts/`, Python 3.12 venv with the CI test dependencies and the service packages | `contracts` pass, `isolation` pass, `security` pass (8 commands), `cost` pass. `e2e`: the pipeline tests are skipped without a stack and the mocked browser suite passes (268); the live-stack journey was **not run** (needs `MMI_GATES_LIVE_STACK=1`, which builds the compose images). `integration` not run (no PRs in the plan). One of four gate runs failed in the mocked browser suite; two direct runs of the same command passed 268 of 268. |

## Exports (T057, read from the service code; nothing was exported)

The web app builds no export itself: every file is produced by the server and handed to the browser.

| Export | Where | Headers | Numbers and dates | Verdict |
|---|---|---|---|---|
| Proposal CSV | `services/procurement-service/src/proposals/export.py` | Spanish, from the es-ES catalogue | `;` delimiter, UTF-8 with BOM, comma decimals, `dd/mm/yyyy` | meets FR-008; covered by `test_export_locale.py` |
| Proposal Excel | same | Spanish | numeric cells with a euro number format | meets FR-008 |
| Audit CSV | `services/api-bff/src/routes/admin_audit.py` | **English field names** (`id, ts, actor, action, entity, entity_id, outcome, reason_code`) | **ISO timestamps**, `,` delimiter, `\n` line ends; the file is named `audit.csv` by the server and `auditoria.csv` by the browser | **does not meet FR-008**; a server change (Agent 00 and feature 010), requested in `agent-00-contract-note.md` |

The proposal exports also carry a column "Variante (ID Siweb)" next to the SKU. It looks intended for ERP hand-off, but project rule 5 says people see the SKU; recorded as a question for the owner.

## Known intermittent failures

`tests/e2e/a11y-all-routes.spec.ts` "reference task 3 by keyboard: edit one supplier term and save it" fails about 1 run in 6–15 under load (typing into the lead-time field is lost). It fails at the same rate without this feature's changes (measured: 1 of 15 on the unchanged `AppShell.tsx` and `PageHeader.tsx`), so it predates this feature. `suppliers.spec.ts` "a buyer edits the lead time, reloads" also fails about 1 run in 30 on the committed code (it fills the field before the terms finish loading). Both tests now wait for the saved terms to load before typing (test-only change in `a11y-all-routes.spec.ts` and `suppliers.spec.ts`): 100 of 100 repeated runs passed.

## Not verified

- The moderated usability check (SC-002) has not been run; see `usability.md`.
- The live-stack journey (`playwright.live.config.ts`) and the compose pipeline tests: they need the compose stack and were not started here.
- Real browsers other than Chromium; real screen readers; 200% zoom is covered by the existing `responsive.spec.ts` test (a 1280 px window shows 640 CSS px).
