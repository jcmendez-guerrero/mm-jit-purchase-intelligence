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

## Writer (`siweb-cost-writer`) — one operation

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

## Explicitly refused (non-exhaustive)

Stock adjustments, transfers and infinite-stock operations; variant pricing `PUT`; any `POST/PUT/PATCH/DELETE` on purchases, invoices, tickets, contacts; any `DELETE`; any path outside the lists above.
