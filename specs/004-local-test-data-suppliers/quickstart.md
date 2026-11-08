# Quickstart: Validation Scenarios — MMI 004

Local only. Synthetic data unless you deliberately load your own files from the ignored folder.

## 0. Prerequisites

Docker with Compose, Python 3.12, Node 20+. No Azure, Siweb or Entra credentials.

## 1. Generate and check the synthetic exports (US4)

```bash
python -m generator.exports --seed 42 --out packages/testing/fixtures/exports
python scripts/check_export_signatures.py
```

Expected: three files in export format with `SYN-` SKUs; the same seed gives identical bytes; the guard passes. Copy any real-shaped file elsewhere in the repo and the guard fails.

## 2. Start the stack with the loader

```bash
docker compose -f infra/compose.yaml -f infra/compose.local-data.yaml up --build
```

Expected: services healthy; the Suppliers and "Carga local" screens visible in the SPA (local flag on).

## 3. Load inventory, stock and movements (US1)

```bash
python -m export_loader check --dir packages/testing/fixtures/exports
python -m export_loader load  --dir packages/testing/fixtures/exports
```

Expected: `loaded + updated + unchanged + quarantined + excluded + services == rows` for each file; dashboard populated; quarantined rows (unknown SKU, malformed expiry, unmapped reason) listed with reasons; second run reports zero new rows.

Verified 2026-11-08 (T027, T039): with the compose override running, `RUN_LOCAL_LOAD_E2E=1 pytest infra/tests/test_local_load_e2e.py` loads the committed synthetic set through the command, the connector collects it, inventory-service holds the loaded movements and stock snapshots, and a second load changes nothing (about 2.5 minutes including image builds).

## 4. Suppliers (US2, US3)

In the SPA (buyer): create a supplier, set conditions, link two products by SKU, bulk-assign a supplier to a category after the preview, deactivate and see affected lines. Load the synthetic suppliers file: customers excluded, duplicate-looking names listed, non-EUR kept, payment terms parsed.

Expected: proposals honour minimums and multiples and never use deactivated or non-purchasing suppliers.

Verified 2026-11-08 (T056): the supplier screens and API are covered by unit, API and browser tests. SC-004: creating a supplier, setting a cost and linking a product takes three short forms (no wizard). SC-005: `services/procurement-service/tests/test_allocation_excludes_suppliers.py` shows a deactivated or non-purchasing supplier never receives a proposal line, and `test_supplier_merge.py` / `test_suppliers_service.py` cover the audit trail.

Known limits of this slice: a link stores cost, pack multiple and minimum quantity, but not a supplier product reference or a rank (the cost tables have no place for them); bulk assignment selects by SKU list, free text on SKU or name, or a two-column file, not by category or brand (procurement does not hold those).

Supplier file (US3, verified 2026-11-08): load the suppliers export first (`export_loader load` does this order by itself, and the "Carga local" screen lists it first). Customers are excluded; every other row becomes an imported supplier with `erp_link_state = unverified` (the contact number is only trusted as the API's contact id after Gate 0, G0-L1), so cost writes for it stay pending. Obvious expense vendors (energy, insurance, telecoms, software, hosting, advisers) arrive as "sin compras"; the rest arrive "sin clasificar" and can still be proposed until the buyer classifies them in "Proveedores importados por clasificar". Look-alike names are both kept and listed for review; payment terms such as "a convenir" are left empty and listed. When the inventory file names a supplier, the product is linked only on an exact single match; anything else goes to the review list. Re-loading never overwrites what the buyer edited.

## 5. Your own files (optional, stays on your machine)

```bash
mkdir -p data/local-exports   # ignored by version control
# copy your three exports here, then:
python -m export_loader check --dir data/local-exports
python -m export_loader load  --dir data/local-exports
python -m export_loader wipe   # when finished
```

Expected: counts only are printed; nothing leaves the machine; `git status` shows no new tracked file.

## 6. Cloud absence (US4)

```bash
pytest infra/tests/test_no_local_loader_in_cloud.py
MMI_ENV=prod pytest services/api-bff/tests -k local_load_disabled
```

Expected: no cloud image, Bicep or workflow references the loader; BFF `local-load` routes answer 404 and record a security event when not local.

## 7. Note block (phase 7, disabled)

```bash
pytest services/siweb-cost-writer/tests -k note_block
pytest services/siweb-connector/tests/contract -k allowlist
```

Expected: merge and refusal properties hold; the allowlist still allows only the cost update; the note operation builds no request while its path is `TBD`.
