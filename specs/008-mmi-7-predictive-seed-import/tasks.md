# Tasks: Predictive Seed Import and Dataset Governance (MMI-7)

**Input**: `specs/008-mmi-7-predictive-seed-import/` (spec.md, plan.md, research.md). `data-model.md`, `quickstart.md` and `contracts/seed-governance.delta.md` now exist (T005, T006, T046 done).

**Tests**: Included. The constitution and the spec (SC-001 to SC-011) require tests; tests come before implementation within each story. Synthetic fixtures only.

**Format**: `- [ ] ID [P] [Story] Description with file path`. `[P]` means a different file with no dependency on an unfinished task.

**Baseline**: feature 002 user story 5 already built most of the pipeline. Reuse it; change only what the audit in research.md shows is missing.

## Phase 1: Setup

- [X] T001 Run the existing seed test set on main and record pass/fail in `specs/008-mmi-7-predictive-seed-import/research.md` (section "Baseline run"): `services/forecast-service/tests/test_seed_*.py`, `test_import_jobs.py`, `test_imports_api.py`, `apps/web/tests/unit/ImportScreen.test.tsx`
- [X] T002 Check whether inventory series items (`series_source.fetch()['series']`, used by `known_variants()` in `services/forecast-service/src/imports_api.py:75`) carry `sku`; if not, add it as an additive field in the inventory series contract in `packages/contracts/` and `services/inventory-service/src/api/routes.py`; record the result in research.md D1
- [X] T003 [P] Audit unverified rows of the research.md table (provenance default, dry-run "not assessable", retired SKU, explanations, import status section) by reading `services/forecast-service/src/seeds/dryrun.py`, `services/forecast-service/src/runs/seeds.py` and `apps/web/src/features/imports/ImportScreen.tsx`; update each row to complete, partial, broken or missing with file and line

## Phase 2: Foundational (blocks all stories)

- [X] T004 [P] Add synthetic SKU-based seed fixtures (valid CSV and XLSX, duplicate SKU/day, unknown SKU, ambiguous SKU, retired SKU, file with `variant_id` header only, mixed origin) in `packages/testing/`
- [X] T005 [P] Write `specs/008-mmi-7-predictive-seed-import/contracts/seed-governance.delta.md` (done in clarification pass)
- [X] T006 [P] Write `specs/008-mmi-7-predictive-seed-import/data-model.md` (done in clarification pass)
- [X] T007 Add a forecast-service migration after 0004 in `services/forecast-service/migrations/versions/` adding `sku` to `seed_rows` (the quarantine keeps the SKU in `reason_params`, not a column), and `validated_by`, `mapping_chosen_by`, `rollback_reason` and `self_activated_reason` to `seed_datasets` (per data-model.md); update `services/forecast-service/src/db/tables.py`
- [X] T008 Update JSON Schemas first in `packages/contracts/dto/` (`seed_dataset`, `seed_validation_result`, `seed_mapping`) as additive changes per the contract delta (keep deprecated `approved`; keep `variant_id` accepted but rejected per row), refresh `packages/contracts/baseline/`, regenerate Python and TypeScript types; run the contract compatibility check
- [X] T009 [P] Add Spanish strings for the new error keys (including `import_erp_export_refused`) and states to the web i18n resources in `apps/web/src/features/imports/` and the service locale `services/forecast-service/src/locale/es-ES.json`

**Checkpoint**: contracts, migration and fixtures ready.

- [ ] T049 Post the contract delta (`sku` field, new error keys, rollback `reason`, dataset fields, inventory series `sku` if needed) to Agent 00 and record the agreement in research.md before T008 merges

## Phase 3: User Story 1 - Import a seed file and review it (P1)

**Goal**: SKU-based import with mapping, duplicates, quarantine and preview; nothing changes.
**Independent test**: upload the T004 file; preview lists accepted, duplicate and quarantined rows with reasons; no forecast changes.

- [X] T010 [P] [US1] Test SKU matching: known SKU accepted, unknown and ambiguous SKU quarantined, `variant_id`-only file rejected with `import_sku_required`, and files with ERP export header shapes (inventory, movements, supplier) are refused with `import_erp_export_refused` before rows are parsed, in `services/forecast-service/tests/test_seed_sku.py`
- [X] T011 [P] [US1] Test template contains `sku` and no internal id, and mapping suggests `sku`, in `services/forecast-service/tests/test_seed_template.py`
- [X] T012 [P] [US1] Test viewer is refused on upload, mapping and validate and the refusal is recorded, in `services/api-bff/tests/test_imports_rbac.py`
- [X] T013 [US1] Implement SKU resolution in `services/forecast-service/src/seeds/validation.py` using the series source from T002; keep quarantine reasons and never drop rows
- [X] T014 [US1] Switch the template and mapping suggestion to `sku` in `services/forecast-service/src/seeds/template.py` and `services/forecast-service/src/seeds/mapping.py`
- [X] T015 [US1] Pass the SKU map through `services/forecast-service/src/imports_api.py` and the background path `services/forecast-service/src/seeds/jobs.py`
- [X] T016 [US1] Update the preview and quarantine views to show SKU and the "nothing has changed yet" statement in `apps/web/src/features/imports/ImportScreen.tsx` and `importsModel.ts`
- [X] T017 [P] [US1] Web unit test for the SKU preview and quarantine list in `apps/web/tests/unit/ImportScreen.test.tsx`

- [X] T055 [US1] Refuse files recognised as ERP exports (inventory, movements or supplier export header shapes) with `import_erp_export_refused` (415) before parsing rows, in `services/forecast-service/src/seeds/parsers.py` and `services/forecast-service/src/imports_api.py`; fixtures of the three header shapes in `packages/testing/`

## Phase 4: User Story 2 - Dry run, approve, activate, forecast changes (P1)

**Goal**: dry run changes nothing; activation needs a second person and fresh MFA; next forecast differs and names the dataset.
**Independent test**: activate a synthetic dataset for a "new" product; next run differs, is flagged `seed_used`, records the version; uncovered products unchanged.

- [X] T018 [P] [US2] Test uploader and validator cannot activate (`import_self_approval`), a different buyer can, and an owner/admin self-activation succeeds only with a written reason and fresh MFA and is audited as `seed.self_activated`, in `services/forecast-service/tests/test_seed_activation.py`
- [X] T019 [P] [US2] Test activate and rollback routes refuse a session without fresh MFA, in `services/api-bff/tests/test_imports_mfa.py`
- [X] T020 [P] [US2] Test two concurrent activations: exactly one succeeds, the other gets `import_conflict`, in `services/forecast-service/tests/test_seed_concurrency.py` (PostgreSQL)
- [X] T021 [P] [US2] Test dry run changes no stored forecast, proposal or stock, and lists thin-history products as not assessable, in `services/forecast-service/tests/test_seed_dryrun.py`
- [X] T022 [P] [US2] Test actuals prevail over seeds on covered days and the overlap is reported, in `services/forecast-service/tests/test_seed_overlap.py`
- [X] T023 [US2] Record `validated_by` (and the mapping chooser) at validation; at activation refuse the uploader and validator unless an owner/admin passes a written `reason`, then audit `seed.self_activated`, in `services/forecast-service/src/seeds/lifecycle.py`
- [X] T024 [US2] Lock the active-dataset row inside `activate` and `rollback` in `services/forecast-service/src/seeds/lifecycle.py`; map the failure to `import_conflict` 409 in `services/forecast-service/src/imports_api.py`
- [X] T025 [US2] Add `require_fresh_mfa()` to activate and rollback in `services/api-bff/src/routes/imports.py`
- [X] T026 [US2] Add the "not assessable" list to the dry-run result in `services/forecast-service/src/seeds/dryrun.py` if T003 found it missing
- [X] T027 [US2] Make forecast output carry dataset id and version, and add them to the proposal explanation text (verify first; edit `services/procurement-service/src/proposals/generate.py` only for that line, inform Agent 00)
- [X] T028 [US2] Add approval, MFA prompt and dry-run result states in `apps/web/src/features/imports/ImportScreen.tsx`
- [X] T029 [US2] Playwright test: buyer A uploads and validates, buyer B runs dry run and activates, forecast screen shows seed-based value, in `apps/web/tests/e2e/import.spec.ts`

- [X] T050 [P] [US2] Test the rescue rule: only products whose sole ineligibility is "new", with seed density at least half and combined history at the minimum, are rescued and flagged `seed_used`; uncovered products are unchanged, in `services/forecast-service/tests/test_seed_rescue.py`

## Phase 5: User Story 3 - Roll back (P1)

**Goal**: rollback with reason returns forecasts to the pre-activation result.
**Independent test**: forecast X, activate, roll back, rerun: equals X; dataset kept as rolled back with audit entry.

- [X] T030 [P] [US3] Test rollback requires a reason, stores and audits it, deletes nothing, and refuses a non-active dataset, in `services/forecast-service/tests/test_seed_rollback.py`
- [X] T031 [P] [US3] Test forecast after rollback equals the forecast just before activation: no seed influence when none was active before, and dataset A's result when B superseded A, in `services/forecast-service/tests/test_seed_rollback_equivalence.py`
- [X] T032 [P] [US3] Test historical forecasts still show the dataset version used, in `services/forecast-service/tests/test_seed_history.py`
- [X] T033 [US3] Require and store `reason` (`import_reason_required`) in `services/forecast-service/src/seeds/lifecycle.py`, `imports_api.py` and the gateway route `services/api-bff/src/routes/imports.py`
- [X] T034 [US3] Add the rollback reason dialog in `apps/web/src/features/imports/ImportScreen.tsx`
- [X] T035 [US3] Extend the Playwright test to roll back and show the forecast returning, in `apps/web/tests/e2e/import.spec.ts`

## Phase 6: User Story 4 - Provenance and governance visibility (P2)

**Goal**: every seed value labelled; never shown as ERP data.
**Independent test**: list and detail show state, origin, approver, provenance mix; a mixed-origin file is rejected.

- [X] T036 [P] [US4] Test a row with a blank data type or blank source label is quarantined (`import_unknown_kind`, `import_missing_provenance`) and never defaulted, and a mixed-origin file is rejected, in `services/forecast-service/tests/test_seed_validation.py`
- [X] T037 [P] [US4] Test seed rows never appear in ERP-derived demand, ERP-bound requests or exports, and surrogate-id (9,000,000 and above) feature 004 data stays separate, in `services/forecast-service/tests/test_seed_isolation.py`
- [X] T038 [US4] Show approver, rollback reason and provenance mix in the dataset list and detail in `apps/web/src/features/imports/`
- [X] T039 [US4] Fix any provenance default or label gap found in T003 in `services/forecast-service/src/seeds/validation.py`

- [X] T051 [P] [US4] Test Spanish number and date formats and decimal quantities are read exactly with original date text and UTC kept, and notes, tax ids and personal data are discarded at load, in `services/forecast-service/tests/test_seed_validation.py`
- [X] T052 [P] [US4] Test a validated dataset is immutable (a correction is a new version) and superseded, rolled-back and rejected datasets stay viewable, in `services/forecast-service/tests/test_seed_versions.py`
- [X] T053 [P] [US4] Test every state change writes an audit entry with actor, UTC time and dataset version and no file contents, in `services/forecast-service/tests/test_seed_audit.py`

## Phase 7: User Story 5 - Background jobs (P2)

**Goal**: large files run in the background, idempotent, visible.
**Independent test**: file above 10,000 rows shows queued stages and result; resubmission creates no second dataset.

- [X] T040 [P] [US5] Test above-limit file is queued, resubmission is idempotent, failure leaves nothing active, in `services/forecast-service/tests/test_import_jobs.py`
- [X] T041 [P] [US5] Test retired SKU stops contributing and is reported in the run, in `services/forecast-service/tests/test_seed_retired_sku.py`
- [X] T042 [US5] Skip and count rows whose variant left the catalogue in `services/forecast-service/src/runs/seeds.py`
- [X] T043 [US5] Verify the import status section shows stage, timings and error; fix gaps in `apps/web/src/features/imports/ImportScreen.tsx`

- [X] T054 [P] [US5] Check job and worker configuration keeps concurrency and size caps and scale-to-zero (no always-on compute) in `infra/bicep/` and `services/forecast-service/tests/test_import_jobs.py`

## Phase 8: Polish

- [X] T044 [P] Hostile-file abuse tests (macro, formula, external link, decompression bomb past the feature 002 caps, mislabelled type, formula-prefix export, cross-site request without token, ERP-export-shaped file refused) re-run with SKU files in `services/forecast-service/tests/test_seed_parsing.py` and `services/api-bff/tests/test_imports_rbac.py`
- [X] T045 [P] Add the timing check for 1,000 products (under 15 minutes) and rollback (under 2 minutes), and assert every screen request answers within 2 seconds while a large job runs, in `services/forecast-service/tests/test_seed_timing.py`
- [X] T046 [P] Write `specs/008-mmi-7-predictive-seed-import/quickstart.md` (done in clarification pass)
- [X] T047 Run lint, type checks, contract validation and secret scan; update ADR-020 note on the two-person rule in `docs/adr/020-seed-provenance.md`
- [ ] T048 Open one PR with the audit table, migration impact, screenshots, test evidence and known limitations, linking MMI-7 and its Confluence page; mark tasks `[X]` here

## Dependencies and order

- Phase 1 then Phase 2 (T049 before T008; T008 before T013 and T014), then stories. US1 (SKU) comes first because later tests use SKU fixtures.
- US2 depends on US1; US3 depends on US2 (needs an active dataset); US4 and US5 depend only on Phase 2 and can run beside US2/US3.
- Within a story: tests, then implementation, then screen.

## Parallel examples

- Phase 2: T004, T005, T006, T009 together.
- US2 tests: T018 to T022 and T050 together.
- US4 and US5 tests: T036, T037, T040, T041 together.

## Strategy

MVP is Phase 1, 2 and US1 (SKU-based import and preview). Then US2 and US3 deliver the acceptance criteria (forecast changes, rollback works). US4, US5 and Polish follow.

## Traceability (requirement to tasks)

| Requirement | Tasks |
|---|---|
| FR-001 audit | T001–T003, T048 |
| FR-002 upload, roles, ERP-export refusal | T012, T055 |
| FR-003 templates | T011, T014 |
| FR-004 file checks | T044 |
| FR-005 mapping | T011, T014 |
| FR-006 formats | T051 |
| FR-007 SKU | T002, T010, T013–T015, T049 |
| FR-008, FR-009 duplicates, quarantine | T010, T044 |
| FR-010 discard personal data | T051 |
| FR-011, FR-012 provenance, origin | T036, T039 |
| FR-013 actuals prevail | T022 |
| FR-014, FR-015 preview, dry run | T016, T017, T021, T026 |
| FR-016 activation | T018–T020, T023–T025, T028, T029 |
| FR-017 forecast use | T050 |
| FR-018 explanations | T027 |
| FR-019 rollback | T030–T035 |
| FR-020 versioning | T052 |
| FR-021–FR-023 ERP separation | T037 |
| FR-024–FR-026 jobs | T040, T043 |
| FR-027 caps, no idle compute | T054 |
| FR-028, FR-029 roles, audit | T012, T019, T053 |
| FR-030 hostile uploads | T044 |
| FR-031 Spanish | T009, T038 |
| FR-032 synthetic data | T004 |
| SC-004, SC-006 timing, latency | T045 |
| SC-009 hostile files | T044 |
| SC-010 cost | T054 |
| SC-011 audit table | T003, T048 |

## Phase 9: Convergence

- [X] T056 CRITICAL Bring `packages/contracts/dto/seed_dataset.v1.schema.json`, `seed_validation_result.v1.schema.json` and `seed_mapping.v1.schema.json` (and the generated Python and TypeScript types) in line with the fields and error keys already shipped, and add a test that the gateway and forecast-service responses validate against them; completes T008 per Constitution IV (contradicts)
- [X] T057 Audit the dry run (`seed.dry_run` with actor, UTC time and dataset version, no file contents) in `services/forecast-service/src/imports_api.py` and `services/forecast-service/src/seeds/dryrun.py`, with a test in `services/forecast-service/tests/test_seed_audit.py` per FR-029 (missing)
- [X] T058 Run migration `0005_seed_governance.py` and the activation-conflict case against PostgreSQL (`RUN_PG_MIGRATIONS=1 pytest -q infra/tests/test_migrations_postgres.py`) and add the conflict case to `services/forecast-service/tests/test_seed_concurrency.py` per FR-016 and plan D5 (partial)
- [X] T059 Migrate the remaining tests that use the `variant_id` fixtures (`packages/testing/fixtures/seeds/{valid,partly_invalid,mixed_origin}.csv`) to the SKU fixtures, then remove the `variant_id` path from `validate_rows` in `services/forecast-service/src/seeds/validation.py` per FR-007 (unrequested)
- [X] T060 Add a consumer-side check that the inventory series export carries `sku` (a contract test on `InventoryHttpSource.fetch` output in `services/forecast-service/tests/`) per the contract delta (partial)

## Phase 10: Convergence

- [X] T061 CRITICAL Register the seven new error keys (`import_sku_required`, `import_unknown_sku`, `import_ambiguous_sku`, `import_erp_export_refused`, `import_self_approval`, `import_conflict`, `import_reason_required`) with their HTTP status and kind in `packages/contracts/errors/error_codes.json`, and extend `packages/contracts/tests/test_mmi002_contracts.py` (or a new test) to assert every key the forecast service can return is in the catalogue per Constitution IV (contradicts)
- [X] T062 Update `specs/002-mmi-operational-console/contracts/import-template.md` so the documented template starts with `SKU` and has no variant-id column, or mark it superseded by `specs/008-mmi-7-predictive-seed-import/contracts/seed-governance.delta.md` per FR-003 (partial)
- [X] T063 Align `specs/008-mmi-7-predictive-seed-import/contracts/seed-governance.delta.md` with the code: quarantine rows carry the SKU in `params` (for `import_unknown_sku` and `import_ambiguous_sku`), not a new top-level field per the contract delta (partial)
- [X] T064 Stop `suggest` in `services/forecast-service/src/seeds/mapping.py` from proposing `variant_id`, and remove the unused `imports.field.variant_id` string in `apps/web/src/i18n/es-ES.json`, with tests in `services/forecast-service/tests/test_seed_validation.py` per FR-007 (partial)

## Phase 11: Convergence

- [X] T065 Add a list-item schema for the `GET /imports` response (`packages/contracts/dto/seed_dataset_summary.v1.schema.json`, with the generated types and baseline) and a test in `services/forecast-service/tests/test_imports_api.py` that the response validates against it per Constitution IV (partial)
- [X] T066 Add a test in `infra/tests/test_seed_error_keys_registered.py` (or a new file) that every distinctive header in `services/forecast-service/src/seeds/export_shapes.py` is a real header of the ERP export layouts in `packages/testing/src/export_loader/formats.py` per FR-002 (partial)
- [X] T067 Update `packages/testing/fixtures/seeds/README.md` to describe the `*_sku.csv` fixtures (fictional SKUs `EJ-9001` and so on) next to the older variant-id ones per FR-032 (partial)

## Phase 12: Convergence

- [X] T068 Record refused governance attempts (`import_self_approval`, `import_reason_required`, `import_conflict`, and a refused rollback) with actor, action, dataset id and reason key, in a way that survives the request's rollback (a structured `SEED_REFUSED` log line or a separate audit write), and stop labelling them `UPLOAD_REJECTED`, in `services/forecast-service/src/imports_api.py`, with a test using `caplog` or the audit table in `services/forecast-service/tests/test_seed_governance.py` per FR-028 and SC-008 (partial)
- [X] T069 Verify the commands in `specs/008-mmi-7-predictive-seed-import/quickstart.md` on a clean checkout (the repo has no `uv.lock`; CI builds a venv and installs the packages) and replace any that fail with the working procedure per the quickstart purpose (partial)

## Phase 13: Convergence

- [X] T070 Re-run `services/forecast-service/tests/test_seed_concurrency.py` against PostgreSQL (`RUN_PG_MIGRATIONS=1`, `MMI_PG_EXTERNAL_PORT`, `infra/postgres/init.sql` applied) now that T059 moved it to the SKU fixtures and a required `sku_map`, and record the result in `specs/008-mmi-7-predictive-seed-import/research.md` per FR-016 and plan D5 (partial)
- [X] T071 Update the stale mock in `apps/web/tests/e2e/forms-feedback.spec.ts` (the import-wizard test around line 314 still returns the `ID de variante Siweb` header and a `variant_id` mapping) to the SKU layout used by `apps/web/tests/e2e/import.spec.ts` per FR-007 (partial)

## Phase 14: Convergence

- [X] T072 Contract first for the reason rules: in `specs/008-mmi-7-predictive-seed-import/contracts/seed-governance.delta.md`, `data-model.md` and the schemas `packages/contracts/dto/seed_dataset.v1.schema.json` and `seed_dataset_summary.v1.schema.json`, replace the free-text `rollback_reason` and `self_activated_reason` with a reason code plus a detail of at most 100 characters (request bodies `reason_code`, `reason_detail`; the lists of codes from FR-033), mark the detail as admins-only, add the error key for an unknown code to `packages/contracts/errors/error_codes.json` and the documentation table, regenerate the types and the baseline, and extend `packages/contracts/tests/test_seed_governance_schema.py` per FR-033 and Constitution IV (contradicts)
- [X] T073 Build the SKU lookup once as SKU to a set of products in a shared helper (for example `lookups_from_series(series)` in `services/forecast-service/src/seeds/`), use it in `imports_api.py` (`known_variants`) and `worker.py` (`process_imports`), make `_sku_index` in `seeds/validation.py` accept it, and add a test in `services/forecast-service/tests/test_seed_sku.py` that two products with exactly the same SKU quarantine every row carrying it as `import_ambiguous_sku` per FR-007 (partial)
- [X] T074 Guard rollback against a simultaneous rollback: include `status == "active"` in the update in `rollback` (`services/forecast-service/src/seeds/lifecycle.py`), raise `import_conflict` when no row changed, add a unit test in `tests/test_seed_governance.py`, and add a two-rollbacks case to `services/forecast-service/tests/test_seed_concurrency.py` (PostgreSQL) per FR-019 and the concurrency edge case (partial)
- [X] T075 Implement the reason rules in the forecast service: accept `reason_code` and an optional `reason_detail` (at most 100 characters) on rollback and on owner/admin self-activation in `seeds/lifecycle.py` and `imports_api.py`, validate the code against the fixed lists of FR-033, store code and detail (amend migration `services/forecast-service/migrations/versions/0005_seed_governance.py` and `src/db/tables.py`: `rollback_reason_code`, `rollback_reason_detail`, `self_activation_reason_code`, `self_activation_reason_detail`), and put the code, never the detail, in the audit entries of `seed.rolled_back` and `seed.self_activated`, with tests in `tests/test_seed_governance.py` and `tests/test_seed_audit.py` per FR-033, FR-029 and FR-016 (contradicts)
- [X] T076 Show the chosen reason to everyone and the detail only to admins: make `GET /imports` (`imports_api.py`, `lc.list_datasets`) drop the detail unless the caller has the admin role, and add tests in `tests/test_imports_api.py` for a viewer, a buyer and an admin per FR-033 (contradicts)
- [X] T077 Forward `reason_code` and `reason_detail` from the gateway on activate and rollback in `services/api-bff/src/routes/imports.py` (replace the single `reason`), and update `services/api-bff/tests/test_imports_mfa.py` and `test_imports_rbac.py` per FR-033 (partial)
- [X] T078 Web: replace the free-text reason fields with a pick-list (Spanish labels for each code) and an optional detail input limited to 100 characters in the rollback and self-activation flows (`apps/web/src/features/imports/ImportScreen.tsx`, `importsModel.ts`, `apps/web/src/api/client.ts`, `apps/web/src/i18n/es-ES.json`), show the chosen reason in the dataset list and the detail only when the server sends it, and update `apps/web/tests/unit/ImportScreen.test.tsx`, `imports-model.test.ts` and `apps/web/tests/e2e/import.spec.ts` per FR-033 and FR-031 (contradicts)
- [X] T079 Add the equivalence test for SC-012 in `services/forecast-service/tests/test_seed_worker_sku.py`: the same SKU file, catalogue and mapping give identical accepted and quarantined counts and reasons when validated through `POST /imports/{id}/validate` and through `worker.process_imports` per FR-024 and SC-012 (partial)
- [X] T080 Update `docs/adr/020-seed-provenance.md` (the MMI-7 amendment still says a written reason of 1 to 300 characters) and `research.md` to describe the pick-list reason with a short admin-only detail, and re-run the full suites and lint per FR-033 (partial)

## Phase 15: Convergence

- [X] T081 Update the activation and rollback rules in `specs/008-mmi-7-predictive-seed-import/data-model.md` (lines 20 and 21) so a self-activation and a rollback each need a reason from the fixed list (FR-033) with an optional detail of at most 100 characters that is returned to admins only and never audited, instead of "a written reason" per FR-033 and FR-016 (partial)
- [X] T082 Mark decisions D2 and D4 in `specs/008-mmi-7-predictive-seed-import/research.md` as superseded by the section "Correction after review (2026-11-09, T072 to T080)" (or reword them to the pick-list rule) so the decisions list matches the spec per FR-033 (partial)
- [X] T083 Reword the test title at `apps/web/tests/unit/ImportScreen.test.tsx:241` ("a written reason") to describe the reason pick-list and its guidance per FR-033 (partial)

## Phase 16: Convergence

- [X] T084 Reject non-printable characters (for example NUL, `\u0000`) in the reason detail: in `_reason` (`services/forecast-service/src/seeds/lifecycle.py`) refuse with `import_reason_invalid` (or drop them before the blank collapse), and add a case with `"a\x00b"` to `services/forecast-service/tests/test_seed_governance.py` for rollback and self-activation, so PostgreSQL never receives a NUL and the answer is the clean 422 instead of a server error per FR-033 and FR-016 (partial)
- [X] T085 Make `worker.process_imports` (`services/forecast-service/src/worker.py`) check for a queued, unfinished validation job with one SELECT first and return early when there is none, fetching the inventory export only when there is work; add a test in `services/forecast-service/tests/test_seed_worker_sku.py` that the source is not called on an empty queue, and that a queued job still defers when inventory is unavailable per FR-024 and plan: background jobs (partial)
- [ ] T086 Optional, lower priority: give validation (not the dry run) a light lookup so it does not download the whole series export: add an inventory endpoint that returns only `variant_id` and `sku`, use it in `known_variants` of `services/forecast-service/src/imports_api.py` for `validate` only (the dry run keeps the full series), document it in `specs/008-mmi-7-predictive-seed-import/contracts/seed-governance.delta.md`, and keep `lookups_from_series` the single place that builds the lookup (SC-012 equivalence test must still pass) per FR-007 and SC-012 (partial)
