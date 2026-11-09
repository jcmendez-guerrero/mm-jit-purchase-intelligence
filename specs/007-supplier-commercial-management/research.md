# Research and Audit: Supplier Commercial Management

Audit of the worktree's base (latest main at `9d11abb`). Statuses: complete / partial / broken / missing / unverified. Evidence is file and line from code reading (T010, 2026-11-09). "verified T002" means the named tests were run and passed (section C); other "complete" rows are read from code only.

## A. Audit table (FR-001, FR-002)

| # | Capability | Status | Evidence | Closes via |
|---|---|---|---|---|
| 1 | Supplier master CRUD, deactivate/reactivate, duplicate warning, merge | complete (verified T002) | `services/procurement-service/src/api/suppliers.py:166-207` (POST/PATCH/deactivate/reactivate/merge); `src/suppliers/service.py` `create_supplier:89`, `update_supplier:109`, `deactivate_supplier:152`, `reactivate_supplier:168`, `dedupe.py`; tests `test_suppliers_api.py`, `test_suppliers_service.py` (14), `test_supplier_merge.py` | FR-003, FR-006 -> T013 (round-trip and duplicate-name test) |
| 2 | Effective-dated append-only terms | complete (verified T002) | `services/procurement-service/src/terms/service.py` `save_terms:210`, `in_force:183`, `current_terms:196`; table `supplier_terms` `src/db/tables.py:54`; `test_terms_versions.py` (9) | FR-007, FR-008 baseline-only (T002) |
| 3 | Validation (money, weekdays, cutoff, discount tiers, threshold vs minimum) | complete (verified T002) | `services/procurement-service/src/terms/service.py` `validate:117`, `check_discounts:102`; `test_terms_validation.py` (10) | FR-009 baseline-only (T002) |
| 4 | Validity window overlap rules | complete (verified T002) | `services/procurement-service/src/terms/service.py` `check_window:169`; `test_terms_versions.py` | FR-013 baseline-only (T002) |
| 5 | Revision conflict (If-Match, 412, 428) | complete (verified T002) | `services/procurement-service/src/api/terms.py` `_precondition:112`, `put_terms:149`; `src/terms/service.py` `TermsConflict:41`; `test_terms_concurrency.py` (4) | FR-012 -> T020, T024 |
| 6 | Idempotent repeated save | complete (T019-T022) | No `Idempotency-Key` in terms or overrides; idempotency exists only in `costs/writes.py` and `scenarios/store.py` | FR-014 -> T019, T021, T022 |
| 7 | Product-level overrides with inheritance | complete (verified T002) | table `product_supplier_terms` `src/db/tables.py:315` (NULL inherits); `src/terms/overrides.py` `save_override:72`, `validate_override:35`; `src/terms/resolve.py` `resolve_effective:41`; `test_terms_precedence.py` (11); ADR-019 | FR-015 baseline-only (T002) |
| 8 | Cost provenance and manual-vs-ERP difference | complete (T028-T035) | `supplier_costs.source` (`siweb_product_supplier/csv_price_list/manual`), `jump_flag`; difference display in UI not verified (`LinksPanel.tsx`, `OverrideEditor.tsx`) | FR-016 -> T032, T034 |
| 9 | Bulk assignment by filter / SKU list with preview | complete (verified T002) | `services/procurement-service/src/suppliers/bulk.py`, routes `src/api/suppliers.py:241-256`; `test_bulk_assign.py` (11) | FR-018 -> T035 (UI check) |
| 10 | SKU-only user surface, ids resolved server-side | complete (T035, T047) | `test_refuse_local_ids.py`, `test_abuse_ids.py` exist; UI leak check absent | FR-017 -> T035 |
| 11 | Proposals consume terms in force; versions recorded | complete (T038-T041) | Versions recorded: `services/procurement-service/src/proposals/generate.py` `terms_versions:79`, `_terms_explanation:97`; tests `test_allocation_terms.py` (13), `test_input_versions.py` (5) pass. But `src/proposals/model.py:85` `SupplierTermsIn` carries only minimums, free-delivery threshold, delivery charge, discounts, preferred, disabled and version: **order days, order cutoff, delivery weekdays and payment terms never reach the optimizer** | FR-020 -> T025, T026, T028 (extended) |
| 12 | Delivery date from schedule and cutoff shown on proposal | complete (T038-T041) | A per-supplier `expected_delivery_date` exists (`services/procurement-service/src/db/tables.py:214`, `src/proposals/generate.py:60`, shown in `src/proposals/export.py:57`), but no code derives it from order days, cutoff or delivery weekdays (no reference in `src/allocation` or `src/proposals`); lead time is used only for stock targets (`allocation/common.py:131`) | FR-020 -> T025, T028, T029 |
| 13 | Preferred/rank honoured with infeasibility reason | complete: preferred wins ties only (FR-019 reworded) | `services/procurement-service/src/allocation/common.py:138-139`: preferred only **wins a tie**; fallback reasons exist (`src/proposals/generate.py` `_reason:105`, rejected suppliers with reasons `:157`). FR-019 was reworded on 2026-11-09 to match this tie-break; only the reason text needs proving | FR-019 -> T031, T033 |
| 14 | Shortfalls vs minimums not silently dropped | complete (verified T002) | `services/procurement-service/src/allocation/common.py:159` shortfall groups; `tests/test_scenarios_infeasible.py` (3), `tests/test_allocation.py:63` (unreachable minimum flagged, not hidden) | FR-022 -> T030 |
| 15 | Audit of successful changes (tamper-evident) | complete (verified T002) | `services/procurement-service/src/audit/chain.py`; `audit(...)` at `src/terms/service.py:234` and `src/terms/overrides.py:92`; `tests/test_terms_versions.py:80` `test_every_save_is_audited_in_the_hash_chain` | FR-026 baseline-only |
| 16 | Audit of **refused** attempts (role, stale MFA, abuse) | complete (T042, T043, T045; volume bounded by T058 and race-free by T067, FR-038, FR-042) | No audit call on refusal paths in `api/terms.py`, `api/suppliers.py` | FR-028 -> T042, T043, T045 |
| 17 | Server-side role enforcement | complete (T012, T015) | `services/procurement-service/src/api/terms.py:150,187` `Depends(require("buyer"))`; `src/api/suppliers.py:129` buyer/admin check; BFF `services/api-bff/src/routes/rbac.py` | FR-027 -> T012 (explicit viewer-refused test) |
| 18 | Sensitive-op fresh MFA | complete (T044; the BFF override gap closed) | `services/api-bff/src/routes/costs.py:58` `require_fresh_mfa()` | FR-027 -> T044 |
| 19 | Non-EUR currency display/compare | complete (T036-T041, ADR-021) | `suppliers.currency` kept; no rate rule found in `src` | FR-034..036 -> T036..T041 (decision D3) |
| 20 | ERP facts untouched by supplier maintenance | complete (verified T002) | `services/procurement-service/tests/test_terms_no_erp.py` (1), `tests/test_refuse_local_ids.py` (7), `tests/test_abuse_ids.py` (2) | FR-023, FR-024, FR-025 -> T027 |
| 21 | Spanish-only texts via catalogue | complete (T007, T047) | `src/locale/es-ES.json`, web catalogue; new strings pending | FR-030 -> T007, T047 |
| 22 | Playwright journeys for suppliers | complete (T017, T024, T035, T047) | `apps/web/tests/e2e/suppliers.spec.ts`, `suppliers-manage.spec.ts`; no terms history/conflict/future-date journey | SC-002..004 -> T017, T024, T035, T047 |
| 23 | Deactivation: affected lines listed first; proposal with a deactivated supplier not approvable | complete (T016, T018, approval flow blocks deactivated suppliers) | Preview, confirmation and review item exist and pass: `services/procurement-service/src/suppliers/service.py` `deactivation_preview:135`, `flag_open_proposals:143`, `deactivate_supplier:152` (needs `confirm`); tests `test_suppliers_service.py:106,116,138`, `test_suppliers_api.py:89`. **Missing**: `src/approvals/workflow.py` `submit:42` and `decide:56` do not look at the suppliers of a proposal's lines | FR-037 -> T014 (approval block test), T016 |

## B. Decisions

**D1 Idempotency for term saves.** Decision: accept an optional `Idempotency-Key` header on `PUT /suppliers/{id}/terms` and `PUT /product-suppliers/{variant}/{supplier}/terms`; store key, request hash and resulting version in a small additive table; a repeat with the same key and body returns the original result, a repeat with a different body returns 422 `idempotency_key_reuse`. Rationale: matches the existing pattern in `scenarios/store.py`; If-Match alone already prevents duplicates after a successful save but not a retry whose response was lost (the retry then looks stale). Alternatives: rely on If-Match only (rejected: retry yields a false conflict); natural-key hash dedupe (rejected: legitimate identical resaves).

**D2 Refusal auditing.** Decision: record refusals (403, 412, 422 abuse classes, 428) in the existing audit chain as `terms.refused` / `supplier.refused` with actor, target, error code and no request body. Rationale: SC-007 needs recorded refusals; reuse `audit.chain.append`. Alternative: structured logs only (rejected: not tamper-evident, not reviewable in-app).

**D3 Currency (decided by the owner, 2026-11-08).** Decision: use Frankfurter (`https://api.frankfurter.dev`, v2) for EUR reference rates. The existing one-pass procurement worker (a scale-to-zero cron job) calls, at most once a day (only when the newest rate is over 20 hours old), the ECB provider endpoint (`/v2/providers/ecb/rates`, base EUR), stores each rate with publication date and fetch time in `fx_rates`, and allocation converts from stored rates only. A currency the ECB does not publish, a missing rate or a rate older than 7 days excludes the supplier from automatic allocation and raises a review item. Facts from the service's own pages: no API key, no numeric rate limit stated ("rate-limited to prevent abuse"), data provided as is, caching in your own database encouraged, blended rates are not official so the ECB provider is pinned, self-hosting available (not needed). Settled by T036 (2026-11-09, one public read-only request, nothing sent): the answer is a JSON list of `{date, base, quote, rate}` (30 quotes, rates as JSON numbers, parsed as exact decimals); on a Monday morning the newest date was the previous Friday, so weekends carry no new rates. Holiday behaviour is not yet observed (ADR-021 follow-up). The synthetic fixture copies the shape with invented round numbers. Rationale: no manual rate upkeep, no secrets, negligible cost, and it satisfies the constitution's allowlist rule with one host, one path and GET. Alternatives: manual per-supplier rate (more upkeep, error-prone); refuse non-EUR suppliers (blocks real suppliers); blended default feed (not an official rate); self-hosted instance (an always-on service, against the cost rule). Constitution impact: a new outbound integration needs the allowlist (T036, T038) and a documented decision with cost review (T041).

**D4 Delivery date.** Decision: derive the expected delivery date from the terms in force: next order day on or after the proposal date (respecting the cutoff), plus lead time, moved to the next delivery weekday when set. Implemented as a pure function with table-driven tests (no I/O). Alternative: leave to the UI (rejected: must be testable and reproducible).

**D5 Same-start tie.** Decision: keep current behaviour (latest saved version wins, ordered by `valid_from` then `id`) and surface the superseded row as such in history. No schema change.

**D6 Scope guard.** No change to forecasting, policies, ERP connector or cost writer. Contract changes (header, error codes) go through Agent 00 before merge.

**D7 Refusal volume (FR-038, FR-042).** Decision: keep the table of recent refusals in the process (one entry per caller, target, code and status for a 60 s window, a count of skipped repeats carried on the next stored entry, a summary log line when a window closes unused, a counter for 401s which are never stored). Mutate that table and the counters only on the event loop thread, in `_record`, before the database write is handed to a worker thread; the thread only writes. Rationale: the event loop is one thread, so no lock is needed and the check-then-store step cannot race; the review found the earlier version mutated the dictionary from the thread pool (duplicate rows, lost counts, "dictionary changed size" errors swallowed as a log line). Alternatives: a `threading.Lock` around the table (works, but a lock held in async code is easy to misuse); shared storage such as the database (needed only with several replicas, a documented limit, FR-042 assumption). Test: 50 identical refusals from threads give exactly one row and an accurate skipped count.

**D8 Refusal write off the loop (FR-039).** Decision unchanged from T059: the database write runs in `run_in_threadpool`; D7 only moves the bookkeeping before it. Rationale: the synchronous engine would otherwise block every request on the process.

**D9 Size limit (FR-040).** Decision as built (T060): a declared length over 256 KB is refused without reading; a body with no length is read only up to the limit and cached for the route. No design change.

**D10 Rate refresh isolation (FR-043).** Decision: in `worker.run_once`, run the rate refresh and housekeeping after the event relay and inside a `try/except Exception` that logs, audits `fx.refresh_failed` where the database allows it, and reports `fx: "error"` in the pass result; `refresh_if_due` keeps handling download and parse failures itself, and its docstring says so precisely. Rationale: the review showed `store_rates` and `purge` run outside `refresh_if_due`'s try, so a database error aborted the pass before `relay_once`, blocking events from every service. Alternatives: only reorder (leaves the pass crashing on a persistent error); only wrap (relay still waits behind the rate step on every pass). Both together keep relay first and the pass alive. Test: a rates source whose storage raises still leaves the relay executed. Scale note (recorded as a limit): with several replicas two workers could insert the same (currency, day); use insert-or-update then.

**D11 Supplier reason wording.** Decision: a line says `lower_total_with_supplier_terms` only when the plan as a whole is not dearer in cash than the baseline; when the optimiser pays a little more cash to avoid a supplier with more lead-time risk it says `lower_lead_time_risk`. Rationale: the solver minimises cash plus risk, so "lower total" would be false for those lines (Constitution III).

## C. Verification results (T002, 2026-11-09)

Command: see quickstart step 1. Result: **235 passed, 0 failed** (334 deselected), 10 s, SQLite fixtures. A first run failed one test only because `mmi-testing` (which provides `export_loader`) was not installed; after installing it the same test passes.

- **Verified by passing tests**: rows 1 to 5, 7, 9, 11, 14 (infeasible cases) and 20 (terms, supplier, bulk, allocation-terms, input-versions, no-ERP, local-id and abuse-id suites).
- **Not covered by this selection, still as audited**: rows 8, 10, 12, 13, 15 to 19, 21 to 23. Row 15 (audit of saves) is exercised inside the terms tests but has no dedicated assertion yet.
- **Not run**: web unit and Playwright suites, PostgreSQL integration (the fixtures use SQLite, so PostgreSQL behaviour of the new migration is untested until T008), and the whole service suite.
- Row statuses are unchanged: no row was reclassified as broken.

## D. Open verification items

- T003: confirm with Agent 00 that `Idempotency-Key`, the new error codes and the daily exchange-rate fetch are acceptable shared changes (a person must do this; not done).
- Confirm with Agent 00 whether `Idempotency-Key` is already a shared header convention.

## E. Findings from the line-level review (T010, 2026-11-09)

1. **Schedule fields never reach the optimizer (rows 11, 12).** Order days, order cutoff, delivery weekdays and payment terms are stored, validated and versioned, but `SupplierTermsIn` does not carry them. This is the part of "optimizer consumes local terms" that is not met today. Closing it is part of T028: carry the fields through `proposals/inputs.py` into `SupplierTermsIn`, then derive the delivery date from them.
2. **Preferred supplier is only a tie-breaker (row 13).** `allocation/common.py:139` lets a preferred supplier win a tie only. FR-019 says the preferred supplier is honoured unless a minimum, schedule or deactivation makes it infeasible. These differ, and ADR-019 or the 002 spec may have chosen the tie-break on purpose. **Decided 2026-11-09 by the owner: keep the tie-break and reword FR-019** (done in spec.md, along with User Story 4 scenario 4); no allocation change.
3. **Deactivation is mostly done (row 23).** Preview, confirmation, review items and tests exist; only the approval block (FR-037) is missing. T014 therefore tests just the approval block, and T016 implements just that.
4. **Role checks exist in code (row 17).** T012 stays as an explicit viewer-refused test, not a fix.

## F. Baseline-only requirements and their proving tests (T010)

| Requirement | Proving tests (all passed in T002) |
|---|---|
| FR-007 | `test_terms_versions.py`, `test_terms_api.py` |
| FR-008 | `test_terms_versions.py` (append-only, in force on a date) |
| FR-009 | `test_terms_validation.py` (10) |
| FR-013 | `test_terms_versions.py` (window overlap) |
| FR-015 | `test_terms_precedence.py` (11), `test_supplier_links.py` |
| FR-024 | `test_refuse_local_ids.py` (7) |
| FR-031 | not separately proven: money is `Decimal`/`MONEY` and timestamps are timezone-aware in `src/db/tables.py`; covered indirectly by `test_costs.py`. Add an explicit check in T048 if wanted. |
