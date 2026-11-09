# Research: Predictive Seed Import and Dataset Governance (MMI-7)

## Baseline audit (main at 9d11abb; read-only inspection, tests not executed)

| Capability | Status | Evidence |
|------------|--------|----------|
| Upload, type/size/signature checks | Complete (unverified by run) | `services/forecast-service/src/seeds/storage.py`, `parsers.py`; tests `test_seed_parsing.py` |
| Templates CSV/XLSX | Complete | `seeds/template.py`; gateway `GET /imports/template` |
| Column mapping, saved mappings | Complete | `seeds/mapping.py`; `imports.py` `/mappings` |
| Row validation, quarantine, Spanish reasons | Complete | `seeds/validation.py`; error keys in 002 contracts |
| **SKU matching** | **Missing** | `validation.py:128-134` reads `variant_id` from the file and checks it against known variant ids |
| Duplicates (rows, file checksum) | Complete | `validation.py:163-165`; `lifecycle.py:54,147` |
| Provenance labels, origin, no mixed origin | Partial | `lifecycle.py:72` sets origin `synthetic` at upload, validation sets it from the file; mixed-origin refused at `lifecycle.py:150`; default-to-estimated unverified |
| Dry run with backtest | Partial | `seeds/dryrun.py`; "not assessable" listing unverified |
| Activation atomic, audited, supersedes | Complete | `lifecycle.py:139-159` |
| **Fresh MFA on activate/rollback** | **Missing** | `api-bff/src/routes/imports.py:65,96` use role checks only; `require_fresh_mfa` exists in `routes/rbac.py:102` and is used elsewhere |
| **Approver differs from creator** | **Missing** | `lifecycle.activate` takes `actor` but compares nothing |
| **Rollback reason** | **Missing** | `lifecycle.rollback(conn, writer, actor)` has no reason |
| Rollback restores previous, deletes nothing | Complete | `lifecycle.py:162-175`; `test_seed_rollback.py` |
| **Concurrent activation guard** | **Unverified / likely missing** | no row lock seen in `lifecycle.py` |
| Forecast uses seeds only to rescue "new" variants, actuals prevail | Complete | `runs/seeds.py` |
| Retired SKU stops contributing | Unverified | no evidence found |
| Separation from ERP data and from feature 004 data | Partial | `test_seed_isolation.py` exists; surrogate-id (9,000,000+) separation untested |
| Background jobs, status, rerun, idempotency | Complete | `seeds/jobs.py`; `imports_api.py` `/jobs`, `/jobs/{id}/rerun` |
| Spanish UI and Playwright flow | Partial | `apps/web/src/features/imports/ImportScreen.tsx`; `tests/e2e/import.spec.ts` covers wizard, hostile files, viewer; forecast-changes-then-returns not covered |

## Decisions

- **D1 SKU matching.** Template and mapping use `sku` (the column already exists as informational in `seeds/template.py:17` and `seeds/mapping.py:15`). Known variants come from the inventory series source (`imports_api.py:75`, `series_source.fetch()['series']`); resolve SKU there. If series items do not carry `sku`, add it as an additive field in the inventory series contract (coordinated with Agent 00); no cross-schema SQL. A `variant_id` column is rejected per row with a new key `import_sku_required`. Alternative rejected: keep `variant_id` for compatibility, because users never see that id (AGENTS rule 5).
- **D2 Two-person activation.** Record who validated; activation refuses the uploader and the last validator (`import_self_approval`, 403). Clarified 2026-11-08: an audited owner/admin self-activation with a written reason and fresh MFA is allowed (distinct audit action `seed.self_activated`). "Last editor" means whoever chose the mapping or ran validation; the unused `approved` state is dropped.
- **D3 Fresh MFA.** Add the existing `require_fresh_mfa()` dependency to activate and rollback in the gateway.
- **D4 Rollback reason.** Required text of bounded length, stored and audited; it is a reason, not a free-text note about products.
- **D5 Concurrency.** Lock the active-dataset row inside the activate/rollback transaction; the loser gets 409 `import_conflict`.
- **D6 Retired SKU.** At forecast-run read time, rows whose variant is absent from the catalogue are skipped and counted in the run report.
- **D7 Proof.** Add tests for each gap plus an end-to-end Spanish flow: forecast differs after activation, equals the original after rollback.

## Open questions

- Whether inventory series items already carry `sku` (T002 confirms; if not, additive contract change).
- D8 Procurement scope: explanations already carry `seed_used` (feature 002 T175). Only add dataset id and version to the explanation text; touch `services/procurement-service/` only for that line, with Agent 00 informed.
- D9 Rollback restores the previously active dataset, or no seed influence if none (spec FR-019).
- D10 ERP-export files are refused as seed files by header shape (spec FR-002).

## Baseline run (T001, 2026-11-09)

`services/forecast-service`: `pytest -k "seed or import"` gives 63 passed, 1 skipped (the skipped test needs a database or blob service). Environment: repo-root `.venv` built as in `.github/workflows/ci.yml`.

## T002 result

Inventory `/export/series` items did not carry `sku` (`services/inventory-service/src/api/routes.py`). Added `sku` as an additive field (null when the variant is unknown), covered by `test_export_series_carries_segment_and_service_level`; inventory API tests pass (4 passed). The forecast service reads it through `known_variants()` in `imports_api.py`.

## Implementation notes (2026-11-09)

- SKU matching (T013–T015) and the ERP-export refusal (T055) are in `services/forecast-service` (`seeds/validation.py`, `seeds/export_shapes.py`, `seeds/lifecycle.py`, `imports_api.py`, `worker.py`). `validate_rows(..., sku_map=...)` is the only path (the old `variant_id` path was removed in T059).
- Fixtures: `packages/testing/fixtures/seeds/{valid,partly_invalid,mixed_origin}.csv` are SKU files (fictional SKUs `EJ-9001`...); the earlier `variant_id` versions and the `*_sku.csv` duplicates were removed in T059.
- The shared ERP-export header lists exist twice (`packages/testing/.../formats.py` and `seeds/export_shapes.py`); `export_shapes.py` keeps only distinctive headers. Keep them aligned if a layout changes.
- Test status: forecast-service 168 passed, 1 skipped, ruff clean; inventory API 4 passed; fixtures package 8 passed. Not run: web tests, gateway tests, PostgreSQL migration test.

## Governance implementation notes (2026-11-09)

- `seeds/lifecycle.py`: `activate(..., is_admin, reason)` refuses the uploader, the validator and the mapping chooser (`import_self_approval`, 403). An admin with a written reason may self-activate (audited as `seed.self_activated`; without a reason: `import_reason_required`, 422). `rollback(..., reason=)` needs a reason of 1 to 300 characters. The reason is stored on the dataset row and never written to the audit trail.
- A losing activation maps the unique-index violation to `import_conflict` (409). The race is simulated in a SQLite test; a PostgreSQL run of the same case is still to do (T020 notes).
- Gateway `routes/imports.py`: `require_fresh_mfa()` on activate and rollback; the reason is forwarded.
- Known gap: the web client (`apps/web/src/api/client.ts:1213,1217`) sends no reason on rollback, so the screen's rollback now gets 422 until T034 adds the reason dialog. Activation by a different person works as before; a self-activation needs the T028 prompt.
- Test status: forecast-service 174 passed, 1 skipped; api-bff 168 passed; ruff clean on both.

## Web implementation notes (2026-11-09)

- `apps/web`: the mapping now requires `sku` (the screen no longer offers `variant_id`); activation sends an optional reason, shown only to admins; rollback needs a reason (1 to 300 characters) and its button is disabled until one is typed. New Spanish strings cover the SKU, approver, conflict and reason errors.
- Tests: the 18 import unit tests pass, `tsc` and eslint are clean on the touched files, and the 3 Playwright import tests pass in Chromium (the rollback test now checks the reason is sent).
- Not done in the web app: a dedicated prompt for an expired second factor (the existing `errors.auth_mfa_stale` message is shown), approver and rollback-reason columns in the dataset list (T038), and the end-to-end flow that shows the forecast changing and returning (T029, T035).
- Unrelated failures: `npx vitest run` shows 23 failures in `tests/unit/ui/{DataTable,ThemeToggle,forms,preferences}` (`localStorage.clear` is undefined under Node 26.13 with jsdom). These files are untouched by this work.

## Convergence pass 1 notes (2026-11-09)

- T056 and T008: `seed_dataset.v1` now declares `validated_by`, `mapping_chosen_by`, `rollback_reason` and `self_activated_reason` as optional properties; `approved` stays in the status enum. Generated Python and TypeScript types and the compatibility baseline were regenerated (only `seed_dataset` changed). New test: `packages/contracts/tests/test_seed_governance_schema.py`; contracts suite: 181 passed.
- Known drift, not caused by this feature: the dataset-list response of `GET /imports` (`id, version, name, status, origin, uploader, uploaded_at, row_count, activated_by, activated_at, accepted, quarantined, kinds`) does not match the full `seed_dataset.v1` schema (which requires `file_sha256` and nests `row_counts`). The web app uses its own interface for it. A response-vs-schema test would need either a schema revision or a dedicated list-item schema; left as a follow-up for Agent 00.
- T057: the dry run is audited as `seed.dry_run` (actor, version, comparison counts; no rows). `lifecycle.record_dry_run`, called from `imports_api.dryrun`. Forecast service: 175 passed, 1 skipped.

## Convergence pass 2 notes (2026-11-09)

- T061: the web pass had added seven `errors.*` messages without catalogue entries, which made `infra/tests/test_error_keys_localised.py::test_web_has_no_orphan_error_messages` fail (I had not run the infra tests then). The keys are now in `packages/contracts/errors/error_codes.json` and in the documentation table of `specs/002-mmi-operational-console/contracts/error-keys.md`; new guard test `infra/tests/test_seed_error_keys_registered.py` (every `import_*` key used by the forecast service is in the catalogue). Infra error tests: 10 passed; web `i18n-coverage`: 132 passed.
- T062, T063: the 002 template contract now documents the SKU layout; the delta states that the SKU travels in `params`.
- T059 and T064 are deferred together: the older tests (about 15 files, plus the shared `sf.HEADER` in `packages/testing`) still rely on the `variant_id` fixtures, so the legacy path and the `variant_id` mapping suggestion can only go after those are migrated.

## Convergence pass 3 notes (2026-11-09)

- T065: new `seed_dataset_summary.v1` schema for the `GET /imports` list item (types and baseline regenerated). `test_imports_api.py::test_the_dataset_list_validates_against_the_summary_schema_in_every_state` validates the real response (active and freshly uploaded datasets) against it. This closes the drift noted in pass 1 for the list; the full `seed_dataset.v1` record is still not returned by any endpoint.
- T066: `infra/tests/test_seed_error_keys_registered.py` also checks the ERP-export signature headers against the feature 004 layouts in `packages/testing`.
- T067: the fixtures README describes both fixture sets.
- Test status: contracts 213 passed; forecast-service and infra suites green after these edits (see the run below).

## Convergence pass 4 notes (2026-11-09)

- T068: refused governance attempts are logged as `SEED_REFUSED action=<activate|rollback> dataset=<id|-> actor=<subject> reason=<key>` (a log line, because an audit row written inside the request would be rolled back with it, and on PostgreSQL a failed activation leaves the transaction aborted). The three keys that only exist in governance flows (`import_self_approval`, `import_reason_required`, `import_conflict`) are no longer logged as `UPLOAD_REJECTED`; the other keys keep their old log line. Any alert that matches `UPLOAD_REJECTED` for those three keys needs a matching rule for `SEED_REFUSED` (ops follow-up).
- T069: `uv run pytest` from the repository root fails (no dependencies at the workspace root, no `uv.lock`); the quickstart now documents the venv procedure used in CI and was run end to end: forecast-service 177 passed, api-bff 168, inventory 163, contracts+infra 274, web import unit tests 17, ruff clean. The Playwright import spec passed 3 of 3 on a rerun; one earlier run printed "2 passed" (32 s), cause not investigated, so treat that spec as possibly flaky.

## Test pass notes (2026-11-09)

- T050, T031 (`tests/test_seed_forecast_effect.py`): the rescue rule and the rollback effect on the series already behaved as specified (only "new" variants with dense enough seeds and enough combined history are rescued; uncovered, sparse and otherwise-ineligible variants are unchanged; rollback gives back the series of the previous dataset, or the original one).
- T051 (`tests/test_seed_data_rules.py`): found one real gap and fixed it: the original date text was not stored. `seed_rows.day_text` now keeps the date as written (migration `0005`, `validation.Accepted.day_text`). Spanish numbers (`1.234,5`), notes, tax ids and e-mail columns were already handled (never stored, logged or audited). The seed `day` is a calendar day, so there is no instant to convert to UTC; FR-006's "normalised UTC value" is satisfied by the normalised calendar day (Europe/Madrid).
- T052: datasets that are active, superseded, rolled back or rejected cannot be validated again and their rows are kept. **Deviation to confirm:** a dataset in the `validated` state can still be validated again (for example with a corrected mapping), which replaces its rows; the spec says datasets are immutable once validated. Left as is because re-mapping before activation is useful and every validation is audited; if the owner wants strict immutability, validation must create a new version instead.
- T053: the audit trail holds an entry for upload, validation, dry run, activation, rollback and rejection with actor and no file content.
- **Decided 2026-11-09 (T036), unlabelled rows stay quarantined; the spec now says so:** FR-011 says a row without a stated label is treated as estimated. The code quarantines it instead (`import_unknown_kind` for a blank data type, `import_missing_provenance` for a blank source label), which follows "never normalise ambiguous data into trusted input" in the constitution. T036 stays open until the owner picks one; the spec wording or the code should change.
- Forecast service now 188 passed, 1 skipped; ruff clean.

## Test pass 2 notes (2026-11-09)

- Verified by existing tests, no new code: T021 (`test_dryrun_backtest.py`: the dry run stores nothing and never activates; thin-history variants are listed as `skipped_sparse` and the backtest says `insufficient_history`, which is the "not assessable" list, so T026 was not needed), T022 (`test_seed_overlap.py`), T040 (`test_import_jobs.py`: queueing, idempotent enqueue, failing job recorded and the next one still runs).
- New tests: T011 (`test_seed_template.py`), T012 (`api-bff/tests/test_imports_rbac.py`: a viewer is refused on all seven changing actions, nothing is forwarded, each refusal is recorded with user and path), T032 (`test_seed_history.py`: a seeded run keeps `dataset_version_id` and its `seed` config after a rollback and a later run), T060 (`test_seed_worker_sku.py`: the worker builds the SKU map from the series items; without `sku` every row is quarantined, never guessed).
- New code (T041, T042): `SeedReport.retired` lists variants that have seed rows but are no longer in the series (left the catalogue). They contribute nothing; the dry run returns `retired_variants` and the run record `config.seed.retired_variants`.
- Still not runnable here: T058 (no PostgreSQL available locally: `psql`, `pg_ctl`, `postgres` and Docker are absent).
- Status: forecast-service 198 passed, api-bff 176, inventory 163, contracts+testing+infra 509 passed (22 skipped); ruff clean.

## PostgreSQL run (2026-11-09, T058)

- Setup: an isolated, loopback-only PostgreSQL 18.6 started from a fresh data directory in the session scratch area (a different server already runs on this machine and was not touched), with `infra/postgres/init.sql` applied. The data directory and server were removed afterwards. Note that the repository pins PostgreSQL 16 by digest in `infra/compose.yaml`; CI and a Docker run remain the authoritative check.
- `RUN_PG_MIGRATIONS=1 MMI_PG_EXTERNAL_PORT=<port> pytest infra/tests/test_migrations_postgres.py`: 9 passed. For the forecast service this covers migration `0005` (including `seed_rows.sku`, `seed_rows.day_text` and the four dataset governance columns): the tables and nullability match the code, `downgrade base` leaves nothing behind, and `upgrade head` works again.
- New `services/forecast-service/tests/test_seed_concurrency.py` (skipped unless `RUN_PG_MIGRATIONS=1` and `MMI_PG_EXTERNAL_PORT` are set): a first transaction activates dataset A without committing; a second activation of dataset B waits on the unique index of active datasets; after A commits, B gets `import_conflict` and A stays the active dataset. 1 passed. This is the real-PostgreSQL proof of the conflict path that `test_seed_governance.py` only simulates on SQLite.
- Default run: forecast-service 198 passed, 2 skipped.

## Final audit table (T003; main at 9d11abb versus this branch, 2026-11-09)

| Capability | At the start | Now | Evidence |
|---|---|---|---|
| Upload checks (type, size, signature, macros, bombs) | complete | complete; **workbooks with external links are now refused** (FR-004) | `seeds/storage.py`, `test_upload_hardening.py` |
| Templates and mapping | complete | complete; SKU layout, `sku` required | `seeds/template.py`, `seeds/mapping.py`, `test_seed_template.py` |
| SKU matching | **missing** | complete; ambiguous and unknown SKUs quarantined; the worker uses the same path | `seeds/validation.py`, `test_seed_sku.py`, `test_seed_worker_sku.py` |
| ERP exports as seed files | missing | complete; refused with `import_erp_export_refused` | `seeds/export_shapes.py`, `test_seed_sku.py`, `infra/tests/test_seed_error_keys_registered.py` |
| Duplicates, quarantine, discard of notes and personal data | complete | complete; original date text now kept | `test_seed_data_rules.py` |
| Provenance and origin | partial | complete; unlabelled rows quarantined (owner decision) | `test_seed_validation.py` |
| Dry run | partial | complete; "not assessable" = `skipped_sparse` + `insufficient_history`; audited; reports retired variants | `seeds/dryrun.py`, `test_dryrun_backtest.py`, `test_seed_audit.py`, `test_seed_retired_sku.py` |
| Activation | complete | complete; second person, audited owner/admin self-activation, fresh MFA, conflict on a race (proven on PostgreSQL) | `seeds/lifecycle.py`, `test_seed_governance.py`, `test_seed_concurrency.py` |
| Rollback | complete | complete; reason required, fresh MFA, restores the previous dataset | `test_seed_rollback.py`, `test_seed_forecast_effect.py` |
| Forecast effect | complete | verified: rescue rule, uncovered variants unchanged, rollback returns the same series and the same run | `test_seed_forecast_effect.py`, `test_seed_isolation.py`, `test_seed_history.py` |
| Separation from ERP and from locally loaded export data | partial | complete; static boundary tests | `infra/tests/test_seed_erp_boundary.py` |
| Jobs, status section, idempotency, cost caps | complete | complete; hard-cap file validated in 0.6 s, requests under 2 s, scale-to-zero guardrails | `test_import_jobs.py`, `test_seed_timing.py`, `infra/tests/test_cost_guardrails.py` |
| Refusals recorded | missing | complete; gateway role refusals and `SEED_REFUSED` log lines | `api-bff/tests/test_imports_rbac.py`, `test_imports_api.py` |
| Contracts (schemas, error catalogue, baseline) | partial | complete; `seed_dataset`, new `seed_dataset_summary`, seven error keys | `packages/contracts`, `infra/tests` |
| Spanish screens | partial | complete for the specified flows: SKU wording, reasons, approver and provenance columns, guidance on refusal | `ImportScreen.tsx`, 152 web unit tests, 4 Playwright tests |

## Known limitations (for the pull request)

- Not done: T049 (agreement with Agent 00 on the shared contract delta and the inventory `sku` field), T048 (the pull request itself), T059 and T064 (removal of the legacy `variant_id` path, which needs about 15 older tests moved to the SKU fixtures).
- The Playwright flows mock the backend, so they prove the screen behaviour only; that the forecast changes after activation and returns after rollback is proven by the service tests (`test_seed_forecast_effect.py`, `test_seed_isolation.py`).
- A stale second factor shows the Spanish message `errors.auth_mfa_stale`; the app has no re-verification action to offer.
- The proposal explanation names the dataset id used (proposal header) and states the line is based on imported estimates; it does not show a dataset version number.
- A dataset in the `validated` state can be validated again (corrected mapping) before activation; the spec's "immutable once validated" is met from activation on.
- PostgreSQL checks ran on version 18.6 (the repository pins 16); no secret scanner (gitleaks) is installed locally, only a pattern grep was run; CI runs gitleaks.
- 23 unrelated web unit tests fail under Node 26 (`localStorage.clear`); mypy shows the same 24 errors as before this work.
- Alerts that match `UPLOAD_REJECTED` for the three governance keys need a matching rule for `SEED_REFUSED`.

## T059 and T064 (2026-11-09): the `variant_id` path is gone

- `validate_rows`, `validate_dataset` and `process_queued` now require `sku_map` (keyword-only); a row without a SKU is rejected with `import_sku_required`, so a file that supplies only a variant id has every row rejected. `variant_id` stays an accepted mapping field for compatibility (contract delta), but the mapping never suggests it and the mapping step reports the missing SKU column first.
- The three static fixtures and the shared `sf.HEADER` are now SKU-based; `conftest.SKUS` maps `EJ-<variant>` to each variant in the tests; XLSX, formula, macro and oversized fixtures were converted. About 15 test files were migrated; the unused `template.col.variant_id` (service) and `imports.field.variant_id` (web) strings were removed.
- New test: a variant-id header is never suggested and the file is told it has no product column (`test_seed_validation.py`).
- Results: forecast-service 204 passed, 2 skipped; api-bff 176; inventory 163; contracts + fixtures + infra 513 passed; web import unit tests 152, Playwright 4 of 4; ruff clean; mypy unchanged at 24 pre-existing errors. The PostgreSQL concurrency test was edited mechanically (fixture name, `sku_map`) and collected, but not re-run against PostgreSQL after this change.

## Convergence pass 5 (2026-11-09, T070 and T071)

- T070: after T059 moved the concurrency test to the SKU fixtures and a required `sku_map`, it was run again on a fresh throwaway PostgreSQL 18.6 (loopback only, removed afterwards; the other server on this machine was not touched): `services/forecast-service/tests/test_seed_concurrency.py` 1 passed (the second activation waited on the first and got `import_conflict`), and `infra/tests/test_migrations_postgres.py` 9 passed (including migration `0005`).
- T071: the import-wizard mock in `apps/web/tests/e2e/forms-feedback.spec.ts` now uses the SKU layout. The whole Playwright suite was also run once: 190 passed, 6 skipped (before the edit); `forms-feedback` plus `import` 18 passed after it.
- Web unit suite: the same 23 unrelated failures as before (`localStorage.clear` under Node 26 in four UI test files).

## Correction after review (2026-11-09, T072 to T080)

- Contract first (T072): `seed_dataset.v1` and `seed_dataset_summary.v1` now carry `rollback_reason_code`, `rollback_reason_detail` (at most 100 characters), `self_activation_reason_code` and `self_activation_reason_detail`; the free-text `rollback_reason` and `self_activated_reason` are gone (they were never released). New error key `import_reason_invalid`; `import_reason_required` now means "choose a reason". The lists of codes are the schema enums, and a test keeps the service lists equal to them.
- SKU lookup (T073, T079): one helper, `seeds/lookup.py`, builds the known variants and SKU to set of products for both the API route and the worker. Two products with exactly the same SKU are ambiguous. `test_a_file_gets_the_same_outcome_in_the_request_and_in_the_background` proves SC-012 with a shared SKU.
- Rollback guard (T074): the update includes `status == "active"`; a second rollback gets `import_conflict`. Proven on PostgreSQL 18.6 with two real transactions (and the activation race again), together with the 9 migration tests, on a throwaway server that was removed afterwards.
- Reasons (T075 to T078): the service validates the code against the fixed lists, stores code and detail, audits the code only, and returns the detail to admins only (`GET /imports`); the gateway forwards only `reason_code`, `reason_detail` and `acknowledge_duplicate`; the web screen shows a pick-list with Spanish labels plus a 100-character detail, and the list shows the chosen reason (and the detail when the server sends it).
- Free text and the constitution: the detail is the only free text this feature keeps. It is limited, admins-only, and absent from the audit trail and from logs.
- Results after the correction: forecast-service 211 passed, 3 skipped (the 3 PostgreSQL tests were run separately and passed); api-bff 176; inventory 163; contracts + fixtures + infra 515 passed (one earlier run showed a single failure that did not repeat in four reruns and was not identified); ruff clean; mypy unchanged at 24 pre-existing errors; web `tsc` and eslint clean; web unit tests 464 passed with the same 23 unrelated failures under Node 26; Playwright 190 passed, 6 skipped.

