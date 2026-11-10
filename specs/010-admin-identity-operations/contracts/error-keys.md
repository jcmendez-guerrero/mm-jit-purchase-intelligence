# Error keys added by feature 010

Stable codes only; Spanish text lives in `apps/web/src/i18n/es-ES.json` (and the services' locale files). Register in `packages/contracts/errors/error_codes.json` through Agent 00.

| Code | HTTP | Meaning |
|---|---|---|
| `roles_conflict` | 409 | `expected_revision` differs from the stored revision |
| `roles_last_admin` | 409 | existing: the change would remove the last active administrator |
| `approval_fewer_than_two_approvers` | 409 | existing: the change would leave fewer than two eligible approvers |
| `auth_mfa_stale` | 403 | existing; now also returned by the admin routes marked `x-fresh-mfa` |
| `ops_item_unknown` | 404 | queue item not found |
| `ops_settings_invalid` | 422 | threshold outside its allowed range |
| `export_truncated` | header | informational: export capped at 10 000 rows |
| `snapshot_invalid` | worker log | snapshot failed validation and was rejected (never stored); logged as `SNAPSHOT_REJECTED`, not an HTTP code |
| `snapshot_stale` | UI state | latest snapshot older than its limit |

Alert reason codes (shown in Spanish): `source_stale`, `job_failed`, `message_dead_lettered`, `mirror_lag`, `backup_old`, `backup_missing`, `budget_warning`, `budget_critical`, `delivery_unconfigured`.
