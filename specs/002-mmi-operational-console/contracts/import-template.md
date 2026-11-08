# Seed import template and validation rules (synthetic example values only)

Downloadable as CSV (UTF-8, `;` or `,` auto-detected, decimal comma accepted) and XLSX (first sheet, no macros). Headers are Spanish; the wizard maps any header to the canonical field.

| Canonical field | Spanish header | Required | Rule |
|---|---|---|---|
| variant_id | ID de variante Siweb | Yes (or SKU) | Must match an existing variant; unmatched rows rejected |
| sku | SKU | If no variant_id | Attribute only; ambiguous matches go to quarantine |
| day | Fecha | Yes | ISO or dd/mm/aaaa; between 2015-01-01 and 18 months ahead; DST-ambiguous local times quarantined |
| quantity | Cantidad | Yes | Number ≥ 0; non-numeric or negative rejected |
| warehouse | Almacén | No | Must match a live warehouse if given |
| kind | Tipo de dato | Yes | observado_externo / estimado / previsión_manual |
| provenance | Origen | Yes | Free label of the source (no personal data) |
| origin | Sintético/Real | Yes | One value per file; mixed files refused |

Whole-file rules: size cap (default 5 MB), row cap, no formulas executed (cells starting with `=`, `+`, `-`, `@` are treated as text and neutralised on output), duplicate (variant, day, kind) rejected, duplicate file checksum flagged, free-text columns such as notes are ignored and never stored, supplier tax identifiers are dropped.
Example rows use made-up IDs such as `variant 9001` and `2026-01-05`; never copy real data into this repository.
