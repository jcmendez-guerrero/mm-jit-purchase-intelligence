# Note for Agent 00: contract changes in spec 016 (MMI-16, SKU route for product-supplier terms)

## Gateway endpoints (`docs/architecture/integration/contract-matrix.json`, status `draft`)

| Change | Entry |
|--------|-------|
| **Renamed (breaking for callers of the old path)** | `GET /api/product-suppliers/{variant_id}/{supplier_id}/terms` is now `GET /api/product-suppliers/{sku}/{supplier_id}/terms` |
| **Renamed (breaking for callers of the old path)** | `PUT /api/product-suppliers/{variant_id}/{supplier_id}/terms` is now `PUT /api/product-suppliers/{sku}/{supplier_id}/terms` |

The only consumer is the web app, changed in the same PR (override screen only). The app has no production data, so there is no transition route.

## Schemas

- New `packages/contracts/dto/override_terms_view.v1.schema.json` (answer of the GET; `sku` instead of `variant_id`, `additionalProperties: false`), with baseline, generated Python model and TypeScript type and a matrix entry (`draft`, owner `procurement-service`, as Agent 00 asked; it becomes `frozen` when this merges). The save still answers `{version}`.
- Error keys: unchanged. `sku_unknown` and `sku_ambiguous` already exist in `packages/contracts/errors/error_codes.json` and `apps/web/src/i18n/es-ES.json`.

## Behaviour

- Procurement resolves the variant id from the SKU (`variant_for_sku`, trimmed and case-insensitive). Unknown or empty SKU: 422 `sku_unknown`; several products: 422 `sku_ambiguous`.
- Stored records, versions, idempotency scope and target (`product_supplier_terms`, `variant_id:supplier_id`) and the change-event key are unchanged and internal. Terms saved before this change stay reachable by SKU.
- Audit entities for `terms.override_saved` and `terms.refused` on this route are now `<sku>:<supplier_id>` (earlier entries keep the old text).

## OpenAPI

There is no committed OpenAPI file: the gateway's own `app.openapi()` is compared with the matrix by `services/api-bff/tests/test_gateway_matrix.py`, which covers the rename (T005). `python -m gates run` reports "endpoints not checked (no openapi supplied)" for the same reason.

## Overlap with feature 012 (PR 24)

`specs/012-ux-navigation-localization/tasks.md` T050 lists the override screen; this change does that screen only. If PR 24 lands first, keep its `OverrideEditor.tsx` and apply only what is missing.
