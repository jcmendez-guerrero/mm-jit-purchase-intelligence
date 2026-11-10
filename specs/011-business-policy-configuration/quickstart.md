# Quickstart: validating Business Policy Configuration (feature 011)

Synthetic data only. Never point any step at a real Siweb host.

## Prerequisites

- The local stack and synthetic dataset used by the other console tests (see `specs/002-mmi-operational-console/quickstart.md`).
- Users with roles viewer, buyer, approver and admin from the synthetic fixtures; the buyer session with and without fresh MFA.

## 1. Service and contract tests

```bash
pytest services/procurement-service/tests -k "polic or budget"
pytest services/inventory-service/tests -k "rule or exclusion or criticality"
pytest services/forecast-service/tests -k "parameter or run"
pytest services/api-bff/tests -k polic
cd scripts && python -m gates run
```

Expected: all pass, including the new budget concurrency, MFA, SKU, effective-policy, audit-read and run-version tests; the gates report no contract drift.

## 2. Acceptance walk-through in the Spanish UI (API-backed)

```bash
cd apps/web && npx playwright test policies-live.spec.ts
```

The journeys, each with a screenshot saved for the PR:

1. **Change alters the next proposal (story 1).** Buyer sets a segment service level, previews (affected SKUs listed, "nada guardado"), saves, requests a new proposal; quantities match the preview and the explanation cites scope and revision. The earlier proposal is unchanged.
2. **Precedence and defaults (stories 1, 5).** A SKU with global, segment and product values shows each rule's source; a rule with no policy shows "valor por defecto".
3. **Conflict (story 2).** Two sessions open one policy; the second save is refused with the newer revision shown. Same for a budget cap and an exclusion.
4. **Roles and MFA (story 2).** Viewer and approver are refused on every edit; buyer with stale MFA is refused on a budget cap and a global policy, and succeeds after re-authentication. Refusals appear in the audit view.
5. **Budget and criticality (story 3).** A cap below the unconstrained total keeps the next proposal within it and lists deferred lines; marking a SKU critical applies the critical service level.
6. **Exclusion, censoring, parameter (story 4).** Excluding a synthetic spike changes the next forecast and the run lists the exclusion version; reversing restores it; an out-of-range parameter is refused.
7. **Audit and history (stories 2, 5).** The admin audit view lists every change above with actor, before, after and time; policy history shows every revision, none editable.

## 3. Checks that must hold

- No outbound request to the ERP during any step (test asserts this).
- No variant id visible anywhere in the console.
- All text in es-ES; no hard-coded strings (`i18n` test).
- Preview on the full synthetic catalogue within 5 seconds, or progress shown.

## 4. Done when

Every step passes, the PR lists test evidence, screenshots, migration impact (procurement 0013, forecast run column) and known limitations; nothing is deployed or merged.
