# Research: SKU Route for Product-Supplier Overrides

## D1. Path and old route  (**decided by the owner, 2026-11-16**)

- **Decision**: rename in place to `/product-suppliers/{sku}/{supplier_id}/terms` and delete the variant-id route in the same change, as PR 22 did. The app is new and has no production data, so a transition period buys nothing.
- **Consequence**: the web client and the override screen must move in the same change, or the screen breaks; this overlaps feature 012 T050 for that one screen.
- **Rejected**: a transitional `by-sku` path with both routes (more code, and the final path would differ from the Jira text).

## D2. How the variant id is resolved

- **Decision**: reuse `policies.service.variant_for_sku` (trim, case-insensitive; unknown or empty → `sku_unknown`, several matches → `sku_ambiguous`), mapped to HTTP 422 with `error_code(exc)`, exactly as `GET /products/{sku}/effective-policy` does.
- **Rationale**: one lookup rule for every SKU route; error codes and Spanish text already exist (`errors.sku_unknown`, `errors.sku_ambiguous`).
- **Rejected**: a second lookup in the gateway (the gateway has no catalogue and rule: ids resolved inside the owning service).

## D3. Shared handlers, shared storage

- **Decision**: the route resolves the SKU first, then calls today's logic with the variant id. Stored records, version numbers, the idempotency scope (`product_supplier_terms`, target `variant_id:supplier_id`) and the change-event key stay keyed by variant id internally.
- **Rationale**: no migration and no event-schema change; existing saved terms stay reachable by SKU.
- **Consequence**: the idempotency target and event key still hold the variant id internally. They are not shown to people and are not part of the route's request or response (spec FR-002 says so). The two audit entries (saved and refused) do show the SKU (D5).

## D4. Response shape

- **Decision**: new schema `override_terms_view.v1` = today's `OverrideView` with `sku` instead of `variant_id`. `additionalProperties: false`, so a variant id cannot slip back in. The save answers `{version}` as today.
- **Rejected**: stripping `variant_id` from the old route's answer (breaks the current screen).

## D5. Audit entries show the SKU

- Refused: `api/refusals.py::_target` builds the entity id from `params['variant_id']`, which no longer exists. **Decision**: use `params['sku']`, so the audit shows `<sku>:<supplier>`, consistent with 011's audit that "shows SKUs".
- Saved: `terms/overrides.py::save_override` audits `terms.override_saved` with entity id `variant_id:supplier_id` (line 92). **Decision**: add an optional `audit_label` argument; the route passes `<sku>:<supplier>`. No other caller changes.

## D6. Checks that must change with the new routes

- Existing tests that call the variant-id paths (`services/procurement-service/tests/test_terms_*.py`, `services/api-bff/tests/test_gateway_idempotency.py`, `test_terms_idempotency_forwarding.py`, `test_suppliers_rbac.py`, web e2e `suppliers-manage.spec.ts` and `suppliers-terms-journey.spec.ts`) move to the SKU path.
- Matrix entries are renamed; the "only recorded routes declare an Idempotency-Key" test follows the new path.
- Unverified until implementation: whether a generated OpenAPI file exists (none found in the repo); task T005 checks and records the answer.

## D7. Unknowns

None. Real ERP behaviour is untouched.
