# Note to Agent 00: shared contract changes from feature 010 (Jira MMI-9)

Everything below is already in this branch so the gateway, matrix and error-code tests pass. Please review; nothing here widens a permission or adds an ERP request.

## 1. New gateway endpoints (all admin only; marked ones need MFA no older than 5 minutes)

`GET /api/admin/audit`, `GET /api/admin/audit/verify`, `GET /api/admin/audit/export` (MFA), `GET /api/admin/ops/queue`, `POST /api/admin/ops/queue/{kind}/{item_id}/retry` (MFA), `GET /api/admin/alerts`, `POST /api/admin/alerts/{alert_id}/acknowledge` (MFA), `GET /api/admin/ops/summary`, `GET /api/admin/ops/settings`, `PUT /api/admin/ops/settings` (MFA). Entries added to `docs/architecture/integration/contract-matrix.json` as `draft`, owner `agent-00`, consumer `web`. Spec: `contracts/admin-ops.delta.openapi.yaml`.

## 2. Changed behaviour of existing endpoints

- `PUT /api/admin/roles/{user_id}` accepts optional `expected_revision` (409 `roles_conflict` when stale) and now needs fresh MFA.
- `POST /api/admin/roles/mirror/retry`, `POST /api/admin/rerun/forecast`, `POST /api/admin/rerun/import/{job_id}`, `POST /api/admin/rerun/mirror` now need fresh MFA.
- `GET /api/admin/status`: `cost.estimate_eur` is removed (the static figure was misleading); spend now comes from `GET /api/admin/ops/summary`.

## 3. Error codes

Added to `packages/contracts/errors/error_codes.json` (and `errors.*` in es-ES, and the 002 error-key table): `roles_conflict` 409, `ops_item_unknown` 404, `ops_settings_invalid` 422. The existing names `roles_last_admin` and `approval_fewer_than_two_approvers` are reused.

## 4. Draft schema, not promoted

`contracts/ops_snapshot.v1.schema.json` (backup, cost, queues figures supplied by the platform) is still a feature-local draft. The BFF validates it with its own Pydantic model (`services/api-bff/src/ops/snapshots.py`). Please decide whether it moves to `packages/contracts/dto/`.

## 5. Schema ownership

`api-bff` (schema `bff`) gains tables `alerts`, `ops_snapshots`, `ops_settings` (migration `0002`). No other schema is touched.

## Open questions

- **OQ-1** Should procurement's audit chain appear in the same console? Not built; v1 shows the BFF chain only.
- **OQ-2** Resolved by default: snapshots are read from `ops-inputs/*.json` (gitignored). Tell us if the platform wants another channel.
- **OQ-3** The approver floor is 2 (`approval_fewer_than_two_approvers`, `services/api-bff/src/db/roles.py`).
