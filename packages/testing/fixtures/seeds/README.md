# Synthetic seed-import fixtures

Every value here is made up (variant ids 9001 to 9005, "Hoja sintética"). Binary and hostile files
(XLSX, macro workbook, wrong signature, oversized, formula cells, decompression bomb) are generated at
test time by `seed_fixtures` (`packages/testing/src/seed_fixtures/`), so no malware-like file is committed.
Never copy real exports into this directory.
