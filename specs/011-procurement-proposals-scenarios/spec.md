# Feature Specification: Procurement Proposals & Scenarios (Agent 03)

**Feature Branch**: `claude/speckit-specify-jira-mmi5-d4aabd`

**Created**: 2026-11-13

**Status**: Draft

**Input**: Jira MMI-5 ("AGENT 03 | Procurement Proposals & Scenarios", epic MMI-1) and its Confluence page 3145771. The Jira text names `specs/003-agent-03/`; number 003 is already taken, so this directory (011, the next free number after 010) replaces it.

## Context

Features 001 and 002 already deliver weekly proposals by SKU and supplier, explained lines, buyer edits, approval with separation of duties and fresh MFA, supplier allocation, scenarios with sensitivity and comparison, CSV/Excel export and order confirmation. What the owner needs now is the whole domain **proven complete and deterministic**: the same supplier constraints always give the same scenario, every proposal line can be explained, nobody approves their own work, and nothing is ever sent to a supplier or written to the ERP beyond the two permitted writes.

This is therefore an **audit-then-close-gaps** feature. It starts with an evidence-backed inventory of the current main (complete, partial, broken, missing, unverified, each with file evidence), reuses what works, and builds only what the inventory shows missing or unproven. Siweb360 stays the source of truth for catalogue, stock, movements and ERP costs; this feature adds no ERP request of any kind.

Out of scope: sending orders to suppliers; any ERP write; production deployment or merge to main; changes to files owned by other agents (shared contracts go through Agent 00); forecasting and policy editing (owned elsewhere; this feature only consumes them).

## Clarifications

### Session 2026-11-13

- Q: When a buyer promotes a scenario, does it replace the current draft or create a new version? → A: It creates a new proposal version in draft state; the previous version stays viewable and is marked superseded.
- Q: Are volume-discount tiers added by this feature or only applied when supplier terms already hold them? → A: Only applied when supplier terms already hold them; any gap is recorded in the inventory and raised with Agent 00, with no new supplier-terms editing here.
- Q: When two buyers edit the same proposal line at once, is the second save rejected or merged? → A: Rejected with a Spanish "line changed, reload" message; nothing is overwritten or merged silently.
- Q: Which roles may export an approved proposal? → A: Buyers, approvers and admins; viewers cannot, and the refused attempt is audited.
- Q: What catalogue size is the proposal-generation time target tested against? → A: About 2,000 active SKUs.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Weekly proposal by SKU and supplier, explained line by line (Priority: P1)

A buyer opens the weekly proposal and sees, per SKU and supplier, the quantity to order, cost and its source, lead time, pack size and the reason, including which constraint (minimum order, pack multiple, shipping, discount, budget) shaped it. The buyer can edit lines; every edit is recorded and constraints are re-checked.

**Why this priority**: The proposal is the product's core output; every other story depends on it being correct and understandable.

**Independent Test**: Generate a proposal from synthetic data and confirm each line carries a Spanish explanation naming its binding constraints; edit a line below a supplier minimum and confirm the warning and the audit entry.

**Acceptance Scenarios**:

1. **Given** synthetic stock, demand and supplier terms, **When** a proposal is generated twice from the same inputs, **Then** both are identical line by line and carry the same input and rule versions.
2. **Given** a line whose quantity was rounded up to a pack multiple or raised to meet a minimum order, **When** the buyer opens its explanation, **Then** the rounding or top-up and its cost impact are stated in Spanish.
3. **Given** a supplier minimum that cannot be met, **When** the proposal is generated, **Then** the shortfall is flagged with its cost impact instead of being hidden or silently dropped.
4. **Given** a buyer edit, **When** it is saved, **Then** who, when, old and new value are recorded and constraints are re-validated.

---

### User Story 2 - Changing supplier constraints changes the scenario deterministically (Priority: P1)

A buyer creates a scenario by changing supplier constraints (minimum order, lead time, packs, shipping charge, discount, budget cap, excluded supplier) without touching the real proposal. The result is reproducible, shows what changed against the base and why, and can be compared side by side.

**Why this priority**: This is the first completion gate of the Jira task.

**Independent Test**: Run a scenario, repeat it with identical inputs and confirm identical results; change one constraint and confirm the difference matches the explanation.

**Acceptance Scenarios**:

1. **Given** a base proposal and a set of constraint changes, **When** the scenario is run repeatedly, **Then** the result and its fingerprint are identical every time.
2. **Given** one changed constraint, **When** the scenario is re-run, **Then** only the affected lines change and each change is explained.
3. **Given** two or more scenarios, **When** the buyer compares them, **Then** total cost, per-supplier spend, shortfalls and binding constraints are shown side by side, with the most cost-sensitive constraints ranked.
4. **Given** constraints that make a plan impossible (for example a budget below every minimum), **When** the scenario runs, **Then** it reports infeasibility with the conflicting constraints, never a partial silent result.
5. **Given** a scenario, **When** it is run, **Then** the real proposal and supplier terms are unchanged until a buyer explicitly promotes it.
6. **Given** a scenario is promoted, **When** the buyer opens the proposal, **Then** a new draft version exists with the scenario's lines, the previous version is viewable and marked superseded, and the new version needs its own submission and approval.

---

### User Story 3 - Approval with separation of duties and no order sent (Priority: P1)

A buyer submits the proposal; a different approver, with fresh MFA, approves it. Approved proposals are grouped by supplier for manual ordering and exported to CSV and Excel. The system never sends an order to a supplier and never creates an ERP order.

**Why this priority**: Second and third completion gates of the Jira task, and a non-negotiable project rule.

**Independent Test**: Submit as one user and attempt approval as the creator, the last editor, a viewer and an eligible approver with stale and fresh MFA; confirm outcomes, audit entries and that no outbound supplier or ERP request exists.

**Acceptance Scenarios**:

1. **Given** a submitted proposal, **When** its creator or last editor tries to approve, **Then** it is refused with a stable reason and the refusal is audited.
2. **Given** an eligible approver whose MFA is stale, **When** they approve, **Then** a fresh sign-in is demanded; with fresh MFA the approval succeeds as a distinct recorded transition.
3. **Given** an edit after submission, **When** it is saved, **Then** approval eligibility is reset and the proposal returns to review.
4. **Given** fewer than two eligible people could satisfy the rule, **When** a buyer submits, **Then** submission is refused and explains why.
5. **Given** a viewer, **When** they try to export, **Then** it is refused and audited.
6. **Given** an approved proposal, **When** it is exported as CSV or Excel, **Then** the file uses es-ES number and date formats, neutralises spreadsheet-formula injection and contains no free-text notes or secrets.
7. **Given** any proposal or scenario action, **When** network activity is inspected in tests, **Then** no request to a supplier or to the ERP exists.

---

### User Story 4 - Budgets, shipping and discounts shape the plan transparently (Priority: P2)

The buyer sets a budget cap and sees how shipping charges, free-delivery thresholds and volume discounts change the plan; when the cap cannot be met, the system says by how much it is exceeded and which lines (and clinically critical needs) are involved. It never cuts quantities on its own: the buyer decides what to reduce.

**Why this priority**: These constraints drive real savings but the proposal is already usable without full coverage.

**Independent Test**: Set a cap below the unconstrained total and confirm cuts follow the documented priority and are listed with their reason.

**Acceptance Scenarios**:

1. **Given** a budget cap below the unconstrained total, **When** the proposal is generated, **Then** the proposal still carries every needed quantity (clinically critical needs are never dropped), the excess over the cap is shown with its amount, and every line is flagged as over budget so the buyer can edit it.
2. **Given** a supplier whose free-delivery threshold is just out of reach, **When** the plan is built, **Then** the system shows whether topping up or reallocating is cheaper and why it chose one.
3. **Given** a quantity discount tier already held in the supplier terms, **When** quantities cross it, **Then** the discount applies and is stated on the line.

---

### User Story 5 - Proven end to end in the Spanish UI (Priority: P2)

The whole journey (generate, explain, edit, scenario, compare, promote, submit, approve, export) can be demonstrated in the Spanish (es-ES) screens and is covered by automated end-to-end tests with synthetic data only.

**Why this priority**: The completion gate demands demonstrated evidence, but it builds on Stories 1 to 4.

**Independent Test**: Run the end-to-end suite and confirm it passes and that every visible string is Spanish with EUR and Spanish date formats.

**Acceptance Scenarios**:

1. **Given** the synthetic stack, **When** the end-to-end suite runs, **Then** every step of the journey is exercised, including the refused self-approval.
2. **Given** any proposal or scenario screen, **When** inspected, **Then** all text is es-ES and amounts and dates follow Spanish formats.

### Edge Cases

- A supplier is deactivated or its cost is stale/unconfirmed after a proposal is generated: the line is flagged, never silently repriced.
- Two buyers edit the same line at once: the second save is rejected with a Spanish "line changed, reload" message; nothing is overwritten or merged silently.
- A scenario refers to a supplier later removed, or its inputs have moved since it was run: it is marked stale and cannot be promoted.
- An export is requested for a non-approved proposal: refused with a stable reason.
- Repeated submit, approve or promote requests (double click, retry): one effect only.
- Amounts in a non-EUR currency: converted with the stored rate and shown with the original.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST first produce an evidence-backed inventory of this domain on the current main (complete, partial, broken, missing, unverified, each with file evidence) and reuse what works.
- **FR-002**: The system MUST generate one company-wide weekly proposal by SKU and supplier, deterministically from the same inputs, recording input, rule and model versions.
- **FR-003**: Every proposal line MUST explain quantity, supplier, cost and source, lead time, pack, binding constraints, risk and confidence, in Spanish.
- **FR-004**: The system MUST apply minimum order value and quantity, pack multiples, lead time, shipping charge, free-delivery threshold, volume discount (only where the supplier terms already hold discount data; a missing capability is recorded in the inventory and raised with Agent 00, not built here) and budget cap, and MUST flag unmet minimums as shortfalls with cost impact.
- **FR-005**: Buyers MUST be able to edit lines; every edit MUST record who, when, old and new value and re-validate constraints; a save based on a stale version of a line MUST be rejected with a reload message.
- **FR-006**: Scenarios MUST run on a copy, leave the real proposal and supplier terms untouched, and give identical results for identical inputs.
- **FR-007**: Scenarios MUST explain each difference against the base, rank the most cost-sensitive constraints, report infeasibility with its cause, and support side-by-side comparison.
- **FR-008**: Promoting a scenario MUST require an explicit buyer action, MUST create a new draft proposal version (the previous version is kept and marked superseded, and any earlier approval does not carry over; a promotion for a week that already has an approved or exported proposal is refused as `proposal_conflict`, so an approved plan is never replaced), and MUST be audited; stale scenarios MUST NOT be promotable. "Stale" means the inputs changed since the scenario was run.
- **FR-009**: Approval MUST be refused for the creator and last editor, require fresh MFA, be a distinct audited transition, and reset after any later edit; submission MUST be refused when fewer than two eligible people exist.
- **FR-010**: Approved proposals MUST be shown grouped by supplier and exportable to CSV and Excel by buyers, approvers and admins only (a viewer's attempt is refused and audited), in es-ES formats with formula-injection neutralisation and no free-text notes.
- **FR-011**: The system MUST NOT send orders to suppliers and MUST NOT make any ERP request from this domain; tests MUST prove it.
- **FR-012**: Money MUST be exact decimal; timestamps UTC with the original string; products keyed internally by variant id while users see and supply SKUs.
- **FR-013**: Submit, approve, promote and export MUST be idempotent; refusals and security events MUST be audited without secrets or personal data.
- **FR-014**: Malformed or ambiguous inputs MUST go to the review list, never be dropped silently.
- **FR-015**: All user-facing text MUST be Spanish (es-ES) with EUR and Spanish date and number formats, with no hard-coded strings.
- **FR-016**: The domain MUST be covered by unit, API contract, database integration, security-abuse and end-to-end tests using synthetic fixtures only, and MUST keep shared contracts changes to Agent 00.

### Key Entities

- **Proposal**: the weekly company-wide purchase plan; has a state (draft, submitted, approved, superseded; an approved proposal that has been exported is only marked as exported, not a separate state), versions of inputs, creator and last editor; promoting a scenario creates a new version.
- **Proposal line**: one SKU and supplier with quantity, cost and source, constraints applied, explanation, risk and confidence.
- **Supplier terms**: minimum order, delivery charge, free-delivery threshold, discounts, lead time, order days (versioned, owned by supplier management).
- **Scenario**: a named set of constraint changes with its result, fingerprint, differences, sensitivity and status (computing, ready, failed, promoted); a scenario whose inputs moved since it was run is refused at promotion as stale.
- **Approval record**: who submitted, who approved, when, MFA freshness, outcome.
- **Export**: a CSV or Excel file of an approved proposal, per supplier or whole.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running the same scenario 20 times on identical inputs gives 20 identical results.
- **SC-002**: Changing any single supplier constraint changes only the lines it affects, and 100 % of changed lines carry an explanation.
- **SC-003**: 100 % of attempted self-approvals (creator or last editor) are refused and audited in tests.
- **SC-004**: Zero outbound requests to suppliers or the ERP are observed across the full test suite.
- **SC-005**: A buyer can go from opening a proposal to a compared scenario in under 3 minutes on synthetic data.
- **SC-006**: A proposal for a synthetic catalogue of about 2,000 active SKUs is generated in under 60 seconds.
- **SC-007**: The end-to-end suite passes with every visible string in Spanish and all amounts and dates in Spanish formats.
- **SC-008**: The inventory covers 100 % of this domain's user stories with a status and file evidence each.

## Assumptions

- Features 001 and 002 code on main is the starting point; gaps are found by the inventory, not assumed.
- Forecasts, policies and supplier terms are provided by other features; this feature consumes them read-only.
- Roles, MFA and the audit trail come from the identity/administration feature (010).
- Synthetic fixtures from `packages/testing` are sufficient; no real data is used.
- A budget cap is a soft limit, as in the existing allocation and scenarios: the plan minimises cost, flags the excess and never cuts quantities automatically (a human decides purchases). Automatic cutting by priority is out of scope.
- Excel and CSV remain the only export formats.
