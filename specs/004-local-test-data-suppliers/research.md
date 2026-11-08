# Research: MMI 004 — Local Test Data and Supplier Management

Observations below come from profiling the owner's three current exports locally (column layouts, enumerations, counts, shapes). No values from them are stored in this repository.

## Observed facts (shape only)

| Export | Facts that drive the design |
|---|---|
| Inventory CSV | 22 columns; ≈ 2,935 data rows with multi-line description cells; every SKU unique; `Tipo` = physical (≈ 2,924) or service (11); `Estado` all active; currency EUR; tax kinds IVA / IVA10 / IVA21 with rates 10 and 21; `Impuesto Incluido` yes/no per row; `Lote` empty on ≈ 84% of rows; **`Proveedor` empty on every row**; BOM-prefixed UTF-8; decimal point in prices |
| Movements XLSX | one sheet "Datos", 12 columns, ≈ 1,695 rows, 01/07/2026 – 31/10/2026; `Fecha` is **text** `dd/mm/yyyy, HH:MM`; quantities are integers (outbound negative); lot empty on ≈ 14%; warehouse never empty; 8 distinct (Tipo, Motivo) pairs seen |
| Suppliers CSV | 41 columns; ≈ 57 rows; first column `ID` (ERP contact number); `Tipo Relación` supplier or customer; many rows are expense vendors (utilities, software, telecoms); some rows have no tax ID; a few foreign suppliers with USD; free-text `Notas` present on at least one row and containing personal information |

## Decisions

### R1 — Product identity locally: SKU → stable surrogate IDs

- **Decision**: the loader assigns each SKU a persistent integer from a reserved range (starting at 9,000,000) and uses it as `variant_id`/`product_id` in the Siweb-shaped payloads. The map is stored in the gitignored loader state folder, so reloads and later loads never renumber. SKU stays the user-visible identifier and is unique per variant; screens search and export by SKU.
- **Rationale**: every service keys on integer `variant_id`; changing keys would touch all schemas and contracts. A reserved range cannot collide with real ERP IDs. When real ERP data arrives, SKU is the matching key and the surrogate is replaced.
- **Alternatives**: hash of SKU (collision risk, not reversible), SKU as primary key (rewrites every schema), UUID (not stable across wipes).

### R1a — SKU for people, ERP ids for the API

- **Decision**: SKU is the only product identifier users see or provide. ERP ids (`variant_id`, `product_id`, `contact_id`) are resolved from the SKU through the synced catalogue at the moment an API call is built (existing `services/procurement-service/src/costs/directory.py` is the starting point). Every client that builds ERP requests (connector reader, cost writer, note writer) rejects ids from the reserved local range, so a locally loaded product can never reach the ERP.
- **Consequence**: cost updates and the note block stay `pending_link` for locally loaded products and for imported suppliers whose contact id is unverified (G0-L1).

### R2 — How data enters: through the mock and the existing connector

- **Decision**: parse exports into the mock's `Dataset` (warehouses, products, variants, stock, lots, movements) and let the unchanged connector sync, reconcile and publish events.
- **Rationale**: exercises the real pipeline (reconciliation counts, quarantine, demand rules, backward stock reconstruction); no second write path into `inventory`; keeps "no cross-schema SQL".
- **Alternatives**: write directly to the inventory schema (bypasses the quality gates being tested), a new import endpoint in inventory-service (would exist in cloud).

### R3 — Upload hardening

- **Decision**: the loader re-implements the same checks the seed import applies (extension, declared type, signature, size, row limit, decompression ratio, no macros / external links / formulas) with a parity test against the seed import's cases; limits come from the same environment variables.
- **Rationale**: the loader may not import service code (it is a separate local package); a later task can extract a shared module.
- **Alternatives**: import from `forecast-service` (cross-service dependency), skip hardening locally (the screen upload is still a file entry point).

### R4 — Movement type/reason mapping

- **Decision**: a versioned mapping table in `formats.py`, keyed by the pair (Tipo, Motivo) after trimming and case/accent folding. Seen pairs map as follows; any other pair goes to the review list until added.

| Tipo / Motivo (export) | Platform reason |
|---|---|
| Entrada / Recepción de compra | `purchase_receipt` |
| Salida / Envío de venta | `sale_shipment` |
| Entrada / Devolución de cliente | `return_customer` |
| Ajuste / Ajuste negativo | `adjustment_negative` |
| Ajuste / Ajuste positivo | `adjustment_positive` |
| Entrada / Stock inicial | `initial_stock` |
| Transferencia / Entrada por transferencia | `transfer_in` |
| Transferencia / Salida por transferencia | `transfer_out` |

  Confirmed 2026-11-08 (T007): every platform reason in this table already exists in the generator's reason list (`packages/testing/src/generator/dataset.py` `REASONS`) and in the connector's movement mapping; no enum change is needed. Reasons not yet seen in the owner's data (damage, theft, expiry, count, production, supplier return) have candidate Spanish labels listed but flagged "unverified"; they are treated as unmapped.

- **Rationale**: honours "never guess"; the constitution's loss-classification cutover still applies.

### R5 — Timestamps

- **Decision**: parse `dd/mm/yyyy, HH:MM` as Europe/Madrid local time, store UTC plus the original text; an ambiguous or non-existent local time (clock change) goes to review. Expiry `dd/mm/yyyy`; malformed (e.g. 3-digit year) goes to review, never stored.

### R6 — Price and tax interpretation

- **Decision**: keep price and cost as given with the row's "tax included" flag and rate; compute a normalised tax-inclusive PVP for the margin check; show the interpretation in the load summary for the owner to confirm once (spec assumption). Cost is treated as net unless the flag says otherwise, and Recargo rules follow the existing cost module.
- **Alternatives**: assume all tax-included (wrong for most rows in the current export).

### R7 — Supplier ERP reference

- **Decision**: the supplier export's `ID` column is stored as `external_contact_id`. **Assumption to verify (Gate 0, G0-L1)**: it equals the API `contact_id`. Until verified, imported suppliers are marked "ERP reference unverified" and cost writes stay blocked for them.
- **Rationale**: avoids a second identifier and lets cost writes target the right contact later.

### R8 — Supplier linking when the file has no supplier

- **Decision**: product-supplier links cannot come from the inventory file (empty column). Provide (a) automatic exact-match linking when a name is present (FR-033), and (b) a bulk assignment tool: filter or selection, or a two-column SKU/supplier file, with a preview and audit (FR-035). Cost on a new link defaults from the product's export cost with source `inventory_export`.
- **Alternatives**: infer suppliers from purchase-receipt movements (they carry no supplier), one-by-one linking of ≈ 3,000 products.

### R9 — Services and inactive items

- **Decision**: `Tipo` = service is loaded with a flag and excluded from stock, demand, forecasting and proposals (FR-036); inactive status is kept and shown.

### R10 — Reload and edit protection (FR-034)

- **Decision**: the loader stores the value it last wrote for each protected field (cost, reorder point, target stock). On reload it writes a field only if the app's current value still equals that last-written value, otherwise it records a difference for the buyer to accept or ignore. Stock quantities and descriptive fields are always overwritten.
- **Risk**: needs read access to current app values through service APIs; if an API cannot return a field, that field is treated as protected and listed.

### R11 — Keeping the loader out of the cloud (three layers)

1. **Not packaged**: the loader lives in `packages/testing`, which no cloud Dockerfile copies; an infra test asserts no cloud image or Bicep file references it.
2. **Not mounted**: the BFF `local-load` router is registered only when `MMI_LOCAL_LOADER=1` and `MMI_ENV` is not prod/staging; otherwise requests get 404 and a security event is recorded.
3. **Not reachable**: the override file `infra/compose.local-data.yaml` is the only place the loader service and the flag are defined; Bicep and deployment workflows contain no reference; a test fails the build if one appears.

### R12 — Repository safeguard against real exports

- **Decision**: `scripts/check_export_signatures.py` (pre-commit and CI) detects the three header signatures in any tracked or staged CSV/XLSX; a match is allowed only under `packages/testing/fixtures/exports/` and only if every SKU starts with `SYN-` and every supplier ID is in a reserved synthetic range. Existing ignore rules (`*.csv`, `*.xlsx`, `/data/`) stay.
- **Rationale**: the export headers are fixed, so a signature check is cheap and reliable; the synthetic marker makes the allow-case unambiguous.

### R13 — Conditions storage and the ERP note block

- **Decision**: reuse the existing versioned `supplier_terms` (minimums, delivery threshold, charge, order days, lead time) and `product_supplier_terms`. Payment terms in days and currency are added to the supplier. The note block (format in `contracts/supplier-note-block.md`) is generated from the current terms; merge logic is implemented and tested with no network path.
- **Evidence from earlier verification (research V4)**: the ERP's supplier PUT ignores lead time and minimum order, which confirms they cannot be stored in structured fields there.
- **Gate 0 additions**: G0-N1 which operation/field carries the supplier (contact) note; G0-N2 whether a read-merge-write round trip preserves all other characters (including line breaks and non-ASCII); G0-N3 note length limit; G0-L1 as in R7.

### R14 — Loader identities (Principle IV)

- **Decision**: the local dev issuer gains an audience `local-loader` and a service principal for the loader. The BFF forwards an audience-scoped token to the loader app; the loader uses its own principal when it calls inventory-service and procurement-service. Wrong audience, missing or expired tokens are refused.
- **Rationale**: keeps the constitution's rule for service-to-service access even in a local-only tool.

### R15 — Where review items live (FR-006)

- **Decision**: two labelled sources shown together in the data-quality screen. (a) Anything the Siweb-shaped payload can express is passed through, so the connector's normal quarantine handles it (malformed expiry kept as raw text, missing warehouse mapped to "unassigned", unreferenced sale). (b) Rows the payload cannot express (unmapped type/reason, unknown SKU, unreadable values) are kept in the loader's review store and served by `GET /local-load/review`. SC-002's invariant is checked over both.
- **Alternatives**: drop (b) rows (violates "never drop"), write them straight to the integration schema (cross-schema write).

### R16 — Export cost and selling price (FR-037)

- **Decision**: the loader pushes `(sku, export_cost, pvp_gross, tax_rate, loaded_at)` to procurement's `export_costs` table through an internal, flag-guarded endpoint. `export_costs` is a reference refreshed on every load; link creation defaults the link cost from it with source `inventory_export`; edited link costs are never overwritten (FR-034). For the margin check the selling price travels as each variant's `price_cents` (normalised, tax-inclusive), which is the source inventory-service's `/pvp` already serves to `costs/pvp.py`; no movement is stamped with a price.
- **Alternatives**: store cost on a product-level field (the ERP keeps one cost per supplier, not per product), keep cost only in loader state (procurement would depend on a local tool).

### R17 — No mixing of local and ERP data (FR-038)

- **Decision**: the connector checks, before any sync against a non-mock host, whether reserved-range ids exist and refuses with a stable error code. `wipe` clears them. SKU rebinding is deferred to a follow-up feature.
- **Rationale**: silently mixing surrogate and real ids would corrupt demand history.

## Open items carried to Gate 0

| Id | Question | Blocks |
|---|---|---|
| G0-L1 | Does the CSV `ID` equal the API contact id? | Cost writes for imported suppliers |
| G0-N1 | Which ERP operation and field hold the supplier note? | FR-027 to FR-032 enablement |
| G0-N2 | Does a read-merge-write round trip preserve foreign note content exactly? | FR-028 |
| G0-N3 | Maximum note length and character handling? | Block size budget |
| G0-M1 | Time zone and seconds handling of UI-exported movement timestamps (assumed Europe/Madrid, minute precision) | Backward stock reconstruction accuracy |

## Post-design constitution re-check

All gates in plan.md still pass: the design adds no cloud resource, no new write (note block disabled), keeps real data local with three independent absence layers, and keeps every supplier or link change versioned and audited.
