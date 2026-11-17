# Contract: product-supplier terms by SKU

Same session and roles as before. Gateway prefix `/api`. Matrix status `draft`, owner Agent 00. The two old entries (`{variant_id}`) are **renamed** to `{sku}`; this is breaking for callers of the old path, and the only consumer is the web app, changed in the same PR.

## GET `/api/product-suppliers/{sku}/{supplier_id}/terms?as_of=`

- Roles: viewer, buyer, approver, admin.
- 200: `override_terms_view.v1` (`sku`, no `variant_id`).
- 422 `sku_unknown`, 422 `sku_ambiguous`, 422 `invalid_input` (NUL byte), 400 `request_invalid` (bad `as_of`), 401, 403.

## PUT `/api/product-suppliers/{sku}/{supplier_id}/terms`

- Role: buyer. Headers: `If-Match` (428 `revision_required` / 412 with `current_version`), optional `Idempotency-Key` (422 on a bad key; replay answers `Idempotent-Replay: true`).
- Body: unchanged (`pack_multiple`, `min_qty_units`, `lead_time_days`, `payment_terms_days`, `preferred`, `reliability`, `disabled`, `valid_from`, `valid_to`, `reason`).
- 200: `{ "version": n }`.
- 422 `sku_unknown`, `sku_ambiguous`, plus today's validation codes; 403 `auth_forbidden_role`.

## Procurement service (internal)

Same two operations at `/product-suppliers/{sku}/{supplier_id}/terms`; caller identity and roles forwarded as today.

## Removed

`GET|PUT /api/product-suppliers/{variant_id}/{supplier_id}/terms` (gateway and procurement), their matrix entries and the `OverrideView.variant_id` field in the web client.

## Schema

[override_terms_view.v1.schema.json](override_terms_view.v1.schema.json)
