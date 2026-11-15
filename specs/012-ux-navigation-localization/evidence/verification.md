# Verification (feature 012)

Run on 2026-11-15 from `apps/web` and `scripts`, synthetic data only, no Siweb host contacted.

| Check | Command | Result |
|---|---|---|
| Unit tests | `npx vitest run` | 51 files, 600 tests pass (baseline was 46 files, 552 tests) |
| Lint | `npm run lint` | clean |
| Types | `npx tsc --noEmit` | clean |
| Build and bundle budget | `npm run build && npm run check:bundle` | JS gzip total 272.7 kB (budget 350), charts chunk 154.6 kB (budget 160) |
| Browser tests, whole suite | `npx playwright test` | 244 pass, 14 skipped (evidence capture and earlier skips), 1 intermittent failure (see below) |
| Accessibility, every route | `npx playwright test a11y-all-routes` | 27 route cases (9 routes × 1280, 768, 375 px), each in light and dark: no serious or critical violations |
| No horizontal scroll at 375 px | `npx playwright test responsive.spec` | 9 routes pass; palette focus check passes |
| Heading focus after a screen change | `npx playwright test navigation.spec` | 15 pass |
| Repository gates | `python3 -m gates run` from `scripts/` | `contracts` pass, `isolation` pass, `integration` not run (no PRs in the plan), `e2e`, `security`, `cost` **not run here**: this machine's Python has no `pytest` |

## Known intermittent failure

`tests/e2e/a11y-all-routes.spec.ts` "reference task 3 by keyboard: edit one supplier term and save it" fails about 1 run in 6–15 under load (typing into the lead-time field is lost). It fails at the same rate without this feature's changes (measured: 1 of 15 on the unchanged `AppShell.tsx` and `PageHeader.tsx`), so it predates this feature. It is not fixed here.

## Not verified

- The moderated usability check (SC-002) has not been run; see `usability.md`.
- The three gates that need `pytest` were not run; the change touches no service code, contract or schema.
- Real browsers other than Chromium; real screen readers; 200% zoom was checked only through the no-horizontal-scroll test at 375 px.
