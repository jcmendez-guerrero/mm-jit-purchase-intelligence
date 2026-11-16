# Data Model: SKU Route for Product-Supplier Overrides

No new tables, columns or migrations.

| Thing | Change |
|-------|--------|
| Override history (procurement) | None. Still keyed by `variant_id` + `supplier_id`. |
| `product_refs` (`sku`, `variant_id`) | Read-only lookup by SKU (trimmed, case-insensitive). |
| Idempotency record | None. Scope `product_supplier_terms`, target `variant_id:supplier_id` (internal). |
| Change event | None. Key `variant_id:supplier_id` (internal). |
| Audit entries (saved, refused) | Entity id becomes `<sku>:<supplier_id>`. Entries already written keep their old text. |
| **OverrideTermsView** (response, new) | `sku`, `supplier_id`, `version`, `override` (nullable), `history[]`, `effective{}`. No `variant_id`. |

**Validation rules**: SKU must resolve to exactly one product (else `sku_unknown` / `sku_ambiguous`, 422); NUL byte refused by the shared guard (`invalid_input`); all other validation (terms values, dates, `If-Match` 428/412, idempotency 422) is unchanged.

**State**: unchanged; each save appends a version.
