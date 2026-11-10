# Note for Agent 00: contract changes in feature 011 (MMI-8, Business Policy Configuration)

Shared interfaces touched by this feature. Everything is additive unless stated; nothing here was merged to main.

## Gateway endpoints (`docs/architecture/integration/contract-matrix.json`, status `draft`)

| Change | Entry |
|--------|-------|
| New | `GET /api/policy-audit` (admin; accepted changes and refusals, no free text) |
| New | `GET /api/products/{sku}/effective-policy` (value, source and revision per rule) |
| New | `DELETE /api/policies/{scope}/{key}` (removes an override as a new revision; `If-Match`; fresh MFA for global scope) |
| **Renamed (breaking for callers of the old path)** | `PUT /api/products/{product_id}/criticality` is now `PUT /api/products/{sku}/criticality`; the only consumer is the web app, changed in the same PR |
| Behaviour | `PUT /api/budget-caps` now requires `If-Match` once a cap exists (428 / 412) and a fresh second factor; `PUT /api/policies/global/*` needs a fresh second factor |
| Behaviour | Product-scope policy keys, preview rows, exclusions and criticality use the SKU; responses no longer carry `variant_id` |
| Behaviour | `PUT /api/demand-rules/exclusions/{id}` and `PUT /api/demand-rules/rules/{rule}` require `If-Match`; `POST /api/demand-rules/exclusions` takes `sku`, `reason_code`, optional `detail` instead of `variant_id` and free-text `reason` |

## Schemas

- `packages/contracts/dto/demand_rule.v1.schema.json`: added optional `sku`, `reason_code` (pick list), `detail`; `reason` kept and marked superseded. Generated Python and TypeScript types regenerated; no other generated file changed. A v2 that removes `variant_id` and `reason` is a decision for you.
- Error keys added (`packages/contracts/errors/error_codes.json`, `apps/web/src/i18n/es-ES.json`, `specs/002-mmi-operational-console/contracts/error-keys.md`): `sku_unknown`, `sku_ambiguous`, `policy_overlap`, `exclusion_reason_invalid`.

## Service interfaces (not in the matrix as endpoints)

- procurement: `GET /policy-audit`, `GET /products/{sku}/effective-policy`, `DELETE /policies/{scope}/{key}`; `GET /policies` adds `weekly_budget_revision` and `orphaned`; proposal and scenario `policy_version_ids` gain `budget:<period>:global:*` entries.
- inventory: `GET /products/{sku}/segments`, `GET /policy-audit`; `/export/series` adds `rule_versions`.
- forecast: `GET /runs` adds `rule_version_ids`.

## Migrations

procurement `0013` (unique index on budget-cap revisions; fails on a database that already holds duplicates), inventory `0008` (`demand_exclusions.reason_detail`), forecast `0006` (`forecast_runs.rule_version_ids`). All additive and reversible.

## Open

The safety-stock override and always-stocked routes still take a variant id (`/stocking/{variant_id}`, `/policy-overrides`); moving them to SKU is a further contract change not made here.
