# Contract delta: policy console (feature 011)

Changes to the existing gateway and service interfaces. Anything not listed is unchanged. Schema changes go to `packages/contracts` first and through Agent 00; run `python -m gates run` from `scripts/` before the PR.

## Gateway (BFF) routes

| Route | Change | Roles | Extra |
|-------|--------|-------|-------|
| `PUT /policies/{scope}/{key}` | `key` for `product` scope is the **SKU**; BFF resolves it to the variant id. Unknown or ambiguous SKU → 422 `sku_unknown` / `sku_ambiguous` | buyer, admin | Fresh MFA when `scope = global` (403 `auth_mfa_stale`) |
| `POST /policies/{scope}/{key}/preview` | Same SKU rule; affected rows return `sku`, never `variant_id` | buyer, admin | none |
| `PUT /budget-caps` | Requires `If-Match` revision (428 `revision_required`; 412 `revision_conflict` with `current_version`); response includes `revision` | buyer, admin | Fresh MFA always |
| `PUT /products/{sku}/criticality` | Path is the SKU | buyer, admin | none |
| `POST /demand-rules/exclusions`, `PUT /demand-rules/exclusions/{id}` | Body uses `sku`, `reason_code` (pick list), optional `detail` (max length, admin-only). Toggle requires `If-Match` | buyer, admin | none |
| `PUT /demand-rules/rules/{rule}` | Requires `If-Match` | buyer, admin | none |
| `GET /products/{sku}/effective-policy` | **New.** Per rule: `{value, source: default/global/segment/product, key, revision, valid_from}` | all roles | read only |
| `GET /policy-audit` | **New.** Paged, filters `scope`, `from`, `to`, `outcome`; items `{at, actor, action, scope, key, before, after, effective_from, revision, outcome, reason_code}` | admin | no free-text detail |
| `GET /policy-console` | Adds `orphaned` list (product policies whose SKU is no longer in the catalogue) | all roles | read only |

Refusals (role, CSRF, stale MFA, stale revision) are recorded through the existing hash-chained audit; `/policy-audit` lists them with `outcome = refused`.

## Service interfaces

| Service | Change |
|---------|--------|
| procurement | `PUT /budget-caps` accepts `expected_revision` (header `If-Match`); explicit overlap refusal for policy sets (422 `policy_overlap`); resolver returns provenance; proposal and scenario `policy_version_ids` gain `budget:<period>:<scope>:<key>` entries |
| inventory | exclusion and censoring-rule saves accept `expected_revision`; series export adds `rule_versions: {"exclusions": n, "censoring.<rule>": n}` |
| forecast | run record adds nullable `rule_version_ids` copied from the export; run list returns it |

## New stable error keys

In `packages/contracts/errors/error_codes.json`, with Spanish text in `apps/web/src/i18n/es-ES.json`: `sku_unknown`, `sku_ambiguous`, `policy_overlap`, `exclusion_reason_invalid`. Reused: `policy_out_of_range`, `revision_conflict`, `revision_required`, `auth_mfa_stale`, `forbidden_missing_role`.

## Events

No new event. Existing policy-change notifications stay as they are.
