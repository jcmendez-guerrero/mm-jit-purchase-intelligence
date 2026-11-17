# Quickstart: validating SKU in scenarios

Synthetic data only.

1. **Contracts**: from `scripts/`, run `python -m gates run`; then the contract tests in `packages/contracts/tests`. Expect the SKU, null and missing cases from [the delta](contracts/scenario-sku.delta.md) to pass.
2. **Procurement**: run `services/procurement-service/tests/test_scenarios_api.py`. Expect SKUs on every change and line, null for an unknown product, and the same `result_hash` as before.
3. **Gateway**: run the api-bff tests; the scenario read passes the field through and the no-arithmetic test still passes.
4. **Web**: run the Vitest unit suite; the variant-id display test passes with the scenarios entry removed from `variant-id-display.baseline.json`.
5. **By eye (local)**: open a synthetic scenario; change rows and the line table show SKUs, and a product without a SKU shows the Spanish "not applicable" marker.
