# Tasks: MMI 004 — Local Test Data Loading and Supplier Management

**Input**: Design documents in `/specs/004-local-test-data-suppliers/` (plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md); constitution v1.3.0.

**Tests**: Included. The project rule is tests before implementation within a story; test tasks come first in each phase and must fail before the matching implementation.

**Rules that apply to every task**: synthetic data only in the repository (fixtures use `SYN-` SKUs); never read `data/local-exports/` from tests; money is `Decimal`; UI text only through `apps/web/src/i18n/es-ES.json`; schema changes in `packages/contracts` first; each service touches only its own schema.

## Format: `- [ ] T### [P?] [Story?] Description with file path`

IDs are stable labels, not execution order: T089–T110 were added after the consistency analysis and sit in the phase where they belong. The phase order and the dependencies section govern execution.

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[US1]** local load of inventory, stock and movements · **[US2]** supplier management · **[US3]** supplier import · **[US4]** safe fixtures and local-only guarantee

---

## Phase 1: Setup

- [X] T001 Extend `.gitignore` so `data/local-exports/` (including `.sku-map.json` and `.last-load.json`) and any `*.xlsx`/`*.csv` outside `packages/testing/fixtures/` stay ignored; add a comment pointing to `specs/004-local-test-data-suppliers/contracts/local-loader.md`
- [X] T002 [P] Create the loader package skeleton `packages/testing/src/export_loader/__init__.py` and register it (and the `export_loader` module entry point) in `packages/testing/pyproject.toml`
- [X] T003 [P] Create `infra/compose.local-data.yaml`, an override file used as `-f infra/compose.yaml -f infra/compose.local-data.yaml`, that defines the `local-loader` service (built from `packages/testing/Dockerfile`, local ports only) and sets `MMI_LOCAL_LOADER=1` on `api-bff`, `procurement-service` and `siweb-connector`; the base `infra/compose.yaml` never sets it
- [X] T004 [P] Create `packages/testing/tests/export_loader/__init__.py` and a shared `conftest.py` that points tests only at `packages/testing/fixtures/exports/`

---

## Phase 2: Foundational (blocks all user stories)

- [X] T005 [P] Add JSON Schemas `supplier`, `supplier_link`, `load_result` and `conditions_block` under `packages/contracts/dto/` following `specs/004-local-test-data-suppliers/data-model.md` and `contracts/`; regenerate Python and TypeScript types per `packages/contracts/codegen.toml`
- [X] T006 [P] Add contract tests for the four new schemas (valid, invalid, compatibility baseline) in `packages/contracts/tests/test_supplier_schemas.py` and update `packages/contracts/baseline/`
- [X] T007 [P] Confirm the exact movement-reason names in `packages/contracts` against the mapping table in `specs/004-local-test-data-suppliers/research.md` R4 and record the result in R4 (rename rows if an enum differs)
- [X] T008 Add the Gate 0 items G0-L1, G0-N1, G0-N2, G0-N3 and G0-M1 from `research.md` to `specs/001-mmi-purchase-intelligence/tasks.md` (same style as T135), blocking real-ERP use of imported supplier ids and of the note write
- [X] T009 [P] Write failing tests for the export-signature guard in `scripts/tests/test_check_export_signatures.py` (real-shaped file elsewhere fails; fixture under `packages/testing/fixtures/exports/` with `SYN-` SKUs passes; fixture without the synthetic marker fails)
- [X] T010 Implement `scripts/check_export_signatures.py` (header signatures of the three exports per `contracts/export-formats.md`, CSV and XLSX, tracked and staged files) and wire it into the pre-commit configuration and the existing CI workflow under `.github/workflows/`
- [X] T011 [P] Write failing tests for the file hardening checks in `packages/testing/tests/export_loader/test_validate_file.py`, mirroring the seed-import cases (extension, declared type, signature, size, row limit, decompression ratio, macros, external links, formulas)
- [X] T012 Implement `packages/testing/src/export_loader/validate_file.py` (limits read from the same `MMI_UPLOAD_*` environment variables as `services/api-bff/src/upload_settings.py`; no import from services)
- [X] T013 [P] Implement `packages/testing/src/export_loader/formats.py`: header signatures, column maps, type/reason mapping table (R4), country-name aliases, tax-kind table
- [X] T014 [P] Write failing tests for the SKU map in `packages/testing/tests/export_loader/test_sku_map.py` (stable ids across runs, reserved range from 9,000,000, case-insensitive match, append-only, wipe)
- [X] T015 Implement `packages/testing/src/export_loader/sku_map.py`
- [X] T016 [P] Write failing tests for the report in `packages/testing/tests/export_loader/test_report.py` including the invariant `loaded + updated + unchanged + quarantined + excluded + services == rows` and the no-PII review detail rule
- [X] T017 Implement `packages/testing/src/export_loader/report.py` producing the `load_result` shape
- [X] T018 [P] Write failing tests for the synthetic export generator in `packages/testing/tests/test_generator_exports.py`: identical bytes for the same seed; all three formats with every column; the listed quirks (empty supplier column, lots on a minority of rows, service items, malformed expiry, unmapped reason, unknown SKU, text dates, customer rows, duplicate-looking supplier names, foreign supplier in another currency, unparsed payment terms)
- [X] T019 Implement `packages/testing/src/generator/exports.py` with a command-line entry (`python -m generator.exports --seed N --out DIR`), `SYN-` SKUs, supplier ids in a reserved synthetic range, fictional names only
- [X] T020 Generate the committed synthetic set into `packages/testing/fixtures/exports/` (inventory CSV, movements XLSX, suppliers CSV; seed 42; roughly 300 products, 400 movements, 25 suppliers) with a short `README.md` stating they are synthetic
- [X] T021 Create procurement migration `services/procurement-service/migrations/versions/0011_suppliers.py` (supplier columns, `supplier_costs.source` value `inventory_export`, `supplier_review_items`, `link_assignment_batches`, `export_costs`) with a migration test in `services/procurement-service/tests/test_migration_0011.py`; update `services/procurement-service/src/db/tables.py`
- [X] T022 Extend `specs/001-mmi-purchase-intelligence/contracts/bff-api.openapi.yaml` with the supplier, link, bulk and `local-load` endpoints from `specs/004-local-test-data-suppliers/contracts/` (contract first) and run the existing contract validation
- [X] T089 [P] Loader identities (FR-039, R14): add audience `local-loader` and a loader service principal to `packages/testing/src/dev_issuer/`, a verification helper `packages/testing/src/export_loader/auth.py`, and failing tests `packages/testing/tests/export_loader/test_auth.py` (missing token, wrong audience, expired token)

**Checkpoint**: contracts, guard, hardening, SKU map, report, generator, fixtures and migration exist; user stories can start.

---

## Phase 3: User Story 1 — Load inventory, stock and movements locally (P1)

**Goal**: a buyer or admin loads the inventory and movements exports (synthetic in tests, real locally) and the full pipeline runs on them, with SKU as the identifier.

**Independent test**: load the synthetic inventory and movements files into a clean local stack; counts reconcile with the files, the dashboard shows the products and stock, quarantined rows are listed, and a second load changes nothing.

### Tests first

- [X] T023 [P] [US1] Failing tests for `parse_inventory.py` in `packages/testing/tests/export_loader/test_parse_inventory.py`: SKU identity and merge of repeated SKUs, Spanish decimals and flags, tax interpretation per row, service items excluded, reserved > total, negative stock, zero cost and cost above price flagged for data quality (loaded, not corrected), non-EUR currency to review, empty supplier column accepted, description and notes never stored
- [X] T024 [P] [US1] Failing tests for `parse_movements.py` in `packages/testing/tests/export_loader/test_parse_movements.py`: text-date parsing in Europe/Madrid with raw text kept, clock-change ambiguity to review, unknown SKU to review, unmapped type/reason to review, malformed expiry to review, empty lot, notes reduced to `has_note`, sign/kind mismatch to review
- [X] T025 [P] [US1] Failing tests for `to_mock.py` and the mock load endpoint in `packages/testing/tests/export_loader/test_to_mock.py`: surrogate ids from the SKU map, products/variants/stock/lots/movements shaped like the mock's `Dataset`, mock reset and replace
- [X] T026 [P] [US1] Failing tests for reload behaviour in `packages/testing/tests/export_loader/test_reload.py`: repeat load creates no duplicates; stock and descriptive fields overwritten; protected fields (cost, reorder point, target stock) kept when the app value differs from the last-written value and listed as differences (FR-034)
- [X] T027 [P] [US1] Failing end-to-end test `infra/tests/test_local_load_e2e.py`: start the compose stack, load the synthetic set, run the connector sync, assert reconciled counts, populated dashboard endpoints, quarantine list, and zero new rows on the second run
- [X] T028 [P] [US1] Failing test `services/inventory-service/tests/test_service_items.py`: items flagged as service are stored but excluded from stock risk, demand, segments and forecasting (FR-036)

### Implementation

- [X] T029 [US1] Implement `packages/testing/src/export_loader/parse_inventory.py`
- [X] T030 [US1] Implement `packages/testing/src/export_loader/parse_movements.py` (`openpyxl` read-only mode plus `validate_file.py`)
- [X] T031 [US1] Implement `packages/testing/src/export_loader/to_mock.py` building the mock `Dataset` (warehouses incl. explicit unassigned, products, variants with SKU, stock snapshots, lots, movements); pass through what the platform's checks can judge (malformed expiry as raw text, missing warehouse as unassigned) and set each variant's `price_cents` to the normalised tax-inclusive selling price, the source inventory-service `/pvp` serves to `services/procurement-service/src/costs/pvp.py`, so the margin check works (FR-037, R15, R16)
- [X] T032 [US1] Add `POST /__mock__/load` (replace dataset and reset counters) to `packages/testing/src/siweb_mock/app.py` and `state.py`, refused unless the mock runs in its local-only setting
- [X] T033 [US1] Implement protected-field tracking and difference listing in `packages/testing/src/export_loader/last_load.py` (reads reorder point and target stock from inventory-service and link costs from procurement-service through their APIs with the loader principal from T089; a field that cannot be read is treated as protected)
- [X] T034 [US1] Implement `packages/testing/src/export_loader/cli.py` (`check`, `load`, `wipe`): refuse directories inside the repository except the fixtures folder, refuse non-local database or queue endpoints, print counts only, require `--accept-interpretation` for an inventory load after `check` has shown the tax and price interpretation, trigger the sync after the mock load through the local-only connector trigger of T103/T104 (command and screen use the same path)
- [X] T035 [US1] Add the service flag and its handling in `services/inventory-service` (migration only if no equivalent attribute exists; filters in `src/risk`, `src/demand`, `src/classification`) and carry it in `services/siweb-connector/src/mapping/normalise.py`
- [X] T036 [US1] Implement the loader HTTP app `packages/testing/src/export_loader/app.py` (`POST /load/{kind}`, `/check/{kind}`, `GET/DELETE /state`, difference accept/ignore); files held in memory or a private temp folder and deleted after the load
- [X] T105 [P] [US1] Failing tests `services/api-bff/tests/test_local_load_routes.py` (roles, idempotency key, stable error codes, 404 when disabled, audience-scoped token forwarded to the loader per T089/T090, capability reports enabled only when the loader answers a health check)
- [X] T037 [US1] Add BFF routes `services/api-bff/src/routes/local_load.py` (capability, check, load, runs, differences) proxying to the loader app, mounted from `services/api-bff/src/main.py` only when `MMI_LOCAL_LOADER=1` and `MMI_ENV` is not `prod`/`staging`
- [X] T106 [P] [US1] Failing component and Playwright tests for the Carga local screen in `apps/web/tests/unit/local-load.test.tsx` and `apps/web/tests/e2e/local-load.spec.ts` (hidden when the capability is disabled, interpretation confirmation required before a load, axe checks, no hard-coded strings)
- [X] T038 [P] [US1] SPA "Carga local" screen `apps/web/src/features/localload/LocalLoadScreen.tsx` (upload per file kind, check, an explicit confirmation of the tax and price interpretation, then load, result counts, review list, differences accept/ignore), shown only when the capability endpoint says enabled; texts in `apps/web/src/i18n/es-ES.json`
- [X] T091 [P] [US1] Failing tests `packages/testing/tests/export_loader/test_review_sources.py`: rows the platform can judge are passed through and quarantined by the connector; rows it cannot express (unmapped reason, unknown SKU, unreadable values) stay in the loader review store; the combined review view labels both sources; the SC-002 invariant holds across both
- [X] T107 [P] [US1] Failing Playwright test `apps/web/tests/e2e/quality-review-sources.spec.ts`: the data-quality screen shows loader and platform review items with their source label, and the loader source is hidden when the capability is disabled
- [X] T092 [US1] Implement the loader review store and `GET /review` in `packages/testing/src/export_loader/app.py`, the BFF `GET /local-load/review` in `services/api-bff/src/routes/local_load.py`, and show both sources (labelled loader / platform) in `apps/web/src/features/quality/QualityScreen.tsx` with es-ES strings
- [X] T093 [P] [US1] Failing test `services/siweb-connector/tests/test_refuse_mixed_local_data.py`: a sync against a non-mock host is refused with a stable error code while reserved-range ids (≥ 9,000,000) exist in the target database; allowed after `wipe` (FR-038, R17)
- [X] T094 [US1] Implement the mixing guard in `services/siweb-connector/src/sync/runner.py` (check before any request to a non-mock host) with the Spanish message key in the connector's locale files
- [X] T095 [P] [US1] Failing tests `services/procurement-service/tests/test_export_costs.py`: the internal endpoint stores `(sku, cost, pvp, tax)`; reload refreshes the reference but never an edited link cost; link creation defaults the cost with source `inventory_export`; the margin check is available for locally loaded products (FR-037, R16)
- [X] T096 [US1] Implement `services/procurement-service/src/suppliers/export_costs.py` and the flag-guarded internal route `services/procurement-service/src/api/internal_export_costs.py` (service identity only, mounted when `MMI_LOCAL_LOADER=1` and not prod), registered in `services/procurement-service/src/main.py`
- [X] T097 [US1] Implement `packages/testing/src/export_loader/push_costs.py` pushing export costs and selling prices to procurement after each inventory load, and call it from `cli.py` and `app.py`
- [X] T090 [US1] Apply the identities: the loader app (T036) validates `local-loader` tokens, the BFF (T037) obtains and forwards audience-scoped tokens, loader calls to inventory-service and procurement-service (T033, T062, T097) use the loader principal; add tests in `services/api-bff/tests/test_local_load_routes.py` and `services/procurement-service/tests/test_internal_supplier_import.py`
- [X] T103 [P] [US1] Failing tests `services/siweb-connector/tests/test_local_sync_trigger.py`: `POST /internal/local-sync` requires the loader service identity, is mounted only when `MMI_LOCAL_LOADER=1`, runs the collection job in-process, refuses any non-mock host, and answers 404 when the flag is unset
- [X] T104 [US1] Implement `POST /internal/local-sync` in `services/siweb-connector/src/main.py` (new module `services/siweb-connector/src/local_sync.py`), reusing `job.py`; the loader calls it from `cli.py` and `app.py`
- [X] T039 [US1] Run T023–T028 until green and record the quickstart step 3 outcome in `specs/004-local-test-data-suppliers/quickstart.md`

**Checkpoint**: US1 delivers a full local data path on synthetic files; real files work the same from `data/local-exports/`.

---

## Phase 4: User Story 2 — Create and configure suppliers from the UI (P1)

**Goal**: buyers and admins create, edit and deactivate suppliers, set conditions, link products (single and bulk) and see proposals honour them.

**Independent test**: in the UI create a supplier, set conditions, link two products, generate a proposal that uses them, then deactivate and confirm the supplier is no longer proposed.

### Tests first

- [X] T040 [P] [US2] Failing tests for the supplier service in `services/procurement-service/tests/test_suppliers_service.py`: create, duplicate-name warning and confirmation, edit with `If-Match`, classification change, deactivate preview then confirm, reactivate, audit events, no tax ID/bank/note fields accepted
- [X] T041 [P] [US2] Failing tests for links in `services/procurement-service/tests/test_supplier_links.py`: create/update/remove by SKU, Recargo option, provenance fields, `pending_link` for platform-only suppliers with no ERP request, currency mismatch refusal
- [X] T042 [P] [US2] Failing tests for bulk assignment in `services/procurement-service/tests/test_bulk_assign.py`: filter, selection and file input; preview counts; conflict with an existing preferred supplier; stale preview refused; per-product audit
- [X] T043 [P] [US2] Failing test `services/procurement-service/tests/test_allocation_excludes_suppliers.py`: deactivated and non-purchasing suppliers never receive lines; open lines of a deactivated supplier are flagged for reallocation
- [X] T044 [P] [US2] Failing BFF tests in `services/api-bff/tests/test_supplier_routes.py` (viewer read-only, buyer/admin write, `If-Match` pass-through, stable codes, es-ES messages)
- [X] T045 [P] [US2] Failing SPA tests in `apps/web/tests/unit/` and `apps/web/tests/e2e/suppliers-manage.spec.ts` (form validation, duplicate warning, deactivate dialog with affected lines, bulk preview, axe checks, no hard-coded strings)

### Implementation

- [X] T046 [US2] Implement `services/procurement-service/src/suppliers/service.py` (CRUD, status, classification, versioning, audit through the existing chain)
- [X] T047 [P] [US2] Implement `services/procurement-service/src/suppliers/dedupe.py` (`name_key` folding, duplicate detection, review items)
- [X] T048 [US2] Implement `services/procurement-service/src/suppliers/links.py` (links by SKU using existing cost provenance, default cost from `export_costs` when present, `inventory_export` and `manual` sources, `pending_link` handling)
- [X] T049 [US2] Implement `services/procurement-service/src/suppliers/bulk.py` (preview, apply, batch table, file input validation)
- [X] T050 [US2] Add routes `services/procurement-service/src/api/suppliers.py` per `contracts/suppliers-api.md` and register them in `services/procurement-service/src/main.py`
- [X] T051 [US2] Exclude deactivated and non-purchasing suppliers in `services/procurement-service/src/allocation/common.py` and flag affected proposal lines in `services/procurement-service/src/proposals/`
- [X] T052 [US2] Add BFF proxy routes `services/api-bff/src/routes/suppliers.py` and client methods in `services/api-bff/src/clients/procurement.py`; keep role checks in `services/api-bff/src/routes/rbac.py`
- [X] T053 [P] [US2] SPA supplier form and list: `apps/web/src/features/suppliers/SupplierForm.tsx`, extend `SuppliersScreen.tsx`, `termsModel.ts`, `apps/web/src/api/client.ts`, new strings in `es-ES.json`
- [X] T054 [P] [US2] SPA links panel `apps/web/src/features/suppliers/LinksPanel.tsx` (by SKU, cost with Recargo option, pack, minimum, rank, provenance badge)
- [X] T055 [P] [US2] SPA bulk assignment `apps/web/src/features/suppliers/BulkAssign.tsx` (filter, selection, SKU/supplier file upload, preview, apply, conflicts)
- [X] T098 [P] [US2] Failing tests `services/siweb-cost-writer/tests/test_refuse_local_ids.py` and `services/siweb-connector/tests/contract/test_refuse_local_ids.py`: any request path, query or body containing an id ≥ 9,000,000 is refused before it is built; a SKU with no real ERP id yields `pending_link` with the SKU as reference; a SKU with a synced real id resolves to it (FR-003, FR-040, R1a)
- [X] T099 [US2] Implement the SKU → ERP-id resolution in `services/procurement-service/src/costs/directory.py` and the reserved-range guard in `services/siweb-connector/src/client/` and `services/siweb-cost-writer/src/writer/`; make cost-write and note-write requests carry the SKU as the user-visible reference and resolve ids only at send time
- [X] T100 [P] [US2] Failing tests `services/procurement-service/tests/test_supplier_merge.py`: an explicit merge moves links, terms, costs and history to the kept supplier, deactivates the merged one with a pointer, is audited, and is refused when currencies differ or either supplier has an open proposal line without confirmation
- [X] T101 [US2] Implement `services/procurement-service/src/suppliers/merge.py` and the `merge_into` action of `POST /suppliers/review-items/{id}/resolve` in `services/procurement-service/src/api/suppliers.py`
- [X] T056 [US2] Run T040–T045 until green; verify quickstart step 4 and record SC-004 and SC-005 evidence in `specs/004-local-test-data-suppliers/quickstart.md`

**Checkpoint**: US2 stands alone and is usable in production without the local loader.

---

## Phase 5: User Story 3 — Import the supplier list from an export (P2)

**Goal**: seed suppliers from the supplier export, excluding customers, flagging non-purchasing vendors and (when a name is present) linking products automatically.

**Independent test**: load the synthetic suppliers file; customers excluded, duplicate-looking names listed, non-EUR kept, payment terms parsed or listed, no tax ID or note text stored.

### Tests first

- [X] T057 [P] [US3] Failing tests for `parse_suppliers.py` in `packages/testing/tests/export_loader/test_parse_suppliers.py` (customer exclusion, dropped columns, country aliases, currency default, payment-terms parsing, `has_note`, duplicate ids to review)
- [X] T058 [P] [US3] Failing tests for the internal import endpoint in `services/procurement-service/tests/test_internal_supplier_import.py` (service identity only, refused unless the local flag is set, row-level validation, counts, idempotent re-import by `external_contact_id`, `erp_link_state = unverified`)
- [X] T059 [P] [US3] Failing tests for automatic product-supplier linking (FR-033) in `services/procurement-service/tests/test_auto_link.py`: exact single match links; none, several, deactivated or non-purchasing go to review; cost stored with source `inventory_export`

### Implementation

- [X] T060 [US3] Implement `packages/testing/src/export_loader/parse_suppliers.py`
- [X] T061 [P] [US3] Implement a payment-terms parser (`"7 días"`, `"30"`) and a non-purchasing suggestion rule (name/category keywords, editable by the buyer, never final) in `services/procurement-service/src/suppliers/import_rules.py`
- [X] T062 [US3] Implement `packages/testing/src/export_loader/to_procurement.py` (suppliers, then links from the inventory file when it names a supplier) calling `POST /internal/suppliers/import`
- [X] T063 [US3] Add `services/procurement-service/src/api/internal_import.py` (flag-guarded, mounted only when `MMI_LOCAL_LOADER=1` and not prod) and the automatic linking in `services/procurement-service/src/suppliers/links.py`
- [X] T064 [US3] Wire supplier loading (`kind = suppliers`) into `packages/testing/src/export_loader/cli.py`, `app.py` and the BFF local-load routes
- [X] T108 [P] [US3] Failing tests `apps/web/tests/unit/supplier-import.test.tsx`: result counts, duplicate merge/keep/ignore actions, classification toggle, unparsed payment terms listed, no hard-coded strings
- [X] T065 [P] [US3] SPA supplier import and review screen `apps/web/src/features/suppliers/SupplierImport.tsx` (result counts, possible duplicates with merge/keep/ignore, classification toggle purchasing / non-purchasing, unparsed payment terms) with es-ES strings
- [X] T066 [US3] Run T057–T059 until green; verify quickstart step 4 (supplier file part)

**Checkpoint**: US3 complete; US2 still works without it.

---

## Phase 6: User Story 4 — Safe fixtures and the local-only guarantee (P1)

**Goal**: prove real data cannot reach the repository or the cloud and that the loader is absent there.

**Independent test**: the safeguard, cloud-absence and no-network tests pass; introducing a real-shaped file or a Bicep reference makes them fail.

### Tests first

- [ ] T067 [P] [US4] Failing test `infra/tests/test_no_local_loader_in_cloud.py`: no Dockerfile, Bicep file, deployment workflow or cloud compose references `export_loader`, `local-loader`, `MMI_LOCAL_LOADER`, `compose.local-data` or `data/local-exports`
- [ ] T068 [P] [US4] Failing BFF tests `services/api-bff/tests/test_local_load_disabled.py`: with `MMI_ENV=prod` or the flag unset every `local-load` route answers 404, the capability endpoint reports disabled, and a security event is recorded
- [ ] T069 [P] [US4] Failing tests `packages/testing/tests/export_loader/test_local_only_guards.py`: `--dir` inside the repo (except the fixtures folder) refused, non-local database/queue endpoints refused, no outbound network connection during a load (sockets blocked except localhost)
- [ ] T070 [P] [US4] Failing repository check `scripts/tests/test_no_private_folder_reads.py` scanning test sources for `data/local-exports`

### Implementation

- [ ] T071 [US4] Implement the runtime guards in `packages/testing/src/export_loader/guards.py` and use them from `cli.py` and `app.py`
- [ ] T072 [US4] Implement `wipe` fully (loader state, local database contents of the loaded data, mock reset) in `packages/testing/src/export_loader/cli.py`
- [ ] T073 [P] [US4] Write the runbook `docs/runbooks/local-real-data.md` (prepare the private folder, load, verify, wipe; what never to do) and link it from `README.md` and `specs/004-local-test-data-suppliers/quickstart.md`
- [ ] T074 [US4] Record security events for refused local-load calls in `services/api-bff/src/audit.py` and note the signal in the `infra/` documentation (no new Azure resource)
- [ ] T075 [US4] Run T067–T070 and the signature guard from T010 in CI; verify quickstart steps 1 and 6 and record SC-006, SC-007 and SC-008 evidence

**Checkpoint**: US4 evidence collected; the feature can be used with real files locally without repository or cloud exposure.

---

## Phase 7: Supplier conditions in the ERP note (FR-027 to FR-032) — built, disabled until Gate 0

**Goal**: the application-owned conditions block can be generated, merged, compared and alerted on, with the ERP operation still disabled.

**Independent test**: property tests prove the merge preserves foreign note content and refuses damaged markers; the allowlist test proves no request is built while the path is `TBD`.

- [ ] T076 [P] [US2] Failing property tests `services/siweb-cost-writer/tests/test_note_block.py` (arbitrary text incl. line breaks, non-ASCII and marker-like text round-trips outside the block; append when absent; replace when present; refuse on duplicate or unterminated markers; idempotent when unchanged; size limit parameter)
- [ ] T077 [P] [US2] Failing allowlist tests in `services/siweb-connector/tests/contract/test_allowlist_note_operation.py` and `infra/tests/test_erp_boundary.py`: the note operation is not built while its path is `TBD`; the cost update stays allowed; every other method and path stays refused
- [ ] T078 [US2] Implement `services/siweb-cost-writer/src/writer/note_block.py` (build, parse, merge, hash; no network path; no logging of note content)
- [ ] T079 [US2] Add the disabled operation placeholder to `services/siweb-connector/src/allowlist/allowlist.py` and the writer's operation table, failing closed, with `MMI_NOTE_BLOCK_ENABLED` defaulting to off and refused in code while the path is `TBD`
- [ ] T109 [P] [US2] Failing tests `services/procurement-service/tests/test_conditions_sync.py`: states `in_sync`, `pending`, `discrepancy`, `failed`, `pending_link`; transitions; hashes only, no note text stored
- [ ] T110 [P] [US2] Failing tests `apps/web/tests/unit/conditions-sync.test.tsx`: both values shown with who and when where known, the buyer or admin chooses, nothing is overwritten automatically, axe checks, no hard-coded strings
- [ ] T080 [US2] Create `services/procurement-service/migrations/versions/0012_conditions_sync.py` for `supplier_conditions_sync`; implement discrepancy detection and state transitions in `services/procurement-service/src/suppliers/conditions_sync.py`
- [ ] T081 [US2] Add the buyer/admin discrepancy alert and decision flow (show both values with who and when each changed where known, choose, no automatic overwrite) in `apps/web/src/features/suppliers/ConditionsSync.tsx` with the matching procurement and BFF routes; es-ES strings
- [ ] T082 [US2] **Gate 0, blocking enablement**: verify G0-N1, G0-N2, G0-N3 and G0-L1 on a non-production record; record outcomes in the internal wiki and in `specs/004-local-test-data-suppliers/research.md`; only then replace `TBD` in `specs/001-mmi-purchase-intelligence/contracts/siweb-allowlist.md` and the allowlist code, add the fresh-MFA review step and `supplier_conditions_write_request` flow, and enable the flag in a separate reviewed change

---

## Phase 8: Polish and cross-cutting

- [ ] T083 [P] Update `docs/architecture/implementation-plan.md` (decisions log: SKU-keyed local path, loader location, three absence layers, note block disabled until Gate 0) and add an ADR entry
- [ ] T084 [P] Update the workflow section of `AGENTS.md` and the cross-references in `specs/001-mmi-purchase-intelligence/tasks.md` to this feature
- [ ] T102 Emit operational signals through the services' existing structured logging (no new metrics stack): loader and BFF log `local_load_result` events with counts by outcome and review items by source and code, procurement logs supplier create/edit/deactivate/merge and bulk-apply events with counts; none carries row content, note text, tax IDs or names; add a test per service asserting the fields and the absence of personal data, and describe the alert queries in `infra/` documentation (no new Azure resource)
- [ ] T085 Run the full test suites (`packages/testing`, `packages/contracts`, `services/*`, `apps/web` unit and Playwright with axe, `infra/tests`) and the repository secret and signature scans; fix regressions
- [ ] T086 Walk through `specs/004-local-test-data-suppliers/quickstart.md` end to end on a clean local state (steps 1–6; step 7 only checks the disabled state) and record results
- [ ] T087 Security review of the new upload path (hardening parity, 404 behaviour, logging hygiene: no note text, tax IDs or personal names in logs or review details) and a performance check against SC-001 with the synthetic set scaled ×5
- [ ] T088 Prepare the pull request using `.github/pull_request_template.md` (data, security, cost, contract impact) and tick completed tasks in this file

---

## Dependencies and execution order

- **Phase 1 → Phase 2** (blocking) → user stories.
- **US1** depends on Phase 2 only. **US2** depends on Phase 2 (migration, contracts, OpenAPI); it does not need US1, but its end-to-end check uses US1's loaded products. **US3** depends on US2 (supplier service) and on the loader from US1. **US4** can start after Phase 2; its final evidence (T075) needs US1 and US3 code.
- **Phase 7** depends on US2 for supplier data and on the allowlist work in `siweb-connector`; T082 depends on external Gate 0 access and is not required for Phases 1–6.
- Within a story: tests → models/services → endpoints → UI → verification.

### Parallel opportunities

- Phase 1: T002, T003, T004.
- Phase 2: T005/T006, T007, T009, T011, T013, T014, T016, T018 after their prerequisites.
- US1 tests T023–T028 together; T038 alongside backend tasks once T037 exists.
- US2 tests T040–T045 together; T053–T055 together after T050 and T052.
- US4 tests T067–T070 together.
- Phase 7 tests T076 and T077 together.

### Suggested slices for separate sessions

1. Phases 1–2, then US1 — delivers the immediate need: the app running on export-shaped data.
2. US2 and its UI — supplier configuration.
3. US3 and US4 — import convenience and proof of local-only handling.
4. Phase 7 — only after Gate 0.

## Implementation strategy

- **MVP**: Phases 1–2 plus US1 (T001–T039). Synthetic exports, and your real inventory and movements from `data/local-exports/`, then run through the whole pipeline.
- **Next increment**: US2 so a buyer can create suppliers and link products, then US3 for the supplier file and automatic linking, then US4 evidence.
- **Not before Gate 0**: T082 and enabling the ERP note write.
