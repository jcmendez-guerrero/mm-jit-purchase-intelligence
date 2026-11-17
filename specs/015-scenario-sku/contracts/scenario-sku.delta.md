# Contract delta: SKU in scenario changes and lines

Schema first (rule 9). Owner: procurement-service. Registered through Agent 00 in `docs/architecture/integration/contract-matrix.json`.

## `dto/scenario_result.v1.schema.json`, `lines[]` item

Add next to `variant_id`:

```json
"sku": { "type": ["string", "null"], "minLength": 1 }
```

It stays optional in `required` terms (Agent 00 review of PR 29, ADR-021: v1 allows only added optional properties); the service always sends it.

## `dto/scenario.v1.schema.json`, new `summary.changes[]` item

Documents the shape the API already returns, plus the SKU:

| Field | Type |
|-------|------|
| `variant_id` | integer ≥ 1 |
| `sku` | string or null (optional) |
| `name` | string or null (optional) |
| `supplier_before`, `supplier_after` | string or null |
| `qty_before`, `qty_after` | integer ≥ 0 |
| `reasons` | array of strings |

## Also added (convergence, T031 and T033)

- `name` (string or null, optional) next to `sku` in `lines[]` of `scenario_result.v1` and in `summary.changes[]` of `scenario.v1`.
- `summary.infeasible` in `scenario.v1`: `over_by`, `clinical_critical_variants` (integers) and `clinical_critical_skus` (string or null, same order).
- The `lines[]` schema keeps its legacy shape; the real read model is checked in `services/procurement-service/tests/test_scenarios_api.py` against `summary`.

## Contract tests (`packages/contracts/tests/test_mmi002_contracts.py`)

- A line and a change with a SKU validate.
- A line and a change with `sku: null` validate.
- A line or change without `sku` is accepted (optional in v1); the service always sends it, which the procurement test checks.
- An empty-string `sku` is rejected.

## Service tests (procurement)

- `GET /scenarios/{id}`: every change and line has the catalogue SKU; unknown product gives null.
- A scenario stored before the change returns SKUs without recompute; `result_hash`, totals and status are identical.
- Row counts equal stored counts.

## Which shape is authoritative

The `GET /scenarios/{id}` read model of procurement is authoritative: lines carry `qty`, `unit_cost` and `line_total` as strings and `clinical_critical`. The `scenario_result.v1` line schema keeps its legacy shape (`quantity`, an object `unit_cost`) because removing or retyping fields is breaking, so only `sku` and `name` are shared with the read model. The `summary` of `scenario.v1` does match the response and is validated against it in `services/procurement-service/tests/test_scenarios_api.py`.

The gateway removes `summary.infeasible.clinical_critical_variants` before the response reaches the browser (rule 5); procurement still sends it next to `clinical_critical_skus`.
