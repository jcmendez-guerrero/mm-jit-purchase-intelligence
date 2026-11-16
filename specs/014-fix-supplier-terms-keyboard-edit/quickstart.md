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
