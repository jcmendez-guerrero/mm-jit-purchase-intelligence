# Note for Agent 00: contract changes in feature 011 (MMI-8, Business Policy Configuration)

Shared interfaces touched by this feature. Everything is additive unless stated; nothing here was merged to main.

## Gateway endpoints (`docs/architecture/integration/contract-matrix.json`, status `draft`)

| Change | Entry |
|--------|-------|
| New | `GET /api/policy-audit` (admin; accepted changes and refusals, no free text) |
| New | `GET /api/products/{sku}/effective-policy` (value, source and revision per rule) |
| New | `DELETE /api/policies/{scope}/{key}` (removes an override as a new revision; `If-Match`; fresh MFA for global scope) |
| **Renamed (breaking for callers of the old path)** | `PUT /api/products/{product_id}/criticality` is now `PUT /api/products/{sku}/criticality`; the only consumer is the web app, changed in the same PR |
| **Renamed (breaking for callers of the old path)** | `GET /api/stocking/{variant_id}`, `PUT /api/stocking/{variant_id}` and `GET /api/policy-overrides/recommendation/{variant_id}` are now `.../{sku}`; `POST /api/policy-overrides` takes `sku` instead of `variant_id`; responses (stocking, overrides, recommendation) no longer carry `variant_id`. Only the web app consumes them and changed in the same PR |
| New | `GET /api/products/{sku}/segment-history` (category history by SKU, used by the dashboard detail and the safety-stock screen) |
| **Removed** | `GET /api/segments/{variant_id}/history` (gateway route and matrix entry); the only consumer, the dashboard detail, now uses the SKU route in this PR. The inventory service keeps its own route |
| Behaviour | `PUT /api/budget-caps` now requires `If-Match` once a cap exists (428 / 412) and a fresh second factor; `PUT /api/policies/global/*` needs a fresh second factor |
| Behaviour | Product-scope policy keys, preview rows, exclusions and criticality use the SKU; responses no longer carry `variant_id` |
| Behaviour | `PUT /api/demand-rules/rules/{rule}` takes optional `scope` (`global` default, `segment`, `product`) and `key` (a segment code or, for a product, the SKU); each scope and key has its own revision for `If-Match`; `GET /api/policy-console` rules carry `scope`, `key` and `revision` per entry |
| Behaviour | `PUT /api/demand-rules/rules/{rule}` and `PUT /api/parameters/{key}` now need a fresh second factor (owner decision) |
| Behaviour | `PUT /api/demand-rules/exclusions/{id}` and `PUT /api/demand-rules/rules/{rule}` require `If-Match`; `POST /api/demand-rules/exclusions` takes `sku`, `reason_code`, optional `detail` instead of `variant_id` and free-text `reason` |

- `GET /api/proposals/{id}` `flags` now carries `deferred` (needed lines left out because a cap binds: `sku`, `product_name`, `needed_qty`, `estimated_cost`, `reason`, `bound_by`) and `notes` entries `budget_bound:<cap>` and `critical_over_budget`; `policy_version_ids` already carries the budget cap revisions. Supplier weekly budget caps now take effect.

- `PUT /api/budget-caps` with `scope: "category"` is now refused (422 `budget_scope_unsupported`); `global` and `supplier` are the supported scopes. The `budget_cap.v1` schema still lists `category` in its `scope` enum because removing a value is a breaking change for you to decide.

- **Behaviour change** (not a route change): `replenishment_cadence_days` now sets the product's review period in the proposal's protection horizon (it was stored but unused), product over segment over global; the line explanation holds `policy_applied.<rule> = {source, revision}`.
- `GET /api/policy-audit` takes `scope` (policy, budget, safety_stock, demand, forecast, access), `outcome`, `from`, `to` and `page`, and answers `{items, total, page, page_size, unavailable, truncated}` (50 per page; `truncated` names sources that returned their 500-row limit); `from` and `to` are Europe/Madrid days; stored payloads are whitelisted and show SKUs. The three services' `GET /policy-audit` also take `prefix`, `outcome`, `since` and `until`.
- `POST /api/policies/{scope}/{key}/preview` also answers `forecast_run_id` (the last finished run it used).

## Schemas

- `packages/contracts/dto/demand_rule.v1.schema.json`: added optional `sku`, `reason_code` (pick list), `detail`; `reason` kept and marked superseded. Generated Python and TypeScript types regenerated; no other generated file changed. A v2 that removes `variant_id` and `reason` is a decision for you.
- New response schemas (T064), all additive, with baseline, Python models, TypeScript types and matrix entries (`draft`): `policy_audit_page.v1` (`GET /api/policy-audit`), `effective_policy.v1` (`GET /api/products/{sku}/effective-policy`) and `segment_history.v1` (`GET /api/products/{sku}/segment-history`). `policy_cleared.v1` covers the `DELETE /api/policies/{scope}/{key}` answer (`{revision}`). `policy_set.v1` now says the product key is the SKU (description only). The rule versions on forecast runs have no schema (`GET /runs` is not in the matrix); a `forecast_run` schema is yours to ask for. `gates matrix` empties the consumers of existing entries each time it runs; the matrix entries were fixed by hand.
- Error keys added (`packages/contracts/errors/error_codes.json`, `apps/web/src/i18n/es-ES.json`, `specs/002-mmi-operational-console/contracts/error-keys.md`): `sku_unknown`, `sku_ambiguous`, `policy_overlap`, `exclusion_reason_invalid`, `invalid_input`.
- **Behaviour, every service built with `create_service_app`:** a NUL byte in the request path, the query or a JSON request body (raw or as a `\u0000` escape) is refused with 422 `invalid_input` before any route runs (PostgreSQL cannot store it, so it used to reach the database and come back as a server error). Only JSON bodies are read (`application/json` or a `+json` type, whatever the case; uploads are untouched), and only when their declared length is at most 1 MiB (`MAX_INSPECTED_BODY`), so a very large body is not held in memory by the guard. The gateway is built with `create_service_app` too (`services/api-bff/src/main.py`), so it refuses the same input before any route, session check or audit write; `services/api-bff/tests/test_nul_guard_011.py` proves it for the path, the query and a JSON body. (An earlier version of this note said the opposite; it was wrong.)

## Service interfaces (not in the matrix as endpoints)

- procurement: `GET /policy-audit`, `GET /products/{sku}/effective-policy`, `DELETE /policies/{scope}/{key}`; `GET /policies` adds `weekly_budget_revision` and `orphaned`; proposal and scenario `policy_version_ids` gain `budget:<period>:global:*` entries.
- inventory: `GET /products/{sku}/segments`, `GET /policy-audit`; `/export/series` adds `rule_versions`.
- forecast: `GET /runs` adds `rule_version_ids`.

## Migrations

procurement `0013` (unique index on budget-cap revisions; fails on a database that already holds duplicates), inventory `0008` (`demand_exclusions.reason_detail`), inventory `0009` (`censoring_rules.scope` and `key`, defaults keep existing rows global), inventory `0010` (unique index on `censoring_rules` rule, scope, key and revision; fails on a database that already holds duplicates), forecast `0006` (`forecast_runs.rule_version_ids`), and procurement `0014` (`cost_write_requests.status` widened from 16 to 24 characters: `approved_by_buyer` is 17, so a buyer's approval of a supplier-cost write failed on PostgreSQL; found by running the suite there). All additive and reversible; all six were run up, down and up on PostgreSQL 18. Not a contract change, but worth knowing: the audit hash chain now hashes the instant in UTC whatever offset the database returns (`_aware`, four copies), so `verify_chain` no longer depends on the database session time zone.

## Open

Nothing from the contract side beyond your review of the `draft` matrix entries. `update_baseline` also refreshed the baseline of `proposal_line` and `seed_dataset` (additive changes that came with `main`).
