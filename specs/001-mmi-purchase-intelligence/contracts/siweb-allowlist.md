# Siweb360 Outbound Allowlist Contract

Enforced in code **before** any request is built or sent. Anything not listed is refused, logged as a security event, and counted in metrics. Tests assert that every other (method, path) pair, every other host, and any redirect to another host is refused (constitution Principle I and Additional Constraints). Real hostnames and tokens are configuration; they are not stored in this repository.

## Reader (`siweb-connector`) — GET only

| Method | Path template | Purpose |
|---|---|---|
| GET | `/api/public/inventory/warehouses` | Warehouses |
| GET | `/api/public/inventory/products` | Active products |
| GET | `/api/public/inventory/products/{id}` | Product detail |
| GET | `/api/public/inventory/products/{id}/suppliers` | Supplier cost/lead time/MOQ (drop `supplier_cif`) |
| GET | `/api/public/inventory/variants` | Variants + stock totals |
| GET | `/api/public/inventory/variants/{id}` | Variant detail |
| GET | `/api/public/inventory/variants/{id}/stock` | Lot/expiry levels |
| GET | `/api/public/inventory/variants/{id}/lots` | Lots |
| GET | `/api/public/inventory/movements` | Movements (frozen `date_to`, `limit` ≤ 200) |
| GET | `/api/public/inventory/variants/{id}/movements` | Per-variant movements |
| GET | `/api/public/purchases`, `/api/public/purchases/{id}` | Reconciliation only, if needed later |

Controls: host allowlist (single approved Siweb host), token from Key Vault via the reader identity, token bucket ≤ 500 req/h (shared-limit share), night window for heavy jobs, `date_to` frozen per run, dedupe by movement `id`.

## Writer (`siweb-cost-writer`) — two operations (constitution v1.3.0)

Operation 1 is the supplier-cost update below. Operation 2, the supplier-conditions note block, is described in the section after the cost-update checks and stays **disabled** until Gate 0 confirms its exact operation and field.

### Operation 1: supplier cost

| Method | Path template | Body (schema-validated) |
|---|---|---|
| PUT | `/api/public/inventory/products/{id}/suppliers/{contact_id}` | Existing supplier record with **only** `purchase_cost_cents` changed (read-modify-write; see research R4/V4) |

Preconditions (all must hold or the call is not made):

1. A `cost_write_request` exists in status `approved_by_buyer` (re-verified against procurement-service through the service identity), triggered by `missing_cost` or `order_confirmed`.
2. The value is the cost **including recargo**, rounded per the documented rule, and differs from the current Siweb value read immediately before the call.
3. The current Siweb record for the pair exists (known `contact_id` from the reader's supplier rows); no other field changes. If no record exists, no call is made: the request moves to `pending_link` and the buyer creates the link in the ERP. Creating a link through this PUT is out of scope unless open item V4 proves it works and the decision is recorded (with a constitution review).
3a. The buyer's release carried fresh step-up MFA (auth_time within 5 minutes), re-verified by procurement-service.
4. Writer identity holds the only write-capable access policy; the reader identity cannot reach this code path.

After the call: `GET .../suppliers` verifies the new value; outcome, previous/new value, actor reference and timestamp go to the hash-chained writer audit; failures stay visible and retry with bounded backoff; any attempted write without a matching buyer-approved request raises an alert.

### Operation 2: supplier-conditions note block (disabled until Gate 0)

| Method | Path template | Body (schema-validated) |
|---|---|---|
| TBD in Gate 0 | TBD in Gate 0 (the ERP operation and field that carry the supplier note) | Existing record with **only** the note changed, and within the note **only** the application's delimited block |

The row above is a placeholder: no request of this kind is built or sent while the path is `TBD`, and the allowlist code MUST fail closed. Enabling it requires recording the confirmed operation here, a non-production verification (same gate as T135), and a contract test.

Preconditions (all must hold or the call is not made):

1. A `supplier_conditions_write_request` exists in status `approved_by_reviewer` (buyer or admin; re-verified against procurement-service through the service identity). The values come from the application's versioned supplier conditions (lead time, minimum order value/quantity, free-delivery threshold, delivery charge, order days).
2. The buyer's or admin's release carried fresh step-up MFA (auth_time within 5 minutes), re-verified by procurement-service.
3. One supplier per request; any other target is refused.
4. Read-merge-write: the current note is read immediately before the call; only the block between the application's markers is replaced (or appended if absent); every character outside the block is byte-identical. If the markers are damaged or duplicated, or the note changed between the read and the write, no call is made and a review item is raised.
5. Note content outside the block is held in memory only for the duration of the call; it is never stored, logged, displayed or used in decisions (only a `has_note` flag is kept). The block's contents are read only to detect discrepancies with the application's values.
6. Writer identity holds the only write-capable access policy; the reader identity cannot reach this code path.

After the call: the note is re-read to verify the block; outcome, previous/new block, actor reference and timestamp go to the hash-chained writer audit; failures stay visible and retry with bounded backoff. A discrepancy found later raises an alert for the buyer or admin to resolve; nothing is overwritten automatically.

## Explicitly refused (non-exhaustive)

Stock adjustments, transfers and infinite-stock operations; variant pricing `PUT`; any `POST/PUT/PATCH/DELETE` on purchases, invoices, tickets, contacts (except Operation 2 once enabled by Gate 0); any `DELETE`; any path outside the lists above.
