# Quickstart: validating feature 012

Synthetic data only. The end-to-end suites run against the mock API; nothing contacts Siweb.

## Prerequisites

```bash
cd apps/web && npm ci && npx playwright install chromium
```

## 1. Fast checks (unit, text, formats, navigation matrix)

```bash
cd apps/web && npm run lint && npm run typecheck && npm test
```

Expect: the untranslated-text and error-code checks, the glossary check, the role-by-route matrix and the screen-state tests all pass (contract sections 1–4).

## 2. Accessibility and responsive matrix

```bash
cd apps/web && npx playwright test a11y-all-routes a11y-screens responsive touch-targets
```

Expect: no serious or critical violations at 1280, 768 and 375 px in light and dark (contract section 5).

## 3. Core journeys as the buyer

```bash
cd apps/web && npx playwright test journey-product journey-supplier navigation
```

Expect: dashboard → product (by SKU) → supplier/proposal → back; supplier search → terms → invalid save → corrected save → unsaved-change prompt → import with a rejected row listed. Keyboard only; all text Spanish.

## 4. Other roles

```bash
cd apps/web && npx playwright test roles dashboard-roles
```

Expect: viewer, approver and admin see only the screens and actions the matrix allows; forbidden and unknown addresses show the Spanish explanation screens.

## 5. Bundle budget

```bash
cd apps/web && npm run build && npm run check:bundle
```

Expect: within 350 KB gzip total and 160 KB for the charts chunk.

## 6. Evidence

Screenshots and the audit inventory are written to `specs/012-ux-navigation-localization/evidence/`. Review them against spec sections FR-001 and FR-018 before opening the pull request.
