# Data Model: Administration, Identity & Operations (010)

All tables live in the BFF-owned `bff` schema (no cross-schema SQL). Existing tables are reused unchanged: `user_roles`, `role_mirror_outbox`, `audit_events`. Times are UTC `timestamptz`; where a source string exists it is kept next to the parsed value. New migration: `services/api-bff/migrations/versions/0002_admin_ops.py`.

## Reused (unchanged)

| Entity | Table | Notes |
|---|---|---|
| User role assignment | `user_roles` | user_id, roles[], active, revision, updated_by, updated_at |
| Role mirror item | `role_mirror_outbox` | status `pending` \| `failed` \| sent; attempts, next_attempt_at, last_error_key. `failed` is the dead-letter state (D4) |
| Audit entry | `audit_events` | append-only, hash-linked (prev_hash, hash); actor, action, entity, entity_id, before/after (structured, no free text) |

## New

### `alerts`

| Column | Type | Rule |
|---|---|---|
| id | bigserial PK | |
| condition_key | text | one of `source_stale`, `job_failed`, `message_dead_lettered`, `mirror_lag`, `backup_old`, `backup_missing`, `budget_warning`, `budget_critical`, `delivery_unconfigured` |
| subject | text | source key, job id, etc.; never free text; part of uniqueness |
| severity | text | `warning` \| `critical` |
| state | text | `open` → `acknowledged` → `closed`; `open` → `closed` when the condition clears |
| opened_at, last_seen_at | timestamptz | |
| acknowledged_by, acknowledged_at | text, timestamptz | set only through the acknowledge action |
| closed_at | timestamptz | |
| reason_code | text | stable code; translated in the UI |

Unique partial index on (condition_key, subject) where state <> `closed` — enforces FR-017 de-duplication (SC-007).

Transitions: re-evaluation of a live condition updates `last_seen_at` only; a cleared condition sets `closed_at`; acknowledging an already closed alert is a no-op (idempotent).

### `alert_observations`

Consecutive-sighting counter for conditions that must repeat before opening (D15): primary key (`condition_key`, `subject`), `count`, `last_seen_at`. Deleted when the condition is no longer seen.

### `ops_snapshots`

| Column | Type | Rule |
|---|---|---|
| id | bigserial PK | |
| kind | text | `backup` \| `cost` \| `queues` |
| captured_at | timestamptz | from the snapshot; rejected if in the future |
| captured_at_original | text | original string retained |
| payload | jsonb | validated against `contracts/ops_snapshot.v1.schema.json`; money as decimal strings, never floats |
| status | text | `ok` \| `unavailable` |

Only the latest row per kind is shown as current; a row older than its limit is shown as stale, never as current (US5 scenario 3).

### `ops_settings`

Single-row-per-key configuration: `source_stale_hours` (36), `backup_max_age_hours` (26), `budget_warn_pct` (80), `budget_critical_pct` (100), `mirror_lag_minutes` (15), `alert_repeat_hours` (24), `job_failed_observations` (2). Changes are audited, admin plus fresh MFA, with `updated_by` and `updated_at`.

## Validation rules (from the spec)

- `expected_revision` on a role update must equal the stored revision, else conflict (D7).
- Role change refused when it removes the last active admin or leaves fewer than the required eligible approvers (FR-006); unknown role names are ignored on sign-in claims (FR-007).
- Audit export range is capped at 10,000 rows and reports `truncated: true` when capped (edge case).
- Cost and backup payloads: amounts are decimal strings in EUR; `projected_eur` is labelled estimate when the month is partial.
