# Data Model: Business Policy Configuration (Agent 06)

Existing entities are listed with only what this feature changes. Each stays in the schema of its owning service; there is no cross-schema SQL.

## Policy set (procurement) — existing `policy_sets`

| Field | Notes |
|-------|-------|
| scope | `global`, `segment`, `product` |
| key | `*` for global; segment code A, B, C, critical, sparse; product: variant id internally, shown as SKU |
| service_level | 0 to 1, 4 decimals, 0 to 100 % in the UI |
| safety_stock_units, min_units, max_units | integer, not negative, max not below min |
| replenishment_cadence_days | integer, at least 1 |
| valid_from, valid_to | date; `valid_from` not in the past (D1) |
| revision | integer, increments per scope and key; saves need the current revision |
| changed_by | actor id |

Rules: most specific scope wins per field. No overlapping periods for the same scope and key (A4, add check). Past revisions are never updated. Removing an override writes a new revision with the field empty, so the lower scope or default applies.

**New (derived, no table):** *effective policy view* per product: for each field, `{value, source: default|global|segment|product, key, revision, valid_from}`.

## Budget cap (procurement) — existing `budget_caps`

| Field | Notes |
|-------|-------|
| period | week or month |
| scope, scope_key | global, supplier or category; `scope_key` null only for global |
| amount | `Decimal`, 18,4, not negative |
| valid_from, valid_to | date |
| revision | **now checked on save** (D2): new revision per `(period, scope, scope_key)` |
| changed_by | actor id |

Change: migration 0013 adds a uniqueness constraint on `(period, scope, scope_key, revision)` so two simultaneous saves cannot both win.

## Stocking setting, override request (procurement) — unchanged

Existing `stocking_settings` and `policy_override_requests`; approver is not the requester (already enforced). Included in the audit view.

## Demand exclusion and censoring rule (inventory) — existing

| Field | Notes |
|-------|-------|
| exclusion: variant, from, to, reason code, active | reason is a pick-list code; short detail admin-only, never in audit payload (D7) |
| censoring rule: rule, value, revision | **save now needs the expected revision** (D2) |
| exclusion set revision | **new**: a counter of changes to the exclusion set, exposed in the series export (D5) |

## Clinical criticality (inventory) — unchanged storage

Edit goes by SKU at the BFF (D3); history already kept.

## Forecast parameter (forecast) — existing `forecast_parameters`

Approved keys and ranges stay in code (`lead_time`, `backtest.min_history`, `backtest.min_windows`, `backtest.min_gain`, `backtest.max_censored_share`). Effective-dated, revisioned.

## Forecast run (forecast) — existing

| Field | Change |
|-------|--------|
| parameter_version_ids | existing |
| **rule_version_ids** | **new JSON**: `{"exclusions": n, "censoring.<rule>": n}` copied from the series export (D5) |

Migration in the forecast service: add nullable `rule_version_ids` column.

## Proposal and scenario — unchanged

Already carry `policy_version_ids` (`"scope:key" -> revision`) and terms versions. Budget cap revisions are added to the same map as `budget:<period>:<scope>:<key>` so SC-006 holds for budgets too.

## Policy audit record — existing hash-chained audit

Read-only projection for the admin view: `{at (UTC), actor, action, scope, key or SKU, before, after, effective_from, revision, outcome}`. Free-text detail is excluded. Refusals appear with `outcome=refused` and the reason code.

## State transitions

- Policy / budget cap / parameter: `saved(rev n)` → `saved(rev n+1)`; never edited in place; effective from `valid_from`.
- Exclusion: `active` ⇄ `inactive`, each audited.
- Override request: `pending` → `approved` / `rejected` → `reverted` (existing).
