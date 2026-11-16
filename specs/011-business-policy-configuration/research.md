# Research: Business Policy Configuration (Agent 06)

First-pass audit of this branch (code read, no test run) plus the design decisions that close the gaps. Statuses: complete / partial / broken / missing / unverified. Every "unverified" is a task to run or write a test, not a finding of defect.

## A. Audit evidence

| # | Capability | Status | Evidence |
|---|------------|--------|----------|
| A1 | Policy sets by scope global/segment/product, product over segment over global per field, effective dates, revisions | complete in code, effect on proposals unverified | `procurement-service/src/policies/service.py:6,22,121-123`, `migrations/versions/0006_policies.py` |
| A2 | Optimistic concurrency on policy sets | complete | `service.py:87-103` (`expected_revision`, `PolicyConflict`), `api/policies.py:130-141` (If-Match, 428 without it, 412 on stale) |
| A3 | Past effective date refused | complete (stricter than spec) | `service.py:94-95` refuses any past start; spec FR-015 allowed a confirmed retroactive date |
| A4 | Overlap of effective periods | unverified | unique constraint only on `(scope, key, valid_from, revision)` (`db/tables.py:358`); no explicit overlap check seen |
| A5 | Budget caps | partial | `service.py:160-186`; `PUT /budget-caps` (`api/policies.py:160`) has no If-Match or revision, so concurrent saves overwrite silently |
| A6 | Preview without saving | complete | `api/policies.py:143-158`, `policies/preview.py`, `tests/test_policy_preview.py` |
| A7 | Audit of policy, budget, exclusion, censoring changes | complete in services | `service.py:104,179`, `inventory-service/src/projections/rules.py:48,59,91` |
| A8 | Refusals recorded | complete for role and CSRF refusals | `api-bff/src/routes/rbac.py:50-65,89-95` (hash-chained audit) |
| A9 | Fresh MFA | missing on policies | `rbac.py:102-106` `require_fresh_mfa` exists and is used by costs and imports, not by `routes/policies.py` |
| A10 | Product scope by SKU | broken against project rule 5 | `service.py:61-62` key is the variant id; preview rows show `variant_id` (`PurchasingSection.tsx:191`) |
| A11 | Criticality, exclusions, censoring rules | partial | BFF routes `routes/policies.py:124-146`; inventory routes `api/demand_rules.py:56-92`; exclusions and rules take no revision, so no stale-save protection |
| A12 | Forecast parameters: approved list, ranges, effective dating, revision | complete in code | `forecast-service/src/parameters.py` (`APPROVED`, 5 keys), `api.py:91-116` |
| A13 | Versions recorded on runs | partial | proposals and scenarios record policy and terms versions (`proposals/inputs.py:136,199`, `scenarios/store.py:65`); forecast runs record `parameter_version_ids` and dataset (`runs/runner.py:143-145`) but not exclusion or censoring-rule versions |
| A14 | Defaults shown as defaults | unverified | no "source" field in the policy JSON (`api/policies.py` `pol_json`) |
| A15 | Admin audit view of rule changes | missing | no BFF route or screen reads the policy audit; only per-policy revision history exists (`PurchasingSection.tsx:197`) |
| A16 | Orphaned product policy flagged | unverified | no check seen |
| A17 | Browser tests | partial | `apps/web/tests/e2e/policies.spec.ts` mocks every endpoint with `page.route`, so it proves screen behaviour, not persistence or effect |
| A18 | Service tests | complete for validation, dates, preview | `procurement-service/tests/test_policies.py`, `test_policy_effective_dates.py`, `test_policy_preview.py`, `test_safety_stock_override.py`; `api-bff/tests/test_policies_rbac.py` |

## B. Decisions

**D1. Retroactive dates.** Keep the existing refusal of any past effective date and amend spec FR-015 and the matching edge case. Rationale: stricter, already tested, keeps earlier runs reproducible. Alternative: admin-confirmed retroactive dates (rejected: no owner demand, more surface).

**D2. Concurrency for budget caps and demand rules.** Add `If-Match` revision to budget cap saves and to exclusion and censoring-rule saves, reusing the policy-set pattern (428 when missing, 412 with `current_version`). Alternative: last write wins (rejected by FR-010).

**D3. SKU instead of variant id.** The BFF resolves SKU to variant id through the synced catalogue before forwarding; ambiguous or unknown SKUs are refused with a stable key; responses carry `sku` and the web app shows only SKU. Services keep the variant id internally. Alternative: change the services' keys (rejected: breaks stored data and contract).

**D4. Fresh MFA scope.** Apply `require_fresh_mfa` (5-minute window, like costs) to budget-cap saves and global-scope policy saves in the BFF; segment and product saves need the normal session. Alternative: MFA on every write (rejected: friction for routine edits).

**D5. Versions on forecast runs.** The inventory series export returns the revision of the exclusion set and of each censoring rule; the run stores them in a new nullable JSON column next to `parameter_version_ids`. Alternative: rely on the input hash only (rejected: not readable in the run list).

**D6. Orphaned SKUs.** A read-time check flags product-scope policies whose variant no longer exists; calculations already ignore unknown variants, so the flag is informational and listed in the existing review list. Nothing is deleted.

**D7. Reasons and free text.** Exclusion reasons use a pick list plus a short limited detail, shown to admins only and not written into the audit payload (same rule as feature 008). First check how `projections/rules.py:48` stores `reason`; if it writes free text to the audit, change it to the pick-list code.

**D8. Effective-policy view and defaults.** A read endpoint per product returns each rule with value, source (default, global, segment, product), revision and period, from the existing resolver extended to return provenance. Defaults come from existing constants and are marked as defaults.

**D9. Audit view.** A read-only, admin-only BFF route lists audit records for policy, budget cap, exclusion, censoring rule and parameter actions, filterable by scope and date and paged. No new table; it reads through each owning service.

**D10. API-backed browser tests.** Add `policies-live.spec.ts` against the real BFF and services with the synthetic dataset and no `page.route` on policy endpoints: save, effect on the next proposal, conflict, viewer refusal, MFA refusal. Keep the mocked spec for pure screen states.

**D11. Preview cost.** No algorithm change; add a timing test on the full synthetic catalogue (SC-008) and return progress if it exceeds 5 s.

## C. Open items, resolved in T001/T002 (2026-11-10)

- **Baseline (T001)**: 124 policy-related tests pass on this branch (procurement 67, inventory 14, forecast 29, gateway 14). Playwright not run in this environment (no web dependencies installed in the worktree).
- **A4 overlap (T002)**: policy sets are append-only and resolve by latest `valid_from` then revision, so same-date saves are deterministic. The real hazard is a save dated *earlier* than an already-scheduled future revision: when the future one takes effect it silently overrides the newer edit. Decision: refuse a save whose `valid_from` is earlier than the latest scheduled `valid_from` for that scope and key (`policy_overlap`); same rule for budget caps.
- **A16 orphans**: no review-list integration point exists for policies; the flag is shown in the policy console list only (`orphaned`). Review-list integration is out of scope.
- **D7 reasons (defect)**: `add_exclusion` writes the free-text `reason` into the audit payload (`projections/rules.py:48`), contrary to project rule 7. Fix: pick-list `reason_code` goes to the audit; the short detail is stored for admins only.
