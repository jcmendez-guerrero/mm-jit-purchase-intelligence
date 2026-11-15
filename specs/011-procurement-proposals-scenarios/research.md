# Research: Procurement Proposals & Scenarios (Agent 03)

## 1. Evidence inventory of current main

Status: complete / partial / missing / unverified. "Tests present" means the files exist; this audit did not execute them.

| Area | Status | Evidence | Note |
|---|---|---|---|
| Weekly proposal generation, versions recorded | complete | `services/procurement-service/src/proposals/generate.py`, `proposals/model.py:139` (inputs hash with rule versions), `tests/test_reproducibility.py` | 20-run repetition not asserted (G3) |
| Line explanation (cost, source, constraints, risk) | complete | `proposals/model.py`, `tests/test_reason_lead_time_risk.py`, `apps/web/src/features/proposals/ProposalLineExplanation.tsx` | |
| Buyer edit with version check | complete | `proposals/edit.py:57-66` (`version_conflict` on stale version), `tests/test_api_proposals.py` | Matches clarification: stale save rejected |
| Submit and approve, separation of duties, fresh MFA | complete | `approvals/workflow.py:21,53,70-86`, `tests/test_approval.py`, `tests/test_approval_eligibility.py` | |
| Allocation with minimums, packs, shipping, thresholds, budget | complete | `allocation/{common,cpsat,greedy,shortfall}.py`, `tests/test_allocation*.py` | budget is a soft cap: flagged over-budget, never cut (confirmed by running the allocator); excess display to verify (G3) |
| Discounts | partial | `terms/resolve.py:15,29,76` reads `discounts` from supplier terms | Per clarification, use as held; no new editing here |
| Scenarios: create, run, sensitivity, compare, infeasible | complete | `scenarios/engine.py`, `tests/test_scenarios_{constraints,sensitivity,infeasible}.py`, `ScenariosScreen.tsx` | |
| Scenario promotion | complete | `scenarios/store.py:127-145`: re-solves, `scenario_stale` if inputs moved, creates a normal draft, supersedes the week's other proposals, audits | Matches clarification: new version, old superseded. UI display of superseded unverified (G6) |
| Export CSV/Excel es-ES, formula neutralising | complete | `proposals/export.py:35-104`, `tests/test_export_locale.py` | |
| Export role gate | partial | `services/api-bff/src/routes/api.py:333` allows `viewer`; `scenarios.py:14,42` READ includes viewer; procurement `api/proposals.py:212` requires buyer | Viewer must be refused and audited (G1) |
| No order sent, no ERP write from domain | partial | `tests/test_terms_no_erp.py` covers terms only | Proposal and scenario paths unproven (G4) |
| Generation time at scale | unverified | `tests/perf/test_generation_time.py`, `tests/test_scale.py` | Size not tied to 2,000 SKUs (G5) |
| Playwright e2e | partial | `apps/web/tests/e2e/scenarios.spec.ts` and `proposals-export.spec.ts` mock the API with `page.route` | No API-backed journey incl. refused self-approval (G2) |

## 2. Gaps

- **G1** Viewer can export proposals and scenarios through the gateway; require buyer, approver or admin, refuse and audit the rest.
- **G2** Add an API-backed Playwright journey: generate, explain, edit, scenario, compare, promote, submit, refused self-approval, approve by another user with fresh MFA, export.
- **G3** Add a 20-run determinism test for scenarios and an over-budget explanation test (the cap is flagged, never cut).
- **G4** Add a test that proposal, scenario, approval and export paths make no request to a supplier or to the ERP (network-denied fixture).
- **G5** Pin the generation-time test to a synthetic catalogue of about 2,000 active SKUs.
- **G6** Show superseded proposals and stale scenarios in Spanish in the UI; confirm approval does not carry over to a promoted version.
- **G7** Idempotency of submit, approve, promote, export under repeated requests: confirm and add missing tests.
- **G8** FR-014: malformed or ambiguous inputs reaching generation must go to the review list (T043).
- **G9** FR-012: decimal money, UTC timestamps and variant-id keying must be evidenced for this domain (T044).
- **G10** Edge cases (deactivated supplier, unconfirmed cost, non-EUR supplier) are covered by existing tests but not verified together (T045).
- **G11** Grouped-by-supplier display of approved proposals is unverified (T046).

## 3. Decisions

- **Promotion semantics**: keep existing behaviour (new draft, others superseded). Rationale: already matches the clarification and is audited. Alternative: in-place overwrite, rejected for losing reproducibility.
- **Stale line saves**: return the new `proposal_line_conflict` (HTTP 409) with the Spanish "line changed, reload" text for line saves; the existing `version_conflict` stays unchanged for every other use, so existing consumers do not break. Alternative: automatic merge, rejected for silent-change risk.
- **Discounts**: consume existing supplier-terms data only. Alternative: add tiers here, rejected as it touches files owned by supplier management.
- **Export roles**: confirm first whether the service's `require("buyer")` already admits approver and admin, then enforce at both the gateway and the domain service. Alternative: gateway only, rejected because the service must not trust the gateway alone.
- **E2E approach**: Playwright against the compose stack with the dev token issuer and synthetic fixtures; the existing mocked specs remain for fast UI checks.
- **No new dependency or table**: the inventory shows none needed.

## 4. Open assumptions

- The two-person approval rule still needs at least two eligible users in the synthetic fixture; the e2e seeds them.
- Agent 00 confirms the error key and role clarification (T-note will be drafted, not sent).

## 5. Implementation results (2026-11-15)

Existing tests were executed for this audit: the procurement suite (876 tests), the gateway suite (302), the web unit suite (559) and the mocked Playwright specs for proposals, scenarios, roles and accessibility all pass.

| Gap | Result | Evidence |
|---|---|---|
| G1 viewer export | Fixed. Viewer is refused (403 `auth_forbidden_role`) and audited at the service; the gateway gate is buyer, approver, admin. An approver without the buyer role could not export before (the service required the buyer role); now allowed. | `services/procurement-service/src/api/proposals.py`, `src/api/scenarios.py`, `services/api-bff/src/routes/api.py`, `routes/scenarios.py`; tests `test_export_roles.py`, BFF route tests |
| G2 e2e | Partly met. A real-services Spanish journey runs against the compose stack (screens, viewer refusal on the real gateway); full generate-to-approve cannot run there because the stack has no forecast service and the gateway has no proposal-generation route. The flow is proven by the service tests. | `apps/web/tests/live/procurement-journey.spec.ts`, `tests/e2e/procurement-i18n.spec.ts` |
| G3 determinism | Proven (20 runs). Over-budget behaviour found to be a soft cap: nothing is cut, the excess is reported and lines are flagged; spec aligned. | `test_scenarios_determinism.py`, `test_budget_cap_explanation.py` |
| G4 no outbound | Proven with a network-denied fixture across the proposal and scenario paths. | `test_no_outbound_requests.py` |
| G5 2,000 SKUs | Proven (well under 60 s). | `tests/perf/test_generation_time.py` |
| G6 superseded and stale | `proposal_superseded` enforced on edit, submit, approve and export; Spanish read-only display added. A stale scenario is refused at promotion (`scenario_stale`), not a stored status. Promotion into an approved week returns 409 `proposal_conflict` (the route did not catch it before). | `test_superseded_proposal.py`, `test_promote_into_approved_week.py`, `proposals-superseded.test.tsx` |
| G7 idempotency | Proven: a repeat is refused or returns the same file, with one state effect. | `test_idempotent_actions.py` |
| G8 FR-014 | Defect fixed: a needed variant with only unusable offers disappeared from the proposal without a trace. It is now named in the proposal notes (`no_eligible_supplier:<variant>`) and shown to the buyer as a review note with its SKU. | `src/proposals/generate.py`, `test_review_list_inputs.py`, `test_review_notes_api.py` |
| G9 FR-012 | Evidenced. | `test_proposal_money_time_keys.py` |
| G10 edge cases | Evidenced. | `test_proposal_edge_cases.py` |
| G11 grouping by supplier | Already present (supplier groups and per-supplier export); verified. | `ProposalsScreen.tsx`, `groupLinesBySupplier` |

Not done: `docs/architecture/integration/feature-status.json` (owned by Agent 00) is not edited here; the table above is the evidence to hand over. The Agent 00 note is a draft and has not been sent.

## 6. Agent 00 answer (PR review, 2026-11-15)

- Export routes: confirmed. The matrix lists only `web` as consumer of both export routes and no other agent calls them as a viewer.
- Error keys `proposal_line_conflict` and `proposal_superseded`: accepted as additive.
- `review_notes` and `over_budget`: accepted in substance. The proposal detail response is now described by a new schema, `packages/contracts/dto/proposal_detail.v1.schema.json` (baseline refreshed, model generated), because `proposal.v1` types money as an object and this response returns strings, so changing it would break its baseline. Agent 00 should register the new schema in `contract-matrix.json` (it owns that file). `review_notes[].variant_id` is for the web app's lookups only and is never displayed.
- Role gate recorded in `docs/architecture/integration/gateway-review.md` (G6).
