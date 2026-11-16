# Contract delta: SKU in scenario changes and lines

Schema first (rule 9). Owner: procurement-service. Registered through Agent 00 in `docs/architecture/integration/contract-matrix.json`.

## `dto/scenario_result.v1.schema.json`, `lines[]` item

Add next to `variant_id`:

```json
"sku": { "type": ["string", "null"], "minLength": 1 }
```

It joins `required` (clarified 2026-11-16); if the gate refuses that in v1, the contract becomes v2.

## `dto/scenario.v1.schema.json`, new `summary.changes[]` item

Documents the shape the API already returns, plus the SKU:

| Field | Type |
|-------|------|
| `variant_id` | integer ≥ 1 |
| `sku` | string or null |
| `supplier_before`, `supplier_after` | string or null |
| `qty_before`, `qty_after` | integer ≥ 0 |
| `reasons` | array of strings |

## Contract tests (`packages/contracts/tests/test_mmi002_contracts.py`)

- A line and a change with a SKU validate.
- A line and a change with `sku: null` validate.
- A line or change without `sku` is rejected.
- An empty-string `sku` is rejected.

## Service tests (procurement)

- `GET /scenarios/{id}`: every change and line has the catalogue SKU; unknown product gives null.
- A scenario stored before the change returns SKUs without recompute; `result_hash`, totals and status are identical.
- Row counts equal stored counts.
