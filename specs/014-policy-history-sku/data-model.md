# Data Model: SKU in the policy history

No new tables, columns or migrations. The feature changes the shape of one response row.

## Policy history row (response of `GET /policy-overrides`, shown as `policy_history` in `GET /admin/status`)

| Field | Type | Notes |
|-------|------|-------|
| `id` | string (uuid) | Row identity |
| `variant_id` | integer ≥ 1 | Internal product reference; stays in the procurement response, removed by the gateway before the browser, never shown to people |
| **`sku`** | string or null | **New in the contract.** Current catalogue SKU of the product (`product_refs.sku`, trimmed); null if unknown or blank |
| `field` | `safety_stock` / `min` / `max` | Unchanged |
| `recommended_value`, `requested_value` | integer ≥ 0 | Unchanged |
| `reason` | string ≤ 500 | Unchanged |
| `status` | `pending` / `approved` / `rejected` / `reverted` | Unchanged |
| `requested_by`, `decided_by`, `decided_at` | as today | Unchanged |
| `current_recommended`, `recommendation_changed` | as today | Unchanged |

## Validation rules

- `sku` is always present on a row returned by the list (value or null); the schema marks it nullable and not required, so older producers stay valid (additive change, FR-008).
- A SKU that is empty or whitespace after trimming is returned as null (FR-002, edge case).
- Surrogate ids (≥ 9,000,000) resolve to their SKU like any other; the id is never shown.

## Source of truth

`product_refs(variant_id → sku)` in the procurement schema. Read at request time (spec A3); no snapshot stored.

## State transitions

None. Read-only.
