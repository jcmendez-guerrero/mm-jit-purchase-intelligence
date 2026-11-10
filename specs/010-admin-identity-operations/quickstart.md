# Quickstart: validating feature 010

Synthetic data only; never point these at a real Siweb host or real identities. Contracts: [contracts/](contracts/). Model: [data-model.md](data-model.md).

## Prerequisites

- Local stack from `infra/compose.yaml` (synthetic seed); Python and Node toolchains as in the repo README.
- Dev sign-in is off by default; tests use the header helpers in `services/api-bff/tests/tests_support.py`.

## 1. Backend suites

```bash
cd services/api-bff && python -m pytest tests -q
cd ../procurement-service && python -m pytest tests -q -k "approv or role"
```

Expect: existing role, audit, MFA and re-run tests stay green; the new tests for FR-008 (stale MFA refused on role change, retries and re-runs), FR-011 (audit filter, verify, export cap), FR-014 to FR-017 (queue view, idempotent retry, alert de-duplication across 20 evaluations) and SC-008 (secret scan) pass.

## 2. Restart survival (US1, SC-001)

1. Assign `approver` to a synthetic user through `PUT /admin/roles/{id}` with fresh MFA.
2. Restart all services (`docker compose restart`).
3. `GET /admin/roles` shows the same assignment and `GET /admin/roles/mirror` shows no pending items.
4. Submit a proposal as buyer A; approve it as the approver with fresh MFA (200); repeat as buyer A (refused, stable code).

## 3. Audit (US2, SC-004)

1. `GET /admin/audit?outcome=refused` lists the stale-MFA refusal from step 2 and nothing sensitive.
2. `GET /admin/audit/verify` returns `ok: true`; alter one row in the test database and it returns the first broken id.

## 4. Operations, alerts, backup and cost (US3 to US5)

1. Load the synthetic snapshots under `packages/testing/fixtures/ops/` (backup old, cost at 85 %).
2. Run the worker alert pass once; `GET /admin/alerts` shows `backup_old` and `budget_warning`; run it 20 more times and the counts do not grow.
3. Acknowledge one alert (fresh MFA); fix the snapshot and rerun; it closes.
4. Retry a failed mirror item twice; one delivery, two audit entries.

## 5. Web (es-ES)

```bash
cd apps/web && npm run test && npx playwright test tests/e2e/admin-status.spec.ts tests/e2e/roles.spec.ts
```

Expect the console to show the alert list, audit viewer, queue view, backup and cost cards in Spanish with EUR and Spanish dates, and no untranslated keys.

## 6. Gates

```bash
cd scripts && python -m gates run
```

Run before the PR, since contracts and error codes change.

## Results (run 2026-11-10, local, synthetic data)

| Check | Result |
|---|---|
| `services/api-bff` pytest | 300 passed (225 before this feature plus the new admin, audit, MFA, queue, alert, snapshot tests) |
| `packages/contracts` pytest (without the Azurite test, which needs a running emulator) | 237 passed |
| `infra/tests` | 66 passed, 17 skipped (Docker-only) |
| `apps/web` Vitest | 552 passed |
| Playwright, whole suite | 215 passed, 6 skipped, 1 failed: `a11y-all-routes.spec.ts` theme switch on `/panel` (a different route failed on a rerun: `/importaciones`); no admin route fails. Not reproduced on a clean main, so unverified there. |
| Playwright `admin-ops`, `admin-status`, `roles` | 13 passed |
| Gates `contracts`, `isolation`, `security`, `cost` | pass |
| Gate `e2e` | fail (same a11y theme flake) |
| Gate `integration` | not run (no PR list) |
| Section 2 (restart survival and approval) | restart survival is covered by the existing `services/api-bff/tests/test_roles_persistence.py` (new process, same database); approver-not-creator by `services/procurement-service/tests/test_approval.py`. The end-to-end flow across all services on the compose stack was not run. |
| Real PostgreSQL migration `0002` | `RUN_PG_MIGRATIONS=1` with Docker: 10 passed (model matches migration, reversible, new admin-tables and one-live-alert test) |
| Compose stack end to end | not run |
