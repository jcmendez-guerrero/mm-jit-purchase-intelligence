# Data Model: SKU in scenario changes and result lines

No table, column or migration changes. The SKU is derived at read time.

| Item | Where it lives | Change |
|------|----------------|--------|
| Scenario change | `scenarios.summary.changes[]` (JSON) | Read response adds `sku: string \| null` next to `variant_id` |
| Scenario result line | `scenario_results.lines[]` (JSON) | Read response adds `sku: string \| null` next to `variant_id` |
| Product reference | `product_refs` (`variant_id` key, `sku`) | Read only; source of the SKU |

## Rules

- `sku` = trimmed `product_refs.sku` for the item's `variant_id`; null when no row, null, empty or whitespace.
- Computed per read; never persisted; never part of `result_hash` or the optimisation inputs.
- `variant_id` stays in the payload for API use; the UI never renders it.
- Item counts in the response equal the stored counts (nothing dropped when a SKU is missing).
