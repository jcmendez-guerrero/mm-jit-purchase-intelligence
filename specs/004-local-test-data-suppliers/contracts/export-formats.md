# Contract: Export Formats (local loader input)

Header signatures are exact (after trimming and BOM removal). A file whose signature does not match is rejected with a Spanish message listing missing and unexpected columns. Real files live only in `data/local-exports/`; committed files live only in `packages/testing/fixtures/exports/` and use `SYN-` SKUs.

## Inventory CSV (UTF-8 with BOM, comma separated, quoted multi-line cells)

`SKU, Nombre, Descripción, Categoría, Marca, Proveedor, Tipo, Unidad de Medida, Categoría Unidad, Precio Venta (€), Precio Coste (€), Tipo Impuesto, Tasa Impuesto (%), Impuesto Incluido, Stock Disponible, Stock Reservado, Stock Total, Punto de Reorden, Stock Objetivo, Moneda, Estado, Lote`

| Column | Maps to | Rule |
|---|---|---|
| SKU | variant.sku (identity) | Trimmed; case-preserved, matched case-insensitively; duplicates → one product per SKU, rows merged as lots; conflicting price/cost → review |
| Nombre, Categoría, Marca | name, category, brand | Descriptive; overwritten on reload |
| Descripción | — | Not stored (free text) |
| Proveedor | link request | Exact single match only (FR-033); empty is normal |
| Tipo | physical / service | Service → excluded from stock, demand, proposals |
| Unidad de Medida, Categoría Unidad | uom, uom category | |
| Precio Venta (€), Precio Coste (€) | PVP, export cost | Decimal point, Decimal type; negative or non-numeric → review |
| Tipo Impuesto, Tasa Impuesto (%), Impuesto Incluido | tax kind, rate, included flag | Per-row interpretation shown in the load summary |
| Stock Disponible / Reservado / Total | snapshot available / reserved / on-hand | Reserved > total → flagged, not corrected; negative → flagged |
| Punto de Reorden, Stock Objetivo | reorder point, target stock | Protected on reload if edited in the app |
| Moneda | currency | Non-EUR → review |
| Estado | active / inactive | Kept and shown |
| Lote | lot batch | Empty is normal; one lot per row |

## Movements XLSX (single sheet "Datos")

`Fecha, Producto, SKU, Almacén, Ubicación, Lote, Caducidad, Tipo, Motivo, Cantidad, Notas, Referencia`

| Column | Maps to | Rule |
|---|---|---|
| Fecha | created_at (UTC) + created_at_raw | Text `dd/mm/yyyy, HH:MM`, Europe/Madrid; invalid → review |
| Producto | — | Display only; SKU is the key; mismatch with catalogue name ignored |
| SKU | variant | Unknown SKU → review (never guessed) |
| Almacén, Ubicación | warehouse, location | Unknown warehouse → explicit "unassigned" + review |
| Lote, Caducidad | batch, expiry | Malformed expiry → review, never stored |
| Tipo + Motivo | movement reason | Mapping table in research R4; unmapped → review |
| Cantidad | signed quantity | Integer or decimal; sign must match the movement kind or → review |
| Notas | has_note | Text discarded |
| Referencia | reference_number | Used for sale/purchase matching |

Rejections: macros, external links, formulas, more than the configured row limit, more than one data sheet with the signature.

## Suppliers CSV (UTF-8 with BOM)

`ID, Nombre Empresa, CIF, Tipo Fiscal, Sector, Dirección, Ciudad, Provincia, Código Postal, País, Teléfono Principal, Email General, Página Web, Nombre Contacto, Apellidos Contacto, Cargo, Teléfono Directo, Email Directo, LinkedIn, Tipo Relación, Categoría, Fecha Alta, Último Contacto, Condiciones Pago, Métodos Pago, Moneda Habitual, Email Empresa, Email Personal, Teléfono Emergencia, Notas, Nombre Facturación, Dirección Facturación, Ciudad Facturación, Código Postal Facturación, Provincia Facturación, País Facturación, Banco, IBAN, SWIFT, Fecha Creación, Fecha Actualización`

| Column | Maps to | Rule |
|---|---|---|
| ID | external_contact_id | `unverified` until G0-L1; duplicates → review |
| Nombre Empresa | name | Duplicate detection by `name_key`; never auto-merged |
| Tipo Fiscal | fiscal_type | national / extranjero / intracomunitario |
| País | country | Spanish and English names accepted ("España", "Spain") |
| Moneda Habitual | currency | Empty → EUR |
| Condiciones Pago | payment_terms_days | "7 días", "30" parsed; anything else → review |
| Tipo Relación | exclusion | `Cliente` rows excluded and counted |
| Notas | has_note | Text discarded |
| CIF, Banco, IBAN, SWIFT, billing and personal contact columns, Sector, Categoría, dates | — | Dropped at parse time; never logged |
