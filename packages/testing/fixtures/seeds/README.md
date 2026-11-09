# Synthetic seed-import fixtures

Every value here is made up: fictional SKUs `EJ-9001` to `EJ-9005` (the layout of the downloadable template) and "Hoja sintética".
`valid.csv`, `partly_invalid.csv` and `mixed_origin.csv` are the three static files; the test series sources expose the matching SKU
`EJ-<variant id>` for each variant, so a file maps to products exactly as it does in the application.

Binary and hostile files (XLSX, macro workbook, workbook with external links, wrong signature, oversized, formula cells,
decompression bomb) are generated at test time by `seed_fixtures` (`packages/testing/src/seed_fixtures/`), so no malware-like
file is committed. Never copy real exports into this directory.
