# Seed import template and validation rules (synthetic example values only)

> Updated by MMI-7 (`specs/008-mmi-7-predictive-seed-import/contracts/seed-governance.delta.md`): the product column is now **SKU**; users never supply the ERP variant id. A file that supplies only `variant_id` has every row rejected with `import_sku_required`. The table below shows the current layout.

Downloadable as CSV (UTF-8, `;` or `,` auto-detected, decimal comma accepted) and XLSX (first sheet, no macros). Headers are Spanish; the wizard maps any header to the canonical field.

| Canonical field | Spanish header | Required | Rule |
|---|---|---|---|
| sku | SKU | Yes | Resolved to a product through the synchronised catalogue; unknown SKUs (`import_unknown_sku`) and SKUs that match more than one product (`import_ambiguous_sku`) go to quarantine |
| day | Fecha | Yes | ISO or dd/mm/aaaa; between 2015-01-01 and 18 months ahead; DST-ambiguous local times quarantined |
| quantity | Cantidad | Yes | Number ≥ 0; non-numeric or negative rejected |
| warehouse | Almacén | No | Must match a live warehouse if given |
| kind | Tipo de dato | Yes | observado_externo / estimado / previsión_manual |
| provenance | Origen | Yes | Free label of the source (no personal data) |
| origin | Sintético/Real | Yes | One value per file; mixed files refused |

Whole-file rules: size cap (default 5 MB), row cap, no formulas executed (cells starting with `=`, `+`, `-`, `@` are treated as text and neutralised on output), duplicate (SKU, day, kind) rejected; ERP export files are refused (`import_erp_export_refused`), duplicate file checksum flagged, free-text columns such as notes are ignored and never stored, supplier tax identifiers are dropped.
Example rows use made-up SKUs such as `EJ-0001` and `2026-01-05`; never copy real data into this repository.
