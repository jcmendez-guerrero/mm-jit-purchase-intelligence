# Feature Specification: Business Policy Configuration (Agent 06)

**Feature Branch**: `claude/jira-mmi-8-spec-f00d63` (Jira MMI-8, epic MMI-1 "MMI 003 | Product completion — parallel agent execution")

**Created**: 2026-11-10

**Status**: Draft

**Input**: User description: "Implement Jira MMI-8 Spec and use Id 011" — Jira MMI-8 "AGENT 06 | Business Policy Configuration — audit, Spec Kit, implement, test and PR" and its linked Confluence page "MMI 003 — Agent 06 — Business Policy Configuration". Scope there: service levels, safety stock, min/max, clinical criticality, budgets, cadence, forecast parameters, exclusions and stockout censorship; scope precedence global/segment/SKU; preview, versions and audit. Acceptance: UI changes persist and alter next calculations, optimistic concurrency, RBAC, audit, defaults and history. The Jira text names the folder `specs/003-agent-06/`; by the owner's instruction this feature uses the id `011` in the repository's own numbering.

## Context

The owner and buyer must be able to steer purchasing by changing business rules in the interface instead of asking a developer. Feature 002 (user story 4, FR-016 to FR-019) already decided what those rules are and the repository already contains a first implementation: policy sets by scope, budget caps, safety-stock overrides with approval, clinical criticality, demand exclusions and rules, forecast parameters, a preview, and a policy console in the web app. What is **not yet evidenced** is that every rule listed in the scope can be changed in the real interface, persists, changes the *next* forecast and proposal, and is covered by tests for concurrency, permissions, audit, defaults and history.

This feature is therefore a **completion and verification unit**, not a greenfield build. It must (1) audit what exists on the latest main branch and record each capability as complete, partial, broken, missing or unverified with file evidence, (2) close the gaps against the requirements below, reusing working code, and (3) prove the acceptance criteria with automated tests and a demonstration in the Spanish interface using synthetic data.

### Baseline audit (first pass, to be re-confirmed during planning)

Read from the code on this branch; no test was run for this pass, so every "exists" below still needs the evidence the plan will collect.

| Capability | First-pass status | Evidence |
|------------|-------------------|----------|
| Service level, safety stock, min/max, cadence by scope (global, segment, product) with product over segment over global, effective dates and revisions | Exists; end-to-end effect on the next proposal unverified | `services/procurement-service/src/policies/service.py`, `migrations/versions/0006_policies.py` |
| Budget caps (global, supplier, category) | Exists; effect on the next proposal unverified | `services/procurement-service/src/policies/service.py`, `src/api/policies.py` |
| Preview of a change without saving | Exists | `src/api/policies.py`, `src/policies/preview.py`, `tests/test_policy_preview.py` |
| Safety-stock override with approval, always-stocked setting | Exists | `src/policies/overrides.py`, `src/policies/stocking.py` |
| Clinical criticality, demand exclusions and rules, forecast parameters | Routes exist through the gateway; persistence and effect on the next forecast unverified; stockout-censoring rules not separately evidenced | `services/api-bff/src/routes/policies.py`, `services/forecast-service/src/api.py`, `src/parameters.py` |
| Policy and parameter versions recorded on proposals and scenarios | Exists for proposals and scenarios; for forecast runs unverified | `services/procurement-service/src/proposals/inputs.py`, `src/scenarios/store.py`, `services/forecast-service/src/runs/runner.py` |
| Per-policy revision history and category history in the interface | Exists; a single audit view of all rule changes unverified | `apps/web/src/features/policies/` |
| Browser tests | Three journeys (preview and save, stale save, viewer read-only) plus safety stock; no journey proves a change alters the next calculation | `apps/web/tests/e2e/policies.spec.ts`, `safety-stock.spec.ts` |

Out of scope: any write to the ERP; changing the forecasting or allocation methods themselves (this feature only configures their inputs); supplier commercial terms (feature 007) and predictive datasets (feature 008); creating or faking ERP movements, stock or costs; sending orders to suppliers; parsing free-text notes; new always-on services.

**Terms used in this spec**: a *policy* is a set of business rule values with a scope, an effective date and a revision; *scope* is global, segment (a product class such as A, B, C, critical or sparse) or product (identified by SKU); the *most specific scope wins* per rule; a *demand exclusion* removes a period of a product's sales from forecasting with a reason; *stockout censoring* is the rule that treats days with no stock as missing demand rather than zero demand; a *forecast parameter* is an approved tuning value of the forecast; a *preview* shows the effect of a change without saving it; *next calculation* means the next forecast run, proposal or scenario created after the policy becomes effective.

## Clarifications

### Session 2026-11-10

- Q: Which roles may change policies? → A: Buyer and admin may edit; approver and viewer may read; a refused attempt is recorded (inherited from feature 002 FR-019).
- Q: Which changes need fresh multi-factor authentication? → A: Changes that move money or stock thresholds across the whole business: budget caps and global-scope values. Product-level and segment-level edits need the normal session only. Safety-stock overrides keep their existing separate approval rule. Defaulted as the conservative reading of the guardrail "MFA for sensitive operations".
- Q: Does the stockout-censoring rule apply by scope, as FR-003 says, or only globally? → A: By scope (owner decision 2026-11-11): global, segment (critical, A, B, C, sparse) or product, resolved most specific first, product over critical over class over sparse over global; each scope and key keeps its own revisions; products are chosen by SKU. Removing a scoped rule is not offered yet; a scoped rule is changed by saving a new value.
- Q: Which business-wide saves need a fresh second factor beyond budget caps and global policy values? → A: Forecast parameters and censoring rules (owner decision 2026-11-11); exclusions stay on the normal session.
- Q: Are past forecast runs and proposals recalculated when a policy changes? → A: No. They keep the versions they recorded; only calculations created after the effective date use the new values.
- Q: Are there values a policy cannot override? → A: Yes, hard limits (service level between 0 and 100 %, no negative quantities, maximum not below minimum, budgets non-negative) are enforced at save time and cannot be bypassed.
- Q: Is the Siweb id ever shown or typed? → A: No. Products are chosen and displayed by SKU; ids are used only internally.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Change a purchasing rule and see the next proposal follow it (Priority: P1)

A buyer opens the policy console, changes a service level, safety stock, minimum or maximum, or replenishment cadence at global, segment or product (SKU) scope, previews the effect, saves it with an effective date, and the next proposal uses the new value and says so in its explanation.

**Why this priority**: This is the acceptance criterion in one sentence: a change made in the interface must alter the next calculation. Without it the console is decoration.

**Independent Test**: With a synthetic catalogue, set a segment service level, preview, save effective today, generate a proposal, and verify the quantities changed as previewed and the proposal records the policy revision used; an earlier proposal is unchanged.

**Acceptance Scenarios**:

1. **Given** current policies, **When** the buyer edits a value and asks for a preview, **Then** the screen lists the affected products by SKU with the expected change in quantity and spend, states that nothing has been saved, and changes nothing stored.
2. **Given** a previewed change, **When** the buyer saves it with an effective date of today, **Then** the next forecast or proposal uses it, and the proposal explanation names the scope and revision that supplied each value.
3. **Given** the same rule set at global, segment and product scope, **When** a proposal is calculated, **Then** the product value wins over the segment value, which wins over the global value, for each rule independently.
4. **Given** a policy saved with a future effective date, **When** that date arrives, **Then** later runs use it, earlier runs are unchanged, and the old value stays visible in the history.
5. **Given** no policy for a rule, **When** a calculation runs, **Then** the documented default applies, and the screen shows that the value is a default rather than a saved choice.
6. **Given** a saved change, **When** the buyer chooses to apply it, **Then** a re-forecast and re-proposal can be requested, and unchanged inputs give identical results.

---

### User Story 2 - Edits are safe: concurrency, permissions and audit (Priority: P1)

Two buyers may open the same policy at once, a viewer may look but not touch, and every change or refusal is traceable.

**Why this priority**: Policies steer real money. A silent overwrite, an unauthorised change or an untraceable change makes the console unsafe to use.

**Independent Test**: Open one policy in two sessions, save in the first, save in the second and verify the conflict; attempt an edit as viewer and approver and verify refusal and a recorded refusal; read the audit trail and find who, what, before, after and when for each change.

**Acceptance Scenarios**:

1. **Given** two people editing the same policy, **When** the second saves from an outdated revision, **Then** the save is refused with a Spanish explanation that shows the newer revision, and nothing is overwritten.
2. **Given** two saves at the same instant, **When** both are processed, **Then** exactly one succeeds and the other receives the conflict.
3. **Given** a viewer or approver, **When** they try to edit any policy, budget, exclusion, criticality or parameter, **Then** the action is refused with a Spanish message and the refusal is recorded.
4. **Given** a change to a budget cap or a global-scope value, **When** the buyer saves without fresh multi-factor authentication, **Then** the save is refused with a message that asks for it; with it, the save succeeds.
5. **Given** any accepted change, **When** an admin opens the audit view, **Then** it shows who changed what, the previous and new values, the scope, the effective date, the revision and the time, and no free-text note content.
6. **Given** a value outside the hard limits (service level outside 0 to 100 %, negative quantity or budget, maximum below minimum, cadence below one day), **When** it is saved, **Then** it is refused with a specific Spanish message and a stable error key, and nothing is stored.

---

### User Story 3 - Budgets and clinical criticality (Priority: P2)

The owner sets monthly or weekly budget caps (global, by supplier, by category) and marks products as clinically critical, so the weekly proposal respects the money limit and never under-stocks critical medicine.

**Why this priority**: Budget and criticality are the two rules the owner cares about most after the service level, but they depend on the editing, preview and audit machinery of stories 1 and 2.

**Independent Test**: Set a weekly budget cap below the unconstrained proposal total and verify the next proposal stays within it and explains what was deferred; mark a product critical and verify its target service level and always-stocked behaviour follow the critical rule.

**Acceptance Scenarios**:

1. **Given** a budget cap, **When** the next proposal is calculated, **Then** the total spend does not exceed it, the lines deferred or reduced are listed with the reason, and the cap and revision are cited.
2. **Given** a product marked clinically critical by its SKU, **When** the next proposal is calculated, **Then** the critical service level applies, the change is audited, and the history of the criticality is visible.
3. **Given** a budget cap and a supplier cap that conflict, **When** a proposal is calculated, **Then** the stricter applies and the explanation says which one bound.
4. **Given** a safety-stock override requested for a product, **When** a second person approves it, **Then** the effective value is shown next to the system recommendation with its source, and the requester cannot approve their own request.

---

### User Story 4 - Forecast parameters, demand exclusions and stockout censoring (Priority: P2)

The owner adjusts approved forecast parameters, excludes one-off periods (for example a promotion or a bulk sale) from a product's demand history, and chooses how days without stock are treated, so forecasts reflect the business and not distortions.

**Why this priority**: These rules change forecast quality rather than purchasing limits, and are the least visible; they need their own proof that the forecast actually changes.

**Independent Test**: Exclude a synthetic spike period for one SKU with a reason, run the forecast, and verify the forecast no longer includes it and the run records the exclusion version; reverse the exclusion and verify the forecast returns; switch the censoring rule and verify days without stock stop counting as zero demand.

**Acceptance Scenarios**:

1. **Given** a product and a period, **When** the buyer saves an exclusion with a reason, **Then** that period is left out of the next forecast, the exclusion is listed on the product, and the run records the version used.
2. **Given** a saved exclusion, **When** the buyer reverses it, **Then** the next forecast includes the period again and the history shows both actions.
3. **Given** the stockout-censoring rule is on, **When** the next forecast runs, **Then** days with no stock are treated as missing demand, not zero demand, for the products covered by the rule's scope.
4. **Given** a forecast parameter from the approved list, **When** the buyer changes it within its allowed range, **Then** the next forecast uses it and records the parameter version; a value outside the range or a parameter not on the list is refused.
5. **Given** a changed parameter, exclusion or censoring rule, **When** the owner reads the run list, **Then** each run shows the policy and parameter versions it used.

---

### User Story 5 - Defaults and history are always visible (Priority: P3)

Anyone allowed to read the console can see, for every rule, whether the value in force is a saved choice or a default, where it comes from (scope and revision), and how it changed over time.

**Why this priority**: It explains the system to its users and supports audits, but the rules work without it.

**Independent Test**: For a product with only a global policy and one with a product override, open the console and verify each rule shows its source; open the history and verify every past revision with its dates is listed and none was edited in place.

**Acceptance Scenarios**:

1. **Given** a product, **When** the user opens its policy view, **Then** every rule shows the value in force, its source (default, global, segment or product), the revision and the effective period.
2. **Given** a policy changed several times, **When** the user opens its history, **Then** each revision appears with its dates, author and values, in order, and earlier revisions cannot be edited.
3. **Given** a default, **When** the buyer overrides it and later removes the override, **Then** the default applies again and the history records both steps.

---

### Edge Cases

- Two policies of the same scope and key whose effective periods overlap: the save is refused with an explanation; the platform never picks one silently.
- A policy effective in the past is entered: refused with a Spanish message, because earlier runs must not change.
- A product moves segment (for example from B to A) after a policy exists: the value follows the product's current segment; the history shows the change of source.
- A SKU in a product-scope policy disappears from the catalogue: the policy is kept, flagged as orphaned in the review list and ignored by calculations; it is never silently deleted.
- A SKU matches more than one product, or differs only by case or spaces: the product-scope edit is refused as ambiguous.
- A preview is requested while a forecast run is in progress: the preview uses the last finished run and says so.
- The preview covers a very large set of products: it answers within the time target or reports progress; it never saves partially.
- A budget cap lower than the cost of the products flagged critical: critical items are still listed, the cap is shown as exceeded, and an approver decides; the platform never drops a critical product silently.
- An exclusion covers the whole history of a product: the product is shown as ineligible for forecast with that reason, not forecast on nothing.
- A change is saved while the calculation service is unavailable: the change is stored and audited, the re-forecast request is queued or reported failed, and the buyer is told which.
- A refused edit, a failed multi-factor check or a stale save leaves the stored policy exactly as it was.

## Requirements *(mandatory)*

### Functional Requirements

**Editing the rules**

- **FR-001**: Authorised users MUST be able to view and change, from the interface, service levels, safety stock, minimum and maximum, and replenishment cadence at global, segment and product scope, with product identified by SKU.
- **FR-002**: Authorised users MUST be able to set budget caps (global, by supplier, by category and period) and clinical criticality per product, and to manage the safety-stock override and always-stocked settings that already exist.
- **FR-003**: Authorised users MUST be able to adjust the approved forecast parameters within their allowed ranges, to add, reverse and list demand exclusions with a reason, and to set the stockout-censoring rule by scope.
- **FR-004**: For each rule the most specific scope MUST win (product over segment over global) independently of the other rules, and the explanation of every proposal and forecast MUST state the scope and revision that supplied each value.
- **FR-005**: Where no policy exists for a rule, a documented default MUST apply and the interface MUST say that the value is a default.

**Preview, effective dates and next calculations**

- **FR-006**: Every change MUST offer a preview that lists affected products by SKU and the expected change in quantity and spend, states that nothing is saved, and stores nothing.
- **FR-007**: Every change MUST carry an effective date; the next forecast, proposal and scenario created on or after it MUST use the new value, and earlier ones MUST remain unchanged.
- **FR-008**: Every forecast run, proposal and scenario MUST record the policy, parameter and exclusion versions it used.
- **FR-009**: The buyer MUST be able to request a re-forecast and re-proposal after a change; unchanged inputs MUST produce identical results.

**Safety**

- **FR-010**: Saves MUST use optimistic concurrency: a save based on an outdated revision, or a simultaneous second save, MUST be refused with a conflict explanation and MUST NOT overwrite; the refusal MUST show the newer revision.
- **FR-011**: Only buyer and admin MAY change policies; approver and viewer MAY read. Refused attempts MUST be refused and recorded.
- **FR-012**: Changes to budget caps, to global-scope values, to forecast parameters and to stockout-censoring rules MUST require fresh multi-factor authentication (owner decision 2026-11-11); exclusions and segment- or product-level policy values need the normal session; the safety-stock override approval rule of feature 002 (approver is not the requester) MUST be kept.
- **FR-013**: Every accepted change and every refusal MUST be audited with actor, action, scope, previous and new values, effective date, revision and UTC time; the audit MUST never contain free-text note content, and an admin MUST be able to read it in the interface.
- **FR-014**: Values MUST be validated against hard limits (service level 0 to 100 %, no negative quantities or budgets, maximum not below minimum, cadence of at least one day, parameters inside their ranges); invalid input MUST be refused with a specific Spanish message and a stable error key, and nothing stored. Money MUST be exact decimal.
- **FR-015**: Overlapping effective periods for the same scope and key MUST be refused; an effective date in the past MUST be refused, because earlier runs must stay reproducible (decision recorded in plan research D1).

**History and data integrity**

- **FR-016**: Past revisions MUST be kept and shown in order with dates, author and values, and MUST NOT be edited or deleted; removing an override MUST create a new revision that restores the default.
- **FR-017**: A policy that refers to a SKU no longer in the catalogue MUST be kept, flagged for review and ignored by calculations, never dropped silently.
- **FR-018**: Ambiguous or unknown SKUs in a product-scope edit MUST be refused; Siweb identifiers MUST NOT be displayed or typed.
- **FR-019**: A critical product MUST NOT be silently dropped when a budget cap binds; the excess MUST be shown for decision.

**Interface and cost**

- **FR-020**: All user-facing text MUST be Spanish (es-ES) with EUR, date and number formats of that locale, and no hard-coded strings; the console MUST be keyboard-usable and meet the accessibility baseline already applied to the other screens.
- **FR-021**: The feature MUST add no always-on service and MUST stay within the shared monthly budget; preview and re-forecast work MUST run on demand and stop when done.
- **FR-022**: No request MUST be made to the ERP by any policy action; policies stay local to MMI.

### Key Entities

- **Policy**: a set of rule values (service level, safety stock, minimum, maximum, cadence) for one scope and key, with an effective period, a revision and an author.
- **Scope**: global, segment (A, B, C, critical, sparse) or product (a SKU); resolved per rule by specificity.
- **Budget cap**: an amount for a period at global, supplier or category scope, with effective dates and a revision.
- **Clinical criticality**: a per-product marker that selects the critical service level and always-stocked behaviour.
- **Safety-stock override request**: a requested replacement of the recommended safety stock, minimum or maximum, with reason, requester, approver and state.
- **Demand exclusion**: a period of a product's demand left out of forecasting, with reason and reversal.
- **Censoring rule**: the setting that treats days without stock as missing demand, by scope.
- **Forecast parameter**: an approved tuning value with an allowed range and a version.
- **Policy audit record**: who changed what, when, before and after, or who was refused and why.
- **Effective policy view**: for one product, the value in force per rule with its source, revision and period.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For each of the rules in the scope (service level, safety stock, minimum, maximum, cadence, budget, criticality, forecast parameter, exclusion, censoring), a change made in the interface alters the next forecast or proposal in an automated end-to-end test, and an earlier run is unchanged; 10 of 10 rules covered.
- **SC-002**: A buyer can preview, save and apply a single-rule change in under 3 minutes without developer help.
- **SC-003**: 100% of accepted changes and 100% of refused attempts appear in the audit view with actor, scope, before and after and time.
- **SC-004**: In concurrency tests, 100% of stale or simultaneous second saves are refused and 0 stored values are overwritten.
- **SC-005**: 100% of edit attempts by viewer and approver are refused, and 100% of budget and global-scope saves without fresh multi-factor authentication are refused.
- **SC-006**: 100% of forecast runs, proposals and scenarios created after the feature list the policy, parameter and exclusion versions they used.
- **SC-007**: For every rule shown to a user, the interface states whether the value is a default or a saved choice and its source; 0 rules shown without a source.
- **SC-008**: A preview over the full synthetic catalogue answers within 5 seconds, or shows progress, and changes nothing stored.
- **SC-009**: 0 requests are sent to the ERP by any policy action, 0 Siweb identifiers are visible in the console, and 0 hard-coded user-facing strings are added.
- **SC-010**: The full set of unit, contract, database integration, security-abuse and browser tests for the console passes on synthetic data only, and the Spanish interface is demonstrated end to end with screenshots in the pull request.

## Assumptions

- Feature 002 remains the source of the rule list and of the role model; this feature completes and proves it and does not redefine it.
- Feature 007 (supplier terms) and feature 008 (seed datasets) own their own versioning; this feature only reads the versions they expose to record them next to the policy versions.
- Segment membership (A, B, C, critical, sparse) is computed elsewhere; this feature only reads it.
- The set of approved forecast parameters and their allowed ranges already exists in the forecast service; changing the set itself is out of scope.
- Hard limits, the default values and the multi-factor rule are those of the existing console and constitution unless the baseline audit shows a defect.
- Synthetic fixtures from the shared testing package are used throughout; no real catalogue data, supplier, price or quantity is committed.
- Delivery is one reviewable pull request that does not deploy to production, does not merge to main and does not write to the ERP; shared contract changes go through Agent 00.
