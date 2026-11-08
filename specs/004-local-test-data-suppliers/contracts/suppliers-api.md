# Contract: Supplier Management API (BFF-facing, es-ES messages)

Schemas live in `packages/contracts` first. Roles: `viewer` read; `buyer`, `admin` write. Updates use `If-Match` on `version` (428 if missing, 412 with the current version if stale), as for terms.

## Suppliers

| Method | Path | Purpose |
|---|---|---|
| GET | `/suppliers` | List with status, classification, origin, `erp_link_state`, conditions summary; filters `status`, `classification`, `q`; paging |
| POST | `/suppliers` | Create (required: name, fiscal_type, country, currency); duplicate name → 409 `supplier_possible_duplicate` unless `confirm_duplicate=true` |
| GET | `/suppliers/{id}` | Detail incl. current terms and history pointers |
| PATCH | `/suppliers/{id}` | Edit commercial fields, payment terms, classification, order channel |
| POST | `/suppliers/{id}/deactivate` | Body `{confirm: false}` returns `{open_proposal_lines: n, lines: [...]}`; with `confirm: true` deactivates and flags those lines for reallocation |
| POST | `/suppliers/{id}/reactivate` | |
| GET/PUT | `/suppliers/{id}/terms` | Existing versioned terms (lead time, minimums, free-delivery threshold, delivery charge, order days) |
| GET | `/suppliers/review-items` | Duplicates, unparsed terms, link problems |
| POST | `/suppliers/review-items/{id}/resolve` | `merge_into`, `keep_both`, `ignore` (merge is explicit and audited) |

## Product-supplier links

| Method | Path | Purpose |
|---|---|---|
| GET | `/suppliers/{id}/links` | Linked products by SKU with cost, source, verification, pack multiple, minimum quantity, rank |
| PUT | `/suppliers/{id}/links/{sku}` | Create or update a link (cost with Recargo option, pack, min qty, reference, rank); follows existing cost provenance; a platform-only supplier yields `pending_link` and no ERP request |
| DELETE | `/suppliers/{id}/links/{sku}` | Remove link (history kept) |
| POST | `/suppliers/{id}/links/bulk/preview` | Body: `filter` (category, brand, `q` on SKU/name) or `skus[]` or `file_id`; returns counts of matched, new, existing, conflicting (other supplier already preferred) |
| POST | `/suppliers/{id}/links/bulk/apply` | Body: `batch_id` from a preview (must be the latest preview, ≤ 15 minutes old); audited per product |
| POST | `/links/bulk/file` | Upload two-column SKU / supplier-name file (same limits); returns a `file_id` and a validation result |

## Supplier file import (local loader path)

Handled by the loader through the procurement service's internal import endpoint `POST /internal/suppliers/import` (service identity, available only when the local flag is set). It applies the same validation as `POST /suppliers` row by row and returns counts and review items.

## Errors (stable codes)

`supplier_not_found`, `supplier_possible_duplicate`, `supplier_version_conflict`, `supplier_deactivated`, `supplier_non_purchasing`, `link_sku_unknown`, `link_cost_invalid`, `link_currency_mismatch`, `bulk_preview_stale`, `bulk_conflicts_unresolved`, `terms_invalid`.
