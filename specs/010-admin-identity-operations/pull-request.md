# Administration, Identity & Operations (Agent 07) — Jira MMI-9, spec 010

Links: Jira MMI-9, Confluence page 3244047 (MMI 003 / Agent 07), epic MMI-1. Spec: `specs/010-admin-identity-operations/`.

## What changed

Audit-then-close-gaps. The inventory (`research.md` section 1) found durable roles, the role mirror, approver separation, the audit chain and the status page already working. This PR closes the gaps:

- **MFA**: role changes, mirror retry and all re-runs now need MFA no older than 5 minutes; refusals are audited.
- **Concurrency**: optional `expected_revision` on role edits (409 `roles_conflict`); the screen always sends it.
- **Audit viewer**: filter, page, verify the hash chain, capped CSV export (10 000 rows, audited, formula-safe). Rows hold ids, codes and UTC times only.
- **Queue view and safe retry**: role-mirror items, import jobs, forecast runs and platform dead letters in one list; retry is idempotent and audited.
- **Alerts**: de-duplicated, acknowledgeable, auto-closing, evaluated by the existing scheduled worker (no always-on service) and on console read; `python -m worker snapshot <file>` supplies backup, cost and queue figures; one log marker `ADMIN_ALERT_OPENED` per opening feeds a new e-mail rule in `alerts.bicep`.
- **Backup and spend**: validated read-only snapshots (`ops-inputs/*.json`, gitignored) shown against the EUR 120 budget; the static estimate is removed from `/admin/status`.
- **Thresholds**: configurable (defaults 36 h, 26 h, 80 %, 100 %, 15 min, 24 h), admin plus fresh MFA, audited.

## Migration impact

`services/api-bff/migrations/versions/0002_admin_ops.py` adds `alerts`, `alert_observations`, `ops_snapshots`, `ops_settings` in the BFF schema; downgrade drops them. Verified on PostgreSQL (`infra/tests/test_migrations_postgres.py`, including a new test for these tables and the one-live-alert index).

## Contract impact (for Agent 00, see `agent-00-contract-note.md`)

10 new gateway endpoints (matrix entries as `draft`), 5 existing admin routes now need fresh MFA, `cost.estimate_eur` removed from `/admin/status`, three error codes added (`roles_conflict`, `ops_item_unknown`, `ops_settings_invalid`).

## Security, data and cost

- No ERP request added; a test asserts the new modules never reference the ERP client. No secrets: the e-mail channel is the existing Azure action group; the app holds no mail credentials.
- Synthetic fixtures only (`packages/testing/fixtures/ops/`). A scan test checks audit rows, exports and logs for tokens, addresses and notes.
- Cost: no new always-on resource; guardrail test and `cost` gate pass.

## Tests

See `quickstart.md` "Results". Screenshots (es-ES): `evidence/*.png`.

## Known limitations

- The BFF audit chain only; procurement's chain is not shown (OQ-1).
- The scheduled worker evaluates everything with a read-only (viewer) service identity; a failed job alerts only after it is seen on 2 consecutive evaluations (setting).
- Platform dead letters depend on the `queues` snapshot being supplied; without it that part of the view is empty.
- One unrelated flaky e2e (`a11y-all-routes.spec.ts` theme switch) fails the e2e gate; unverified on clean main.
- `ops_snapshot.v1.schema.json` is not promoted to `packages/contracts` (decision D13).
