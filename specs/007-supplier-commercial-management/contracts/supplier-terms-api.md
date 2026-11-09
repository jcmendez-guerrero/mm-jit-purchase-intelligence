# Contract: Supplier terms API changes

Existing endpoints stay as implemented in `services/procurement-service/src/api/terms.py` and `suppliers.py`. This feature changes only what is listed here; schemas go to `packages/contracts` first and are negotiated with Agent 00 (FR-033).

## Unchanged (verified, not modified)

| Method | Path | Notes |
|---|---|---|
| GET | `/suppliers/{id}/terms` | history, version in force, planned versions |
| PUT | `/suppliers/{id}/terms` | `If-Match: <version>`; 428 when missing after first save; 412 with current version on stale |
| GET/PUT | `/product-suppliers/{variant}/{supplier}/terms` | override versions, same preconditions |
| POST/PATCH | `/suppliers`, `/suppliers/{id}` | PATCH needs `If-Match` |
| POST | `/suppliers/{id}/deactivate` / `reactivate` | |
| PUT/DELETE | `/suppliers/{id}/links/{sku}` | SKU in the path, never an ERP id |
| POST | `/suppliers/{id}/links/bulk/preview` / `apply` | |

## Changed

### `Idempotency-Key` request header (optional) on both terms PUTs

- Same key + same body: `200`/`201` with the original response (`version` unchanged), header `Idempotent-Replay: true`.
- Same key + different body or target: `422`, code `idempotency_key_reuse`.
- Key longer than 120 characters or with control characters: `422`, code `invalid_idempotency_key`.
- No key: current behaviour.

### New error codes (add to `packages/contracts/errors/error_codes.json`, Spanish text in `es-ES.json`)

| Code | HTTP | When |
|---|---|---|
| `idempotency_key_reuse` | 422 | key replayed with different content |
| `invalid_idempotency_key` | 422 | malformed key |
| `fx_rate_missing` | n/a (review item code) | non-EUR supplier with no stored or no ECB-published rate |
| `fx_rate_stale` | n/a (review item code) | stored rate older than 7 days |

## Outbound dependency (not an HTTP API of this service)

The rate job performs `GET https://api.frankfurter.dev/v2/providers/ecb/rates` (base EUR) once a day. Host, path and method are fixed; no query value comes from user input; no credentials and no business data are sent.

### Refusals are audited

Every 403, 412, 422 and 428 on the endpoints above appends an audit entry (`*.refused`) with actor, target, code and status. No response shape changes.

### Proposal line explanation (read-only addition, if absent)

`explanation.terms.expected_delivery_date` (ISO date) derived per data-model; additive, optional field.

## Not changed

No BFF route is added; the BFF forwards `Idempotency-Key` unchanged. No ERP-facing contract (allowlist) is touched.
