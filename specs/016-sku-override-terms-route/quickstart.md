# Quickstart: validate the SKU route

Prerequisites: repo checked out, Python 3.13 environments for `services/procurement-service` and `services/api-bff`. Synthetic fixtures only; never a real Siweb host.

1. **Contract**: run `python -m gates run` from `scripts/` (schema, baseline and matrix agree).
2. **Procurement**: run `pytest services/procurement-service/tests/test_terms_sku_016.py services/procurement-service/tests/test_terms_api.py`.
   Expect: read and save by a synthetic SKU; unknown SKU gives 422 `sku_unknown`; two products sharing a SKU give `sku_ambiguous`; no `variant_id` in any answer, audit entry or captured log; the old variant-id path is unknown.
3. **Gateway**: run `pytest services/api-bff/tests/test_terms_sku_016.py services/api-bff/tests/test_gateway_matrix.py services/api-bff/tests/test_gateway_idempotency.py`.
   Expect: viewer reads, only buyer saves, headers forwarded, old path unknown.
4. **Spanish message**: the web catalogue already holds `errors.sku_unknown` and `errors.sku_ambiguous`; the existing catalogue test must still pass.
5. **Web**: in `apps/web` run the unit tests (`glossary`, variant-id display) and the suppliers e2e specs; the override screen asks for a SKU and shows the Spanish message for an unknown one.
