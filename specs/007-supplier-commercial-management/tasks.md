# Tasks: Supplier Commercial Management (MMI-6)

**Input**: `specs/007-supplier-commercial-management/` (spec, plan, research, data-model, contracts, quickstart)

**Tests**: Included. The project rules require tests before implementation within a story, and the spec asks for unit, contract, integration, security and Playwright coverage. Synthetic fixtures from `packages/testing` only.

**Format**: `- [ ] ID [P] [Story] Description with path` (`[P]` = parallel, different files)

**Paths**: service `services/procurement-service/` (PS), BFF `services/api-bff/`, web `apps/web/`, contracts `packages/contracts/`. Last migration is `0011_suppliers.py`.

**Baseline-only requirements**: FR-007, 008, 009, 013, 015, 024 and 031 are already implemented and tested (see research.md audit rows 2 to 5, 7, 20). They get no new task; T002 runs their tests and T010 records the named test per requirement. FR-006 (duplicate warning) is checked in T013.

## Phase 1: Setup and audit baseline

- [X] T001 Prepare the Python test environment: there is no `uv.lock`, so run `uv sync` from the repository root (public PyPI only), confirm `.venv` and `uv.lock` are gitignored or leave them untracked, and write the exact working test command into `specs/007-supplier-commercial-management/quickstart.md` step 1
- [X] T002 Run the baseline suites from quickstart step 1 and record pass/fail per audit row in `research.md` (turn "complete by reading" into verified; reclassify failures as broken)
- [X] T003 [P] Confirm with Agent 00 (Jira MMI-1 thread) that `Idempotency-Key`, the new error codes and the daily exchange-rate job are acceptable shared changes; note the answer in `research.md` section C — done: Agent 00 (feature 005) is merged to main; its gateway idempotency test now records the two terms saves
- [X] T004 [P] Check `git diff --stat main` touches only files listed in plan.md Project Structure (guard for FR-033)

## Phase 2: Foundational (blocks all stories)

- [X] T005 Contract first: in `packages/contracts/` add error codes `idempotency_key_reuse`, `invalid_idempotency_key`, `fx_rate_missing`, `fx_rate_stale` to `errors/error_codes.json`, document the `Idempotency-Key` header on the two terms PUT operations, and regenerate types (done: the four codes are in `error_codes.json`, the web catalogue and the feature-002 `error-keys.md` table that a guard test requires; there is no HTTP contract file in `packages/contracts`, so the header is documented in `contracts/supplier-terms-api.md` and the code meanings; no types depend on error codes)
- [X] T006 [P] Contract first: add the optional `expected_delivery_date` field to the proposal-line explanation schema in `packages/contracts/` and regenerate types (done: schema and Python model regenerated, compatibility tests pass; the TypeScript types in `apps/web/src/api/generated` are NOT regenerated yet because the generator downloads an npm package, so run `packages/contracts/tools/codegen.py` where npm is available before the PR)
- [X] T007 [P] Add Spanish messages for the new codes and any new supplier-screen strings to `services/procurement-service/src/locale/es-ES.json` and the web text catalogue under `apps/web/src/` (done for the four error codes in `apps/web/src/i18n/es-ES.json`; the service file only holds export sheet texts, so it is untouched; screen strings are added by the UI tasks)
- [X] T008 Add migration `services/procurement-service/migrations/versions/0012_terms_idempotency_fx_rates.py` creating `terms_idempotency` and `fx_rates` per data-model.md, and the tables in `services/procurement-service/src/db/tables.py`
- [X] T009 [P] Add `record_refusal(conn, actor, action, entity, entity_id, code, status)` to `services/procurement-service/src/audit/chain.py`, appending an entry without any request body (done with `tests/test_audit_refusal.py`; `action` must be `<area>.refused`)

## Phase 3: User Story 1 - Audit evidence (P1)

**Goal**: audit table complete and verified. **Independent test**: every row has a status and evidence; no row unclassified.

- [X] T010 [US1] Review each audit row in `research.md` against T002 results; fix statuses, add file and line evidence, and name the proving test per baseline-only requirement
- [X] T011 [US1] Check every non-complete row names a real task ID in its "Closes via" column and no row is orphaned (FR-002)

## Phase 4: User Story 2 - Supplier master and terms (P1)

**Goal**: CRUD persists, validation, roles, safe deactivation. **Independent test**: create, read back after reload, edit, deactivate, reactivate; viewer read-only.

- [X] T012 [P] [US2] Test: server-side role enforcement on every change route (viewer refused on supplier, terms, link, bulk) in `services/procurement-service/tests/test_terms_roles.py` (done: scans the 13 change routes of the supplier, terms, override, link and bulk families, including routes wrapped by included routers; all refuse viewers with 403 and anonymous callers with 401)
- [X] T013 [P] [US2] Test: persistence round-trip across a new connection (supplier, terms, links) and duplicate-name warning without auto-merge in `services/procurement-service/tests/test_supplier_persistence.py` (done as a round trip across committed transactions; the test engine is one shared SQLite connection, so true cross-connection isolation waits for the PostgreSQL run in T049; the duplicate-name warning was already tested at `test_suppliers_service.py:45,82`)
- [X] T014 [P] [US2] Test: a proposal with a line for a deactivated supplier cannot be submitted or approved until reallocated (FR-037), in `services/procurement-service/tests/test_supplier_deactivation.py`. The preview, confirmation and review item (FR-005) already exist and are tested (`test_suppliers_service.py:106,116,138`), so they are not re-tested here
- [X] T015 [US2] Enforce any role check found missing by T012 in `services/procurement-service/src/api/terms.py` and `src/api/suppliers.py` (no-op: T012 found no missing check)
- [X] T016 [US2] Implement the approval block (audit row 23 confirms it is missing) in `services/procurement-service/src/approvals/workflow.py` `submit` and `decide`: refuse with a stable code while a line belongs to a deactivated supplier (done: code `proposal_has_deactivated_supplier`, HTTP 409, added to `error_codes.json`, the web catalogue and the 002 `error-keys.md` table; blocks submit and approve, still allows rejection; `api/proposals.py` returns 409 for it; tests in `test_supplier_deactivation.py` and `test_api_proposals.py`)
- [X] T017 [P] [US2] Playwright journey in `apps/web/tests/e2e/suppliers-terms-journey.spec.ts` (done: 7 tests pass under Node 20 against an in-test backend: saved terms persist across a reload and show in the history; a future-dated version leaves today's terms in force; a stale save names the newer version, stores nothing and recovers on reload; a viewer reads but cannot change; search narrows 100 suppliers; no ERP contact or variant id on screen; no serious accessibility problem). Creating a supplier, the duplicate warning, deactivation preview and bulk preview are already covered by `suppliers-manage.spec.ts`. The tests pass on the existing UI, so they are regression coverage; they were not mutation-checked
- [X] T018 [US2] Fix any UI defect T017 exposes in `apps/web/src/features/suppliers/SupplierForm.tsx`, `SupplierTermsEditor.tsx`, `SuppliersScreen.tsx` (no-op: T017 exposed no defect)

## Phase 5: User Story 3 - Effective dates, conflicts, idempotency (P1)

**Goal**: future-dated versions, stale-save rejection, retry safety. **Independent test**: quickstart step 3.

- [X] T019 [P] [US3] Test: same `Idempotency-Key` and body creates one version and replays with `Idempotent-Replay: true`; different body gives `idempotency_key_reuse`; malformed key gives `invalid_idempotency_key`, in `services/procurement-service/tests/test_terms_idempotency.py` (done: 10 tests in `test_terms_idempotency.py`; the key is checked before If-Match so a retry with a stale precondition is still a replay; only successful saves are remembered; the key is also scoped per supplier-terms vs override)
- [X] T020 [P] [US3] Test: same-start tie keeps the latest saved version and history marks the other superseded, in `services/procurement-service/tests/test_terms_versions.py` (done in `test_terms_versions.py` plus `test_terms_api.py`: the later saved of two same-day versions wins; added `version_statuses` (in force, planned, superseded, expired) to `terms/service.py` and a `status` field on each history item of `GET /suppliers/{id}/terms`)
- [X] T021 [US3] Implement idempotent save (key, request hash, result version) in `services/procurement-service/src/terms/service.py` and `src/terms/overrides.py`, wired in `src/api/terms.py` (depends on T005, T008) (done: new `terms/idempotency.py` (also holds `forget_older_than` for the T038 purge), `Idempotency-Key` handled in `api/terms.py` for both PUTs; a concurrent request with the same key gets a 412 and the retry replays the winner)
- [X] T022 [US3] Forward `Idempotency-Key` unchanged in the BFF terms routes in `services/api-bff/src/routes/api.py` (the two PUT terms handlers) and send a fresh key per save from `apps/web/src/features/suppliers/termsModel.ts` (done: BFF forwards the header in `routes/api.py` and `clients/procurement.py`, 3 tests in `test_terms_idempotency_forwarding.py`; web client sends it, `saveKeys` in `termsModel.ts` keeps one key per distinct save, used by both the supplier and the override editor; 4 unit tests)
- [X] T023 [US3] UI: show version history (who, when, in force, planned, superseded), end-date warning, and the stale-save conflict message with the newer version in `apps/web/src/features/suppliers/SupplierTermsEditor.tsx` (done: history shows each version's status and the editor warns when the terms in force end with nothing scheduled after them; conflict message and history table already existed; Playwright covers retry key reuse, statuses and the warning)
- [X] T024 [US3] Extend `suppliers-terms-journey.spec.ts` with future-dated version and two-session conflict scenarios (SC-003, SC-004) (done inside T017's file; the history statuses and end-date warning of T023 are still to build, with assertions to add then)

## Phase 6: User Story 5 - Proposals use local terms; ERP untouched (P1)

**Goal**: delivery date from terms, versions shown, ERP data unchanged. **Independent test**: quickstart steps 2 and 5.

- [X] T025 [P] [US5] Test: table-driven expected delivery date (order days, cutoff before/after, lead time, delivery weekdays) in `services/procurement-service/tests/test_terms_delivery_date.py` (done: 21 tests in `test_terms_delivery_date.py` covering order days, the cutoff in Madrid time with the cutoff minute inclusive, lead time, delivery weekdays and the group date)
- [X] T026 [P] [US5] Test: at least 20 synthetic scenarios (minimums, schedules, thresholds, discounts, overrides) assert supplier, quantity, date and cited terms version in `services/procurement-service/tests/test_terms_scenarios.py` (SC-005) (done: 25 scenarios in `test_terms_scenarios.py` through the real inputs builder and the database; they assert supplier choice, pack multiples, minimums, shortfalls, delivery dates and cited versions. Four first expectations were wrong because the optimizer avoids a supplier whose minimum or charge makes it dearer; those became paired scenarios (with and without the alternative supplier))
- [X] T027 [P] [US5] Test: ERP-owned data identical before and after supplier maintenance, and ERP unreachable still works, extending `tests/test_terms_no_erp.py` (SC-006, SC-009) (done in `test_terms_no_erp.py`: a full maintenance round and a proposal run make no network call, and every ERP-owned table (catalogue refs, ERP links, ERP costs, lot costs, cost-write requests) is identical before and after)
- [X] T028 [US5] First carry `order_days`, `order_cutoff_time`, `delivery_weekdays` and `payment_terms_days` from the effective terms through `services/procurement-service/src/proposals/inputs.py` into `SupplierTermsIn` in `src/proposals/model.py` (audit rows 11 and 12: they are stored but never reach the optimizer). Then implement pure `expected_delivery_date` in `services/procurement-service/src/terms/resolve.py` and add `explanation.terms.expected_delivery_date` in `src/proposals/generate.py` (depends on T006) (done: new pure module `terms/schedule.py` (not `resolve.py`) with `next_order_date`, `delivery_date`, `order_date_from`; `SupplierTermsIn` gained `next_order_date` and `delivery_weekdays`, set by `proposals/inputs.py` only when the supplier has order days or a cutoff, so suppliers without a schedule behave exactly as before; payment terms are deliberately not carried because no decision uses them; the date is also on each line's `explanation.terms.expected_delivery_date`, matching the T006 contract field)
- [X] T029 [US5] Show delivery date and terms version on the proposal line in `apps/web/src/features/proposals/ProposalLineExplanation.tsx` (done: each line's explanation shows "Entrega prevista" in Spanish format next to the terms versions, hidden for older proposals; the group table already showed the group date, which is now schedule-aware; 2 unit tests)
- [X] T030 [US5] Verify shortfalls against minimums and thresholds are shown and never drop a line (FR-022): extend the T026 scenarios with shortfall cases and fix `services/procurement-service/src/allocation/common.py` or `shortfall.py` for any failure (done as verification: the line is kept, the group is `shortfall` with the missing value, the line risk is `high` and the buyer gets an `accept` option; locked in by `test_10c`; no code change was needed)

## Phase 7: User Story 4 - Overrides, costs, provenance, currency (P2)

**Goal**: product-level overrides win, provenance visible, non-EUR suppliers handled by stored rates. **Independent test**: link one product to two suppliers with an override and verify the proposal; allocate with a fresh, stale and missing rate.

- [X] T031 [P] [US4] Test: a preferred supplier wins an otherwise equal tie, a clearly cheaper compliant supplier still wins, and each line states why its supplier was chosen and why the alternatives were not (FR-019, tie-break decided 2026-11-09), in `services/procurement-service/tests/test_preferred_fallback_reason.py` (done: 4 tests in `test_preferred_fallback_reason.py`; they exposed that a tie won by the preferred supplier was explained as "lowest cost", fixed in T033)
- [X] T032 [P] [US4] Test: manual cost differing from ERP cost keeps both values, flags the difference, overwrites nothing, in `services/procurement-service/tests/test_cost_provenance_difference.py` (done: `test_cost_provenance_difference.py`, 6 tests; the ERP version is never changed or removed, only its chain link moves to the newer version)
- [X] T033 [US4] Only if T031 shows a missing reason, implement the choice/alternatives reason text in `services/procurement-service/src/allocation/common.py` and its Spanish message in `es-ES.json` (if T031 fails) (done: new reason `preferred_supplier_on_tie` in `proposals/generate.py` with its Spanish text; allocation itself is unchanged)
- [X] T034 [US4] Show cost source, author, date and the ERP-versus-manual difference in `apps/web/src/features/suppliers/LinksPanel.tsx` and `OverrideEditor.tsx` (done: the links table shows who set the cost and the ERP cost with the difference and percentage, or "equal"; 4 unit tests)
- [X] T035 [US4] Playwright: the no-ERP-id check is already in `suppliers-terms-journey.spec.ts`; add only the bulk-assign per-row outcome after apply (preview is covered by `suppliers-manage.spec.ts`), in the same file (FR-017, FR-018) (done differently from the task text: `apply_batch` now returns an outcome per row (linked, already_linked, conflict_skipped, no_cost) and the screen lists them; proven by backend tests and 3 unit tests rather than a Playwright test, because the existing Playwright mock stops at the preview; the no-ERP-id check is in `suppliers-terms-journey.spec.ts`)
- [X] T036 [P] [US4] First make one public, read-only `GET https://api.frankfurter.dev/v2/providers/ecb/rates?base=EUR` by hand (no data sent; the only real network call in this plan, and nothing from it is committed except the synthetic fixture), record the real response shape and the behaviour for weekends and holidays in `research.md` D3, and build a synthetic fixture from that shape in `packages/testing`. Then test the rate job in `services/procurement-service/tests/test_fx_rates.py` with a fake HTTP transport and that fixture, including the purge of rows older than 400 days and of idempotency rows older than 7 days: only host `api.frankfurter.dev`, one rates path, GET (anything else refused before a request), ECB provider only, rate stored with publication date and fetch time, failure keeps the last rate, no call occurs during proposal generation (FR-034, FR-036) (done: one real read-only GET recorded the answer shape (list of {date, base, quote, rate}, 30 quotes, newest date was the previous Friday on a Monday); the fixture `packages/testing/fixtures/fx/ecb_rates.v1.json` uses invented round numbers; 32 tests in `test_fx_rates.py`; `eur_per_unit` widened to 12 decimals because a currency near 17,000 per euro lost accuracy at 8)
- [X] T037 [P] [US4] Test allocation with non-EUR suppliers in `services/procurement-service/tests/test_non_eur_supplier.py`: fresh rate converts; no rate, unsupported currency, or a rate older than 7 days excludes the supplier and creates a review item (FR-035, SC-012) (done: 15 tests in `test_non_eur_supplier.py`)
- [X] T038 [US4] Implement the rate job in `services/procurement-service/src/fx/rates.py` (HTTP GET with the allowlist; request rates for EUR as base from the ECB provider; store the inverse as EUR per unit as an exact decimal) and run it inside the existing one-pass worker in `src/worker.py` (already a scale-to-zero job on a short cron): fetch only when the newest stored rate is more than 20 hours old, so it runs about once a day and adds no job or always-on service; the same pass purges expired `fx_rates` and `terms_idempotency` rows (done: `fx/rates.py` (allowlisted GET, parser, store, refresh, purge) run from `worker.py` with `MMI_FX_DISABLED=1` to skip it; a confirmed-unchanged answer moves `fetched_at` so a weekend does not re-trigger the call, and a failure is audited and backs off for an hour; 4 worker tests)
- [X] T039 [US4] Implement conversion and exclusion in `services/procurement-service/src/proposals/inputs.py` using stored rates only, raising a review item with `fx_rate_missing` or `fx_rate_stale` (done in `proposals/inputs.py`: cost currency was never checked before, so a foreign cost was compared as euros; now converted or excluded with a review item, the rate is on the line's explanation, and the original cost, rate and day are in the inputs hash)
- [X] T040 [US4] Show the rate used and its date wherever an EUR equivalent appears, and list excluded suppliers, in `apps/web/src/features/suppliers/SuppliersScreen.tsx` and `LinksPanel.tsx` (done: the links table shows a foreign cost in its own currency with the euro equivalent, rate and day or why there is none, the review list explains the two new kinds with the currency, the proposal line names the rate; 7 unit tests)
- [X] T041 [US4] Record the new outbound dependency in an architecture decision `docs/adr/` (next free number): host, path, method, no credentials, no data sent, daily cadence, fallback, cost impact, and the "as is" data disclaimer (constitution: exceptions need a documented decision and cost review); also check `infra/bicep/modules/serviceJobs.bicep` and `containerAppJob.bicep` for outbound restrictions on the procurement worker and allow only `api.frankfurter.dev` if any exist (no new job is added) (done: `docs/adr/021-exchange-rates.md` and its index row; the infrastructure has no network-level egress rule and none can be added within the budget (Azure Firewall), so no Bicep change was needed; the application allowlist is the control, as for the cost writer)

## Phase 8: User Story 6 - Security and traceability (P2)

**Goal**: every change and every refusal is audited. **Independent test**: abuse cases refused and recorded.

- [X] T042 [P] [US6] Test: each refusal class (403, 412, 422, 428) leaves a `terms.refused`, `supplier.refused` or `link.refused` audit entry with no request body, in `services/procurement-service/tests/test_terms_refusal_audit.py`
- [X] T043 [P] [US6] Test: abuse inputs (oversized payload, malformed number, out-of-range value, another supplier's link, replayed request) refused with Spanish messages, in `services/procurement-service/tests/test_terms_abuse.py`
- [X] T044 [P] [US6] Test: a sensitive operation (release or override of an ERP cost) is refused with a stale second factor and accepted after re-confirmation (FR-027), in `services/api-bff/tests/test_sensitive_fresh_mfa.py` — done; found and closed a gap: the BFF cost override now also requires a fresh second factor
- [X] T045 [US6] Call `record_refusal` on every refusal path in `services/procurement-service/src/api/terms.py` and `src/api/suppliers.py` (depends on T009) — done as `AuditedRoute` in `src/api/refusals.py` (one route class, applied to the supplier, product-supplier and link families)
- [X] T046 [P] [US6] Test that free-text note content, tax ids and bank details are never stored or returned by supplier endpoints, in `services/procurement-service/tests/test_supplier_privacy.py` — done; sensitive fields are refused with 422 (strict models), no column can hold them, only `has_note` exists

## Phase 9: Polish and delivery

- [X] T047 [P] Playwright check of no untranslated or hard-coded text on supplier screens and Spanish number, date and EUR formats (SC-008), in `apps/web/tests/e2e/suppliers-terms-journey.spec.ts` — done: one more journey test, no raw keys or English, `2,10 €`, dd/mm/yyyy
- [X] T048 [P] Performance test: terms save and read under 300 ms p95 with 50 versions (SC-011), under `services/procurement-service/tests/perf` — done: `tests/perf/test_terms_latency.py`, 50 versions, p95 under 300 ms
- [X] T049 Run the full quickstart (steps 1 to 5), ruff, mypy and the web lint and unit suites; fix failures — done: quickstart 1-5, ruff, eslint, tsc, web 495 unit tests, contracts/infra/BFF/procurement/connector/writer suites, and migrations on real PostgreSQL (9 pass, 0012 included); mypy is not a CI gate and has long-standing errors
- [X] T050 Capture Spanish UI screenshots for the PR — done: `SCREENSHOT_DIR=<dir>` makes the Spanish-format journey test save a screenshot; not committed
- [ ] T051 Update the `research.md` audit table with final statuses, then open one PR from the PR template (data, security, cost including the daily rate job, contract impact), linking MMI-6 and Confluence page 3080407; no merge to main, no deploy

## Dependencies and order

- Phase 1 -> Phase 2 -> stories. T021 needs T005 and T008; T045 needs T009; T028 needs T006; T038 and T039 need T008, and T038 also needs the first step of T036 (the recorded response shape and fixture); T041 can be written alongside T038.
- Stories are independent after Phase 2. Suggested order: US1 -> US3 -> US2 -> US5 -> US4 -> US6.
- Within a story: tests first (must fail), then implementation.
- Parallel: T003/T004; T006, T007 and T009 alongside T005 and T008; all `[P]` tests inside a phase.

## Requirement coverage map

| Requirement | Tasks |
|---|---|
| FR-001, FR-002 | T002, T010, T011 |
| FR-003, FR-006 | T013, T017, T018 |
| FR-004 | T039, T040, T046 |
| FR-005, FR-037 | T014, T016 |
| FR-007, 008, 009, 013, 015, 024, 031 | baseline-only: T002, T010 |
| FR-010 | T023 |
| FR-011, FR-012 | T020, T024 |
| FR-014 | T005, T019, T021, T022 |
| FR-016 | T032, T034 |
| FR-017, FR-018 | T035 |
| FR-019 | T031, T033 |
| FR-020, FR-021 | T006, T025, T026, T028, T029 |
| FR-022 | T030 |
| FR-023, FR-025 | T027 |
| FR-026, FR-028 | T009, T042, T043, T045 |
| FR-027 | T012, T015, T044 |
| FR-029 | T046 |
| FR-030 | T007, T047 |
| FR-032 | T004, T048, T051 |
| FR-033 | T003, T004 |
| FR-034, FR-035, FR-036 | T036 to T041 |
| SC-001 | T010, T011 |
| SC-002 | T017 (proxy) |
| SC-003, SC-004 | T024 |
| SC-005 | T026 |
| SC-006, SC-009 | T027 |
| SC-007 | T042, T043, T044 |
| SC-008 | T047 |
| SC-010 | T038, T041, T051 |
| SC-011 | T048 |
| SC-012 | T037, T039 |

## MVP

Phases 1 and 2 plus US1 and US3 (audit, then idempotent, conflict-safe, effective-dated saves): this closes the main verified code gap and two acceptance criteria. US5 then closes "optimizer consumes local terms".

## Phase 10: Convergence

- [X] T052 Regenerate the TypeScript types in `apps/web/src/api/generated` with `packages/contracts/tools/codegen.py` so `explanation.terms.expected_delivery_date` appears there, and run `tsc` and the web unit tests per FR-012 and constitution rule 9 contract-first (partial: the JSON Schema and Python model have the field, the generated TypeScript does not) — done for `proposal_line.v1.schema.d.ts` (the only changed schema)
- [X] T053 [P] Add an explicit test in `services/procurement-service/tests/test_money_and_time_storage.py` that no money column in the supplier, terms, link and cost tables is a float type and that timestamps are timezone-aware and keep the original text where supplied, per FR-031 (partial: only indirect coverage, noted in research.md) — done

## Phase 11: Review fixes (spec update 2026-11-09: FR-038 to FR-041, SC-013)

Tests first, then the fixes. Findings come from the review of the delivered commit; each task names its requirement.

- [X] T054 [P] [US6] Test that refusals from callers with no valid sign-in are not stored one by one, and that 1,000 identical refusals (same caller, target, reason) in one minute add one audit entry whose next entry carries the repeat count, while a different caller, target or reason is still recorded, in `services/procurement-service/tests/test_refusal_volume.py` (FR-038, SC-013) — done: `test_refusal_volume.py` (5 tests)
- [X] T055 [P] [US6] Test that a burst of refused requests does not delay other users: terms save p95 stays under 300 ms while 200 refusals run at the same time, in `services/procurement-service/tests/perf/test_refusal_burst.py` (FR-039, SC-013) — done: `perf/test_refusal_burst.py`
- [X] T056 [P] [US6] Test that a body over 256 KB is refused with 413 `payload_too_large` under `text/plain`, a missing content type and a chunked upload without a length, and is recorded as a refusal, in `services/procurement-service/tests/test_terms_abuse.py` (FR-040) — done: 3 content-type cases in `test_terms_abuse.py`
- [X] T057 [P] [US4] Test that the rate-feed read stops at the size limit (a fake endless body is never fully read), stores nothing and audits `fx.refresh_failed`, in `services/procurement-service/tests/test_fx_rates.py` (FR-041) — done: `test_fx_rates.py`
- [X] T058 [US6] Collapse repeated refusals in `services/procurement-service/src/api/refusals.py`: skip storing 401 (count only), store one entry per (actor, target, code) per minute and carry the number of skipped repeats in the next stored entry's `after`; keep the counter per process and mark it with a `shortcut:` comment (limit: per replica, upgrade if the service scales out) (FR-038) — done: per-app table in `app.state`, 60 s window, `repeats` carried on the next stored entry; 413 without a known caller is still stored (once per minute) because the size check runs before sign-in
- [X] T059 [US6] Run the refusal write off the event loop with `run_in_threadpool` in `services/procurement-service/src/api/refusals.py`, keeping "recording failures never change the answer" (FR-039) — done: `run_in_threadpool`
- [X] T060 [US6] Apply the size guard to every change request whatever the content type, and stop reading the body at the limit, in `services/procurement-service/src/api/refusals.py` (FR-040, depends on T058 and T059 touching the same file) — done: declared length is trusted up to the limit, a chunked body is read only to the limit
- [X] T061 [US4] Read the rate answer with `client.stream` and stop at `MAX_BODY_BYTES` in `services/procurement-service/src/fx/rates.py` (FR-041) — done: `client.stream`, stops at `MAX_BODY_BYTES`
- [X] T062 [P] Move the fixtures shared by `test_terms_refusal_audit.py`, `test_terms_abuse.py`, `test_supplier_privacy.py` and `tests/perf/test_terms_latency.py` into `services/procurement-service/tests/refusal_support.py`, and remove the `# ruff: noqa: F811` lines (review finding 5) — done, with one deviation: the fixtures moved to `tests/refusal_support.py` (no test file imports another test file), but the file-level `# ruff: noqa: F811` stays because importing a fixture and taking it as a parameter always trips F811 and a per-line noqa does not cover the parameter
- [X] T063 Run the procurement, BFF, contracts and infra suites, ruff and the PostgreSQL migration test; update research.md audit row 16 and the PR text in `pr-body.md` for the new behaviour (depends on T054 to T062) — done: procurement 812, BFF 177, contracts 208, infra 59, PostgreSQL migrations 9, ruff clean

**Order**: T054 to T057 and T062 first (parallel); then T058, T059, T060 (same file, in order); T061 alongside; T063 last.

## Phase 12: Convergence

- [X] T064 Make the skipped refusals countable in `services/procurement-service/src/api/refusals.py`: log one summary line (key and number skipped) when a window closes without a later identical refusal, and increment a per-process counter for 401s so "counted but not stored" in FR-038 is observable; fix the stale `_repeats` reference in the `_skip` docstring; add a test in `tests/test_refusal_volume.py` per FR-038 (partial: skipped repeats are lost if no later identical refusal arrives, and skipped 401s are only logged individually) — done: a sweep at most once a minute logs repeats of closed windows, `app.state.refusal_unauthenticated` counts skipped 401s, docstring fixed

## Phase 13: Review hardening, second pass (spec update 2026-11-09: FR-042, FR-043, SC-014; plan decisions D7 to D10)

Tests first, then the fixes.

- [X] T065 [P] [US6] Test that 50 identical refused requests sent from threads at the same instant leave exactly one audit entry and that the next stored entry reports 49 skipped repeats, in `services/procurement-service/tests/test_refusal_volume.py` (FR-042, SC-014) — done: `test_refusal_volume.py` (50 threads; it passes on the old code too because the race window is nanoseconds, so it guards the regression rather than reproducing it)
- [X] T066 [P] [US4] Test that a rates source whose storage step raises (for example `store_rates` patched to raise) still lets `run_once` relay outbox events in the same pass and report `fx: "error"`, and that a persistent error does not stop the relay on the next pass, in `services/procurement-service/tests/test_worker_fx.py` (FR-043, SC-014) — done: failed before the fix, passes after; the audited failure starts the one-hour backoff
- [X] T067 [US6] Move the refusal bookkeeping (`_skip`, the repeat table and the 401 counter) into the async `_record` so it runs on the event loop thread, leaving only the database write in the worker thread, and remove the duplicated comment, in `services/procurement-service/src/api/refusals.py` (FR-042, research D7) — done: `_skip` and the counters run on the event loop in `_record`; `_write` is all the thread does
- [X] T068 [US4] In `services/procurement-service/src/worker.py` run the rate refresh and housekeeping after `relay_once`, inside `try/except Exception` that logs, records `fx.refresh_failed` best-effort in its own transaction and returns `fx: "error"`; make the `refresh_if_due` docstring in `services/procurement-service/src/fx/rates.py` say exactly which failures it absorbs (FR-043, research D10) — done: the rate step runs after the relay inside try/except, audits `fx_storage_error` in its own transaction, reports `fx: "error"`; docstring corrected
- [X] T069 Run the procurement, BFF, contracts and infra suites, ruff and the PostgreSQL migration test; update `research.md` audit rows, `quickstart.md` step 6 results and `pr-body.md` (depends on T065 to T068) — done: procurement 817, BFF 177, contracts 208, infra 59, PostgreSQL migrations 9, ruff clean

**Order**: T065 and T066 first (parallel, they must fail); then T067 and T068 (different files, parallel); T069 last.

## Phase 14: Convergence

- [X] T070 Run `purge` in its own transaction and its own `try/except` after the rate refresh commits in `services/procurement-service/src/worker.py`, so a failing cleanup cannot roll back freshly stored rates; add a test in `tests/test_worker_fx.py` where `purge` raises and the rates are still stored and the relay still ran per FR-043 (partial: refresh and purge share one transaction, so a persistent purge error rolls the rates back every pass and they go stale after 7 days) — done: purge in its own transaction and try/except; test fails before, passes after
- [X] T071 [P] Add a test in `services/procurement-service/tests/test_refusal_volume.py` that patches `api.refusals._skip` to record `threading.current_thread()` and asserts it ran on the main thread, not a pool thread, per FR-042 (partial: the 50-thread test passes on the old code too, so nothing fails if the bookkeeping moves back into the thread) — done: passes on the current code and fails if `_skip` moves back into the thread
- [X] T072 In `services/procurement-service/src/api/refusals.py` forget the key from the recent-refusals table when the database write fails, so a failed write does not silence identical refusals for the next minute, with a test that makes the write raise and then expects the next identical refusal to be stored, per FR-038 and FR-042 (partial: `_skip` marks the key as stored before the write) — done: the key is forgotten when the write raises; test failed before
- [X] T073 [P] In `services/procurement-service/src/api/refusals.py` include the count of skipped sign-in failures in the once-a-minute sweep summary log line (and reset it), with a test using `caplog`, per FR-038 (partial: `refusal_unauthenticated` is counted but never shown anywhere outside tests) — done: `_sweep` logs the sign-in failures not stored once a minute (also from a pure 401 flood); test failed before

**Order**: T071 and T073 are parallel tests-first work; T072 and T073 touch the same file (`refusals.py`), so run them in order; T070 is independent (`worker.py`).

## Phase 15: Convergence

- [X] T074 [P] Add a failing test in `services/procurement-service/tests/test_preferred_fallback_reason.py` (or a new `test_reason_lead_time_risk.py`) using the allocation case from `tests/test_allocation.py::test_the_optimum_may_cost_a_little_more_cash_to_avoid_a_slow_supplier`: when the chosen supplier's cash total for the line is higher than the baseline supplier's, the line's reason must not be `lower_total_with_supplier_terms`, per Constitution III explainable purchasing (contradicts: the explanation says "lower total" for a plan that costs more cash) — done: `test_reason_lead_time_risk.py` (2 tests); the first failed before the fix
- [X] T075 In `services/procurement-service/src/proposals/generate.py` `_reason`, return a new reason `lower_lead_time_risk` when the optimiser's supplier differs from the baseline's and the baseline offer carries more `risk_ticks` than the chosen one while the chosen cash cost is not lower; keep `lower_total_with_supplier_terms` for the cases where the cash total really is lower; add the Spanish text for `lower_lead_time_risk` in `apps/web/src/i18n/es-ES.json` and a unit test next to `ProposalsScreen.test.tsx`; if the reason list is enumerated in `packages/contracts`, update the schema first per contract-first (contradicts, depends on T074) — done: `_reason` gets `plan_costs_more` and returns `lower_lead_time_risk` only when the whole plan costs more cash and the baseline supplier carries more risk; Spanish text and a web unit test added; the reason is not an enum in `packages/contracts`, so no schema change
- [X] T076 Run the procurement, web unit and contracts suites, ruff, tsc and the Playwright proposal journeys; update `research.md` decision D4 neighbours with the new reason and `pr-body.md` (depends on T075) — done: procurement 824, web 496 unit and 12 e2e, BFF 177, contracts 208, infra 59, ruff, eslint and tsc clean

**Order**: T074 (test, must fail), then T075, then T076.

## Phase 16: Convergence

Source: Agent 00's integration feedback on PR #17 (comment of 2026-11-09, feature 005 gates).

- [X] T077 Renumber the exchange-rate ADR from 021 to 024: rename `docs/adr/021-exchange-rates.md` to `docs/adr/024-exchange-rates.md`, change its title to `ADR-024`, update the row and link in `docs/adr/README.md`, and replace `ADR-021` with `ADR-024` in `specs/007-supplier-commercial-management/research.md` (audit row 19), `plan.md`, `spec.md`, `pr-body.md` and any code comment that names it; leave the `ADR-021` of feature 005 (`docs/architecture/adr/021-contract-versioning.md`) untouched; confirm with Agent 00 which folder holds ADRs (he will move his into `docs/adr/`), then run `uv run python -m pytest infra` per Agent 00 review item 1 (contradicts: two different ADRs carry the number 021 on main) — done: `docs/adr/024-exchange-rates.md` (ADR-024), README row and the references in research.md and pr-body.md updated; the ADR-021 of feature 005 is untouched; infra tests pass
- [X] T078 Resolve the append-at-the-end conflict with PR #18 in `packages/contracts/errors/error_codes.json` and `specs/002-mmi-operational-console/contracts/error-keys.md` (a trial merge on 2026-11-09 conflicts in exactly these two files; PR #19 merges cleanly): whichever of #17 and #18 merges second merges `main`, keeps both sets of appended codes and table rows, re-sorts nothing, and runs `infra/tests/test_error_codes.py`, `infra/tests/test_error_keys_localised.py` and `apps/web` unit tests; if #17 goes first, post the merge order on PR #18 per Agent 00 review item 2 (partial: the conflict is known and not yet resolved, because it depends on merge order) — done: PR #18 merged first; `main` merged into this branch, both sets of codes and rows kept (135 codes), error-code guard tests pass

**Order**: T077 now (independent, small); T078 only when the first of #17 and #18 is merged.

## Phase 17: Convergence

Source: Agent 00's comments on PRs #18 and #19 that name this PR, and the gate run of 2026-11-09 (contracts, isolation, security and cost all pass on this branch).

- [X] T079 Record the merge order and the known conflicts in the description of PR #17, as PR #18 did: the conflict with #18 in `packages/contracts/errors/error_codes.json` and `specs/002-mmi-operational-console/contracts/error-keys.md`, the clean trial merge with #19 today, the gate results (contracts, isolation, security 8 commands, cost 1 command: pass), and the ADR renumbering of T077; update `specs/007-supplier-commercial-management/pr-body.md` first and then the PR body with `gh pr edit 17`, per Agent 00's request that the second PR is rebased (partial: the PR body does not mention merge order or the gate results) — done: `pr-body.md` has the merge order, the conflicts, the ADR number and the gate results, and the PR description was updated with `gh pr edit`
- [X] T080 When the first of #17, #18 and #19 is merged to `main`, merge `main` into this branch and re-check the shared files that Agent 00 flagged on #19, `apps/web/src/api/client.ts` and `apps/web/src/i18n/es-ES.json`, in addition to the two error files of T078; resolve by keeping both sides, then run the web unit tests, `tsc`, `infra/tests/test_error_codes.py` and `python -m gates run --gate contracts --gate isolation` (partial: a trial merge of #19 is clean today, but this PR changes both files heavily and that combination was not tested by Agent 00) — done in the same merge: `client.ts` and `es-ES.json` merged without conflict; web 514 unit tests, tsc, contracts and isolation gates pass

**Order**: T079 now (documentation only); T080 only after another PR merges.
