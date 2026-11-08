# Data Model: MMI 004

Only changes and additions. Conventions of the main data model apply (UUID ids, UTC timestamps, money as `NUMERIC(18,4)` with currency, audit hash chain).

## Schema `procurement` (migration 0011, owned by procurement-service)

### `suppliers` (extended)

| Column | Type | Rule |
|---|---|---|
| external_contact_id | int, nullable, unique | ERP contact number; null for platform-created suppliers |
| name | text | Commercial name; `name_key` below drives duplicate detection |
| name_key | text, indexed | Lower-cased, accent-folded, whitespace-collapsed name; warning on duplicate, never unique |
| status | `active` \| `deactivated` | Deactivation keeps history; reactivation allowed |
| classification | `purchasing` \| `non_purchasing` \| `unclassified` | Non-purchasing and deactivated suppliers are never proposed |
| origin | `platform` \| `imported` \| `erp` | |
| erp_link_state | `none` \| `unverified` \| `linked` \| `pending_link` | `unverified` until Gate 0 G0-L1; no ERP request for `none`/`pending_link` |
| fiscal_type | `national` \| `intracommunity` \| `foreign` | |
| country | ISO 3166 alpha-2 | |
| currency | ISO 4217 | Default EUR; costs in another currency are never mixed without explicit conversion |
| payment_terms_days | int, nullable | Parsed from free form only when unambiguous, else null + review item |
| order_channel | `email` \| `phone` \| `web` \| `other` | No contact details stored beyond what the buyer enters |
| has_note | bool | Free-text notes are never stored |
| created_by / created_at / updated_by / updated_at / version | | Optimistic concurrency on `version` |
| deactivated_by / deactivated_at | | |

Never stored: tax ID, bank, IBAN, SWIFT, billing address, free-text notes, emergency or personal contact fields.

### `supplier_terms` and `product_supplier_terms` (existing, reused)

Lead time, minimum order value/quantity, free-delivery threshold, delivery charge, order days, delivery schedule and pack/multiple stay in the existing versioned tables (effective-dated, `If-Match` concurrency). No structural change; the UI and API now reach them for suppliers created in the platform.

### `supplier_costs.source` (extended enum)

Adds `inventory_export` to `siweb_product_supplier`, `csv_price_list`, `manual`. Same immutability and provenance rules; the load time is the verification time.

### `supplier_review_items` (new)

| Column | Rule |
|---|---|
| id, kind (`possible_duplicate`, `payment_terms_unparsed`, `link_no_match`, `link_ambiguous`, `link_inactive_supplier`, `currency_mismatch`), supplier_id nullable, detail (no PII), status (`open`/`resolved`/`ignored`), resolved_by, resolved_at | Review list shown with the existing data-quality screens |

### `link_assignment_batches` (new)

| Column | Rule |
|---|---|
| id, created_by, created_at, criteria (JSON: filter, selection, or file reference hash), supplier_id, products_matched, products_changed, conflicts, status (`previewed`/`applied`/`cancelled`), applied_at | A batch is applied only after a preview; each change is also an audit event |

### `export_costs` (new)

| Column | Rule |
|---|---|
| sku (unique), export_cost (NUMERIC, nullable), pvp_gross (NUMERIC, nullable), tax_rate, tax_included (bool), currency, loaded_at, load_run_id | Reference values from the inventory export; refreshed every load; used as default link cost (source `inventory_export`) and as the selling price for the margin check; not a supplier cost and never written to the ERP |

### `supplier_conditions_sync` (new, phase 7, disabled)

| Column | Rule |
|---|---|
| supplier_id, block_version, desired_hash, last_written_hash, state (`in_sync`/`pending`/`discrepancy`/`failed`/`pending_link`), last_checked_at, detail (no note content) | Holds hashes and states only, never note text |

## Schema `inventory` and `integration`

No structural change. Locally loaded products enter through the existing sync with surrogate integer ids from the reserved range; `variants.sku` is already stored and gains a uniqueness check at the application level (collisions go to review). Service items carry an `is_service` flag (existing `products` row attribute added in an inventory migration only if no equivalent exists; to confirm in tasks).

## Loader state (local files, gitignored, not a database)

| File | Content | Rule |
|---|---|---|
| `data/local-exports/.sku-map.json` | SKU → surrogate id | Append-only; wiped by `wipe` |
| `data/local-exports/.last-load.json` | per-field last-written values for protected fields (FR-034), load counts, review items | No notes, no tax IDs |
| `data/local-exports/*.csv` or `*.xlsx` | the owner's real exports | Never committed; never read by tests |

## State transitions

```text
supplier:  active ⇄ deactivated        (deactivation: preview of open proposal lines, confirm)
classification: unclassified → purchasing | non_purchasing (buyer/admin; reversible)
erp_link_state: none → pending_link (cost entered) → linked (Gate 0 / ERP link exists)
                unverified → linked (after G0-L1 verification)
conditions sync (disabled): in_sync → pending → in_sync | discrepancy → (buyer decision) → pending/in_sync
```
