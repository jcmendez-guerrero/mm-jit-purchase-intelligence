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
| New | `GET /api/products/{sku}/segment-history` (category history by SKU, used by the safety-stock screen); `GET /api/segments/{variant_id}/history` stays for the dashboard, which only uses ids in API calls |
| Behaviour | `PUT /api/budget-caps` now requires `If-Match` once a cap exists (428 / 412) and a fresh second factor; `PUT /api/policies/global/*` needs a fresh second factor |
| Behaviour | Product-scope policy keys, preview rows, exclusions and criticality use the SKU; responses no longer carry `variant_id` |
| Behaviour | `PUT /api/demand-rules/rules/{rule}` takes optional `scope` (`global` default, `segment`, `product`) and `key` (a segment code or, for a product, the SKU); each scope and key has its own revision for `If-Match`; `GET /api/policy-console` rules carry `scope`, `key` and `revision` per entry |
| Behaviour | `PUT /api/demand-rules/rules/{rule}` and `PUT /api/parameters/{key}` now need a fresh second factor (owner decision) |
| Behaviour | `PUT /api/demand-rules/exclusions/{id}` and `PUT /api/demand-rules/rules/{rule}` require `If-Match`; `POST /api/demand-rules/exclusions` takes `sku`, `reason_code`, optional `detail` instead of `variant_id` and free-text `reason` |

- `GET /api/proposals/{id}` `flags` now carries `deferred` (needed lines left out because a cap binds: `sku`, `product_name`, `needed_qty`, `estimated_cost`, `reason`, `bound_by`) and `notes` entries `budget_bound:<cap>` and `critical_over_budget`; `policy_version_ids` already carries the budget cap revisions. Supplier weekly budget caps now take effect.

- `PUT /api/budget-caps` with `scope: "category"` is now refused (422 `budget_scope_unsupported`); `global` and `supplier` are the supported scopes. The `budget_cap.v1` schema still lists `category` in its `scope` enum because removing a value is a breaking change for you to decide.

- **Behaviour change** (not a route change): `replenishment_cadence_days` now sets the product's review period in the proposal's protection horizon (it was stored but unused), product over segment over global; the line explanation holds `policy_applied.<rule> = {source, revision}`.
- `GET /api/policy-audit` takes `scope` (policy, budget, safety_stock, demand, forecast, access), `outcome`, `from`, `to` and `page`, and answers `{items, total, page, page_size, unavailable}` (50 per page); stored payloads are whitelisted and show SKUs.
- `POST /api/policies/{scope}/{key}/preview` also answers `forecast_run_id` (the last finished run it used).

## Schemas

- `packages/contracts/dto/demand_rule.v1.schema.json`: added optional `sku`, `reason_code` (pick list), `detail`; `reason` kept and marked superseded. Generated Python and TypeScript types regenerated; no other generated file changed. A v2 that removes `variant_id` and `reason` is a decision for you.
- Error keys added (`packages/contracts/errors/error_codes.json`, `apps/web/src/i18n/es-ES.json`, `specs/002-mmi-operational-console/contracts/error-keys.md`): `sku_unknown`, `sku_ambiguous`, `policy_overlap`, `exclusion_reason_invalid`.

## Service interfaces (not in the matrix as endpoints)

- procurement: `GET /policy-audit`, `GET /products/{sku}/effective-policy`, `DELETE /policies/{scope}/{key}`; `GET /policies` adds `weekly_budget_revision` and `orphaned`; proposal and scenario `policy_version_ids` gain `budget:<period>:global:*` entries.
- inventory: `GET /products/{sku}/segments`, `GET /policy-audit`; `/export/series` adds `rule_versions`.
- forecast: `GET /runs` adds `rule_version_ids`.

## Migrations

procurement `0013` (unique index on budget-cap revisions; fails on a database that already holds duplicates), inventory `0008` (`demand_exclusions.reason_detail`), inventory `0009` (`censoring_rules.scope` and `key`, defaults keep existing rows global), forecast `0006` (`forecast_runs.rule_version_ids`). All additive and reversible.

## Open

The dashboard still calls `GET /api/segments/{variant_id}/history` with an id taken from its own rows; it never shows the id. Moving it to the SKU route is a possible follow-up.
