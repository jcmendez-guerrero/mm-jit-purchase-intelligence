# Quickstart: Validate the Keyboard Edit Fix

Synthetic fixtures only; the terms API is mocked by the check. Never point this at a real Siweb host.

## Prerequisites

```bash
cd apps/web
npm ci
npx playwright install chromium
```

## 1. Reproduce (before the fix)

Temporarily change `test.fixme(` to `test(` on the keyboard check and run it:

```bash
npx playwright test tests/e2e/a11y-all-routes.spec.ts -g "reference task 3" --trace on
```

Expected before the fix: fails with saved `lead_time_days` equal to `3`. Open the trace and note which element had focus when `7` was typed (see [research.md](research.md), hypotheses H1–H4).

## 2. Validate the fix

```bash
npx playwright test tests/e2e/a11y-all-routes.spec.ts -g "reference task 3"
```

Expected: passes, with no `fixme` left on the check and a second case for a money term (minimum order value) also passing.

## 3. Stability (SC-001)

```bash
npx playwright test tests/e2e/a11y-all-routes.spec.ts -g "reference task 3" --repeat-each=20
```

Expected: 20 of 20 pass.

## 4. No regression

```bash
npm test
npx playwright test
```

Expected: unit tests and the full e2e suite pass; no check is skipped because of MMI-12.

## 5. Gate

From `scripts/`:

```bash
python -m gates run
```

Expected: the `e2e` gate no longer reports `fail` because of this check.

## 6. Manual check (optional)

In the local app, sign in as buyer, open Proveedores, open a supplier, change "Plazo de entrega (días)" with the keyboard only, add a reason, save with Enter, and confirm the new version shows the typed value.

## Results (2026-11-16)

- Reproduction (T002–T003): the check passed on this branch because `e0e8b18` already locks the form until the terms load; with the lock and the test's load wait removed it saved `3` in 1 of 10 runs. Details in [research.md](research.md).
- Stability (T012, SC-001): `--repeat-each=20` on the keyboard check, 20 of 20 passed. The four supplier-terms cases (keyboard lead time, keyboard money term, mouse money term, delayed load) ran 4 × 80 times with 7 workers: 320 of 320 passed after the supplier-button wait was added (before it, 2–5 of 80 failed per run).
- Unit tests: `npm test`, 791 passed (57 files).
- Full suites (T013): full Playwright run 273 passed, 14 skipped (env-gated, none for this check). `python -m gates run --gate e2e` shows no failure; it reports `not_run` only because its last step needs the live compose stack (`PLAYWRIGHT_BASE_URL`), which was not started here.
- Not done: SC-003 was not timed by a person, and the live-stack Playwright step did not run.
