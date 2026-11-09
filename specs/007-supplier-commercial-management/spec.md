# Feature Specification: Supplier Commercial Management (MMI 003 / Agent 04)

**Feature Branch**: `claude/speckit-specification-d01b1d`

**Created**: 2026-11-08

**Status**: Draft

**Input**: User description: "Get the specification from Jira MMI-6 (AGENT 04 | Supplier Commercial Management) and its linked Confluence page 'MMI 003 / Agent 04'. Scope: supplier master and product-supplier overrides; costs and provenance, lead time, MOQ value/units, delivery schedule/cutoff, shipping thresholds, discounts, payment terms, preferred status, validity and audit. Acceptance: CRUD persists; effective dates and revision conflicts handled; optimizer consumes local terms; Siweb canonical facts unchanged."

## Context

This is one of the parallel agent assignments of epic MMI-1 ("MMI 003 | Product completion"). It owns the **supplier commercial domain**: who the platform buys from and on which terms. Features 002 and 004 already delivered large parts of it (effective-dated supplier terms, supplier screens, product-supplier links, the proposal engine consuming terms). This feature is therefore **audit first**: it verifies, against the latest main branch, which capabilities are complete, partial, broken, missing or unverified, then closes the gaps so the completion gate below holds end to end. Working code is reused, not rewritten.

**Ownership boundary**: the ERP (Siweb360) stays the source of truth for the catalogue, stock, movements and ERP costs. The platform owns the versioned local supplier conditions (lead time, minimums, delivery schedule, shipping thresholds, discounts, preferred status, validity). Shared interface contracts are coordinated by the integration agent (Agent 00); this feature changes nothing owned by another agent.

**Out of scope**: sending orders to suppliers, changes to forecasting or policy logic, any new ERP write beyond the two already permitted by the constitution, production deployment, and loading real data anywhere but the local environment.

**Terms used**: *terms* are a supplier's local commercial conditions; a *terms version* is one immutable, effective-dated record of them; a *link* is a product-supplier offer (cost, pack multiple, minimum, reference, rank); an *override* is a link-level value that takes precedence over the supplier-level default for that product; *provenance* is the recorded origin of a value (ERP, import, manual) with who and when.

## Clarifications

### Session 2026-11-08

- Q: How should a supplier quoting in a currency other than EUR be handled when no exchange rate is configured? → A: Use Frankfurter <https://frankfurter.dev> as the exchange-rate source: a scheduled job fetches the official ECB reference rates and stores them locally with their date; allocation converts using the stored rate and never calls the rate service during a proposal. Currencies the ECB does not publish, or a rate older than 7 days, leave the supplier out of automatic allocation and list it for buyer review.

### Session 2026-11-09

- Q: How are the review findings on the delivered work (audit volume, request handling, size limits, rate-feed read) folded into this specification? → A: They update this feature (no new feature): FR-038 to FR-041 and SC-013 are added, FR-028 is tightened, and the matching tasks are appended to tasks.md.
- Q: How are the second review's findings (concurrent refusals, rate-refresh failure) folded in? → A: Into this same feature: FR-042, FR-043 and SC-014 are added, the replica limit is recorded as an assumption, and the matching tasks are appended to tasks.md.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Audit the current state and publish the evidence (Priority: P1)

Before any change, the owner needs to know what already works. The audit inspects the latest main branch and classifies every capability in scope as complete, partial, broken, missing or unverified, each with file and line evidence and a note on what to reuse.

**Why this priority**: It prevents rebuilding what exists, defines the real gap list, and is a mandatory deliverable of the assignment.

**Independent Test**: Review the audit document: every scope item (supplier master, overrides, cost provenance, lead time, MOQ value/units, delivery schedule/cutoff, shipping thresholds, discounts, payment terms, preferred status, validity, audit) has a status and at least one evidence reference, and no item is left unclassified.

**Acceptance Scenarios**:

1. **Given** the latest main branch, **When** the audit is complete, **Then** each scope item carries exactly one status (complete / partial / broken / missing / unverified) with file and line evidence.
2. **Given** an item classified as partial, broken or missing, **When** the audit is read, **Then** it points to the requirement and task in this feature that closes it.
3. **Given** an item classified as complete, **When** the audit is read, **Then** a test that proves it is named, or the item is reclassified as unverified.

---

### User Story 2 - Maintain the supplier master and its commercial terms (Priority: P1)

A buyer or admin creates, edits, deactivates and reactivates suppliers, and maintains each supplier's terms: lead time, minimum order value and minimum units, delivery weekdays and order cutoff time, free-shipping threshold and delivery charge, volume discounts, payment terms, preferred status and validity. Every save is stored and visible after reload.

**Why this priority**: The proposal engine can only allocate quantities to suppliers whose terms are correct, current and stored. This is the heart of the acceptance criteria ("CRUD persists").

**Independent Test**: Create a supplier, set terms, reload the screen and read the data back through the API; the values match exactly. Edit, deactivate and reactivate and confirm each state change persists and is audited.

**Acceptance Scenarios**:

1. **Given** a buyer on the suppliers screen, **When** they save a new supplier with its required data, **Then** it persists, appears in the list after a reload, and the creation is audited with who and when.
2. **Given** a saved supplier, **When** the buyer saves new terms, **Then** a new terms version is appended, earlier versions remain readable unchanged, and the history shows who changed what and when.
3. **Given** terms with invalid values (negative amounts, a cutoff that is not a valid time, more discount tiers than allowed, a percentage above 100), **When** saving, **Then** the save is refused with a Spanish message naming the field and nothing is stored.
4. **Given** a viewer, **When** they open the suppliers screen, **Then** they can read but not change anything.
5. **Given** a supplier with open proposal lines, **When** the buyer deactivates it, **Then** the affected lines are shown before confirmation and, once confirmed, the supplier is no longer proposed while its history is kept.

---

### User Story 3 - Plan future changes with effective dates and handle edit conflicts (Priority: P1)

A buyer records a change that starts on a future date (a supplier's new price list, a new delivery weekday) and optionally an end date, without disturbing what is in force today. When two people edit the same supplier's terms at the same time, the second save is stopped and told exactly what changed instead of silently overwriting.

**Why this priority**: Both behaviours are explicit acceptance criteria. Silent overwrites or wrong-date terms would produce wrong purchase quantities.

**Independent Test**: Save terms with a start date next month; verify today's proposals still use the current version and a proposal dated after the start uses the new one. Open the same supplier in two sessions, save in one, then save in the other and verify the second is rejected with the current version shown.

**Acceptance Scenarios**:

1. **Given** terms in force today, **When** a buyer saves a version that starts on a future date, **Then** today's calculations still use the current version and calculations dated on or after the start use the new one.
2. **Given** a version with an explicit end date, **When** that date passes, **Then** it no longer applies and the previous or default behaviour is stated clearly in the interface.
3. **Given** two users who both loaded version n, **When** the first saves and the second then saves, **Then** the second save is rejected as a revision conflict, nothing is overwritten, and the user sees the newer version and can re-apply their change.
4. **Given** overlapping or contradictory validity ranges in one save, **When** saving, **Then** the save is refused with an explanation rather than resolved silently.
5. **Given** a retry of the same save request (for example after a network failure), **When** it is sent twice, **Then** only one version is created.

---

### User Story 4 - Product-level overrides, costs and provenance (Priority: P2)

For each product a supplier offers, the buyer sets the supplier's cost, pack multiple, minimum quantity, supplier product reference and rank, and may override supplier-level terms for that product (for example a different lead time or minimum). Every cost shows where it came from (ERP, import, manual), who set it and when, and a manual cost never silently replaces an ERP cost.

**Why this priority**: Costs and overrides drive allocation and margins, but they build on the supplier terms of stories 2 and 3.

**Independent Test**: Link a product to two suppliers with different costs and one override; generate a proposal and verify the line uses the override, the cheaper compliant supplier wins per the existing allocation rules, and the cost shows its source and author.

**Acceptance Scenarios**:

1. **Given** a link with a product-level override, **When** a proposal is generated, **Then** the override takes precedence over the supplier default for that product only.
2. **Given** a cost entered manually that differs from the ERP cost, **When** viewing the link, **Then** both values and their sources are visible and the difference is flagged; neither is overwritten silently.
3. **Given** products referenced by SKU, **When** the buyer links, filters or bulk-assigns, **Then** only SKUs are shown or entered; ERP ids are never visible.
4. **Given** several suppliers for one product, **When** the buyer ranks them, **Then** the preferred supplier is shown first and wins when offers are otherwise equal, while a clearly better compliant offer from another supplier is still chosen and the line explains why.

---

### User Story 5 - Proposals use the local terms; ERP facts stay unchanged (Priority: P1)

The weekly proposal uses the terms version in force on the proposal date: lead time, minimums, delivery schedule and cutoff, free-shipping thresholds, discounts and pack multiples. Each proposal line explains which terms and which version it used. Throughout, catalogue, stock, movements and ERP costs held from the ERP are never altered by supplier maintenance.

**Why this priority**: This closes the loop between configuration and purchasing, and protects the system of record, two acceptance criteria.

**Independent Test**: Change a supplier's minimum order value, regenerate a proposal and verify the lines change accordingly and each line names the terms version used; compare ERP-sourced data before and after and verify it is identical.

**Acceptance Scenarios**:

1. **Given** a supplier with a minimum order value above a proposed total, **When** a proposal is generated, **Then** the shortfall is shown and lines are topped up, consolidated or flagged according to the existing allocation rules, never silently dropped.
2. **Given** a delivery schedule and cutoff, **When** a proposal is generated before or after the cutoff, **Then** the expected delivery date shown follows the schedule.
3. **Given** a proposal already generated, **When** terms later change, **Then** that proposal keeps the version it recorded and shows it.
4. **Given** any create, edit or deactivate of supplier data, **When** it completes, **Then** no ERP-owned record (catalogue, stock, movements, ERP costs) has changed, and no request to the ERP was made except the two writes the constitution permits after buyer/admin review with fresh MFA.

---

### User Story 6 - Security, audit and traceability of every change (Priority: P2)

Every change to a supplier, its terms, a link or a cost is attributable, tamper-evident and reviewable. Sensitive operations require the right role and a fresh second factor. Abuse attempts (role escalation, cross-supplier access, oversized or malformed input, replayed requests) are refused and recorded.

**Why this priority**: It is a non-functional guardrail that must hold for stories 2 to 5, with its own verification.

**Independent Test**: Attempt each abuse case with a viewer and with a buyer lacking a fresh second factor; verify refusal, the Spanish error, and an audit entry for the attempt.

**Acceptance Scenarios**:

1. **Given** any supplier change, **When** it is saved, **Then** an audit entry records who, when, what changed (before and after) and the terms version.
2. **Given** a user without the buyer or admin role, **When** they call a change operation directly, **Then** it is refused regardless of what the interface hides.
3. **Given** a sensitive operation (releasing a cost to the ERP, overriding an ERP cost), **When** the second factor is older than allowed, **Then** it is refused until the user re-confirms.
4. **Given** free-text fields, **When** saving, **Then** no ERP note content, tax identifier or bank detail is stored, shown or used in decisions.

---

### Edge Cases

- A supplier is deactivated while a proposal containing it is awaiting approval: the affected lines are flagged and the proposal cannot be approved until reallocated.
- Two terms versions start on the same date: the later saved wins deterministically and the earlier is shown as superseded.
- A terms version ends and no later version exists: the interface states which defaults apply and warns the buyer before the end date.
- A supplier created locally has no ERP counterpart ("pending link in ERP"): nothing is sent to the ERP and its local terms still drive proposals.
- Supplier currency is not EUR: amounts stay in the supplier currency; the EUR equivalent is shown using the stored reference rate and its date. With no rate, an unsupported currency, or a rate older than 7 days, the supplier is excluded from automatic allocation and listed for review.
- The rate service is unreachable or returns an error: the last stored rate stays in use until it is 7 days old; nothing in supplier maintenance or proposal generation fails.
- Minimum order in units and in value both apply: the stricter one governs and the interface says which.
- Discount tiers overlap or are not increasing: refused at save time.
- A save arrives with a stale revision and also an invalid field: the conflict is reported first, without partial storage.
- Duplicate supplier name (ignoring case and accents): warn and require confirmation; never merge automatically.
- Very long supplier lists: the screen stays usable through search and filters; pagination is not needed at the expected scale of tens of suppliers.
- The ERP is unreachable: all supplier maintenance and proposals keep working from local terms.
- A caller repeats the same invalid request many times (or sends requests with no sign-in): the audit trail records one entry per minute per caller, target and reason with a repeat count, and other users are not slowed.
- Fifty identical refused requests arrive at the same instant: exactly one audit entry is stored and the skipped count is fifty minus one; none is lost silently.
- The exchange-rate refresh fails in its storage step (not only in the download): change events still leave the service in the same pass and the failure is reported.
- A change request is sent with a body larger than the limit under a non-JSON content type: refused as too large, nothing is read beyond the limit.

## Requirements *(mandatory)*

### Functional Requirements

**Audit and reuse**

- **FR-001**: The feature MUST produce an audit of the latest main branch that classifies each in-scope capability as complete, partial, broken, missing or unverified, with file and line evidence, and MUST reuse working code rather than duplicate it.
- **FR-002**: Every gap found by the audit MUST map to a requirement in this specification and to a task; no item may remain unclassified.

**Supplier master**

- **FR-003**: Buyers and admins MUST be able to create, edit, deactivate and reactivate suppliers; every state persists across reloads and restarts.
- **FR-004**: A supplier MUST capture commercial name, fiscal type, country, currency, payment terms in days, order contact channel, purchasing or non-purchasing classification and active status; tax identifiers and bank details MUST NOT be stored.
- **FR-005**: Deactivated or non-purchasing suppliers MUST never be proposed, MUST keep their history, and MUST show affected open proposal lines before deactivation is confirmed.
- **FR-006**: The system MUST warn on probable duplicate suppliers (same name ignoring case and accents) and MUST NOT merge them automatically.

**Commercial terms**

- **FR-007**: For each supplier, buyers and admins MUST be able to maintain: lead time (days); minimum order value; minimum order units; order days; delivery weekdays; order cutoff time; free-shipping threshold; delivery charge; volume discount tiers (by value or by units, percentage or amount, up to the defined maximum number of tiers); payment terms; preferred status; reliability indicator; and a validity start and optional end.
- **FR-008**: Terms MUST be stored as append-only, effective-dated versions: a save never alters an earlier version; the version in force on a given date is the latest that has started and not ended.
- **FR-009**: The system MUST validate terms on save (non-negative money and quantities, valid cutoff time, discount tiers within limits and consistent, valid date range) and reject invalid input with a Spanish message naming the field, storing nothing.
- **FR-010**: The interface MUST show the version history of a supplier's terms (who, when, what changed) and which version is in force today and which are planned.

**Effective dates, conflicts and idempotency**

- **FR-011**: Buyers MUST be able to save terms that start in the future and optionally end on a date, without changing calculations dated before the start.
- **FR-012**: Saves MUST use optimistic concurrency: a save based on a version that is no longer current MUST be rejected as a revision conflict, store nothing, and tell the user the current version so they can reapply.
- **FR-013**: Overlapping or contradictory validity ranges within a single save MUST be refused with an explanation.
- **FR-014**: Repeated delivery of the same save request MUST create at most one version (idempotent saves).

**Product-supplier links and overrides**

- **FR-015**: For each product a supplier offers, buyers and admins MUST be able to set cost, pack multiple, minimum quantity, supplier product reference and preference rank, and optionally override supplier-level terms for that product (lead time, minimum order units, minimum order value).
- **FR-016**: Every cost on a link MUST carry provenance (ERP, import or manual), who set it and when; a manual cost MUST NOT silently replace an ERP cost, and a difference between them MUST be visible.
- **FR-017**: Users MUST always see and supply products by SKU; ERP ids MUST be used only in calls to the ERP and resolved from the SKU.
- **FR-018**: Buyers and admins MUST be able to assign a supplier to many products at once by filter or by SKU list, with a preview of effects and a per-row outcome.
- **FR-019**: A preferred supplier (and the buyer's ranking) MUST win a tie between otherwise equal offers; it MUST NOT override a clearly better total cost, lead time or constraint (minimum, schedule, deactivation), and each proposal line MUST state why its supplier was chosen and why the alternatives were not.

**Use by the optimizer and proposals**

- **FR-020**: Proposal generation MUST consume the terms version in force on the proposal date, including lead time, minimums, delivery schedule and cutoff, shipping thresholds, discounts and pack multiples, with product-level overrides taking precedence.
- **FR-021**: Each proposal line MUST record and show the supplier terms version and the cost source it used; a proposal MUST keep the versions it recorded when terms later change.
- **FR-022**: Shortfalls against minimums or thresholds MUST be shown on the proposal and handled by the existing allocation rules; they MUST NOT silently drop lines.

**ERP integrity and safety**

- **FR-023**: Supplier maintenance MUST NOT modify catalogue, stock, movements or ERP costs held from the ERP. The only ERP writes remain the two permitted by the constitution, performed only after buyer/admin review with a fresh second factor and always audited.
- **FR-024**: A supplier or product without a real ERP id MUST show "pending link in ERP", MUST NOT cause any ERP request, and its local terms MUST still drive proposals.
- **FR-025**: Supplier maintenance and proposal generation MUST keep working when the ERP is unavailable.

**Security, audit and privacy**

- **FR-026**: Every create, edit, deactivation, terms version, link change and cost change MUST be audited with who, when, before and after values, and be tamper-evident.
- **FR-027**: Change operations MUST enforce roles on the server regardless of the interface; viewers MUST NOT change anything; sensitive operations MUST require a recent second factor.
- **FR-028**: The system MUST refuse and record abusive input: oversized payloads, malformed numbers, out-of-range values, requests for a supplier or product the caller may not access, and replayed requests. Oversized payloads MUST be refused whatever content type the caller declares (FR-040).
- **FR-029**: Free-text ERP notes MUST NOT be stored, logged, displayed or used for decisions, apart from the existing in-memory handling during the permitted supplier-conditions write; only a "has note" indicator may be kept.

**Interface, data and cost**

- **FR-030**: All supplier screens, messages and errors MUST appear only in Spanish (es-ES) with EUR and Spanish date and number formats, with all texts coming from the interface text catalogue.
- **FR-031**: Money MUST be exact decimals (never floating point); every timestamp MUST be stored as UTC together with the original text where one was supplied.
- **FR-032**: Tests and demonstrations MUST use synthetic data only; the work MUST NOT add always-on services or raise the shared monthly cost target.
- **FR-033**: Changes to shared interface contracts MUST be negotiated with the integration agent before merging, and this feature MUST NOT edit files owned by another agent.
- **FR-034**: The system MUST obtain EUR reference rates for supplier currencies from the approved exchange-rate service (official central-bank reference rates only) at most once a day, store each rate with its publication date and fetch time, and use only stored rates when converting; proposal generation MUST NOT call the rate service.
- **FR-035**: A supplier whose currency is not EUR MUST be excluded from automatic allocation and listed for buyer review when no stored rate exists, the currency is not published by the ECB, or the stored rate is older than 7 days; the screen MUST show the rate used and its date wherever an EUR equivalent appears.
- **FR-036**: Outbound calls to the rate service MUST be limited to a single approved host, a fixed path and read-only requests, carry no personal or business data, and need no credentials.
- **FR-037**: A proposal containing a line for a supplier that has been deactivated MUST NOT be approvable until those lines are reallocated or removed.
- **FR-038**: Recording refused requests MUST NOT let any caller grow the audit trail without limit: requests with no valid sign-in are counted but not stored one by one, and an identical refusal (same caller, same target, same reason) repeated within one minute MUST be stored once with a repeat count; every refusal by a signed-in caller for a different caller, target or reason is still recorded (FR-028).
- **FR-039**: Recording a refusal MUST NOT delay other users' requests: a burst of refused requests leaves the time to save or read terms for other users within SC-011.
- **FR-040**: Every change request MUST be refused with a clear "payload too large" answer when its body exceeds the size limit, whatever content type or length declaration the caller uses, and the body MUST NOT be held in memory beyond that limit.
- **FR-041**: Reading the exchange-rate answer MUST stop once the maximum accepted size is reached, so an oversized or endless answer cannot use more memory than that limit; the stored rates stay unchanged and the failure is audited as any other rate-service failure.
- **FR-042**: When many refused requests arrive at the same moment, the audit trail MUST still hold exactly one entry per distinct caller, target and reason per minute, and no refusal that should be stored may be lost without a visible error; the counts of skipped refusals MUST stay accurate.
- **FR-043**: A failure in the exchange-rate refresh or its housekeeping (an unreachable service, a database error) MUST NOT stop any other background work of the service, in particular the delivery of change events to other services, and MUST be reported and audited.

### Key Entities *(include if feature involves data)*

- **Supplier**: Purchasing counterparty with commercial name, fiscal type, country, currency, payment terms, order channel, classification, active status, origin (platform, import, ERP) and ERP link state.
- **Terms version**: Immutable, effective-dated record of a supplier's commercial conditions (lead time, minimums in value and units, delivery weekdays, cutoff time, free-shipping threshold, delivery charge, discount tiers, payment terms, preferred, reliability, source, validity start and end), numbered per supplier, with author and timestamp.
- **Discount tier**: A threshold (by value or units) and a benefit (percentage or amount) within a terms version.
- **Product-supplier link**: A supplier's offer for a product by SKU: cost with provenance, pack multiple, minimum quantity, supplier reference, rank and optional product-level overrides.
- **Cost record**: A cost value with source (ERP, import, manual), author, timestamp and difference from the ERP value.
- **Audit entry**: Tamper-evident record of one change with actor, time, target, before/after and version.
- **Audit finding**: One row of the audit deliverable: capability, status, evidence, and the requirement and task that close it.
- **Proposal line terms reference**: The terms version and cost source recorded on a proposal line.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of in-scope capabilities appear in the audit with a status and evidence, and 100% of non-complete items map to a requirement and a task.
- **SC-002**: A buyer can create a supplier, set complete terms and link three products in under 10 minutes (automation proves the flow completes on the supplier screens without dead ends and records the action count for the PR; the 10 minutes themselves are confirmed by a person); all values read back identical after a reload and after a service restart.
- **SC-003**: In a test where two users save the same supplier's terms from the same starting version, exactly one save succeeds and the other is rejected with the newer version shown, in 100% of runs and with no data lost.
- **SC-004**: A terms version starting next month changes no proposal dated before the start and is applied to 100% of proposals dated on or after it.
- **SC-005**: For a set of at least 20 synthetic scenarios covering minimums, schedules and cutoffs, thresholds, discounts and overrides, proposal lines match the expected supplier, quantity and delivery date in 100% of cases, and every line names the terms version used.
- **SC-006**: Before and after any supplier maintenance operation, the ERP-owned data (catalogue, stock, movements, ERP costs) is identical in 100% of checks, and zero unauthorised ERP requests are made.
- **SC-007**: 100% of changes to suppliers, terms, links and costs have an audit entry, and 100% of tested abuse cases (wrong role, stale second factor, oversized or malformed input, cross-access, replay) are refused and recorded.
- **SC-008**: Every supplier screen and message is Spanish (es-ES) with EUR and Spanish formats, verified by an automated end-to-end run with zero untranslated or hard-coded texts.
- **SC-009**: Supplier maintenance and proposal generation complete successfully with the ERP unreachable.
- **SC-010**: The change adds no always-on service and no recurring cost beyond the shared monthly target; the rate job runs at most once a day and scales to zero.
- **SC-011**: Saving or reading a supplier's terms takes under 300 ms for 95% of requests with 50 stored versions.
- **SC-012**: 100% of non-EUR amounts used in an allocation have a stored rate no older than 7 days; every other case appears in the review list, none is silently converted or dropped.
- **SC-013**: 1,000 identical refused requests in one minute add at most one audit entry per distinct caller, target and reason, while the 95th-percentile time to save terms for other users stays under 300 ms; a 50 MB body of any content type is refused without exhausting memory.
- **SC-014**: With 50 identical refused requests sent at once, exactly one audit entry is stored and the skipped count is accurate; with the exchange-rate storage step forced to fail, change events are still delivered in the same pass in 100% of tested runs.

## Assumptions

- The service runs as a single replica; the once-a-minute limit on stored refusals and the once-a-day rate refresh are per process, and moving to several replicas needs shared storage for both (recorded as a limit, not built now).
- Work builds on features 002 and 004 on the latest main branch; existing supplier terms, link, bulk assignment, cost-resolution and audit code is reused wherever the audit shows it works.
- The roles are the existing ones (viewer, buyer, admin); buyers and admins maintain suppliers, viewers read only; releasing or overriding an ERP cost needs a fresh second factor.
- "MOQ value/units" means a minimum order value and a minimum order quantity; when both are set the stricter applies.
- The two ERP writes of the constitution (supplier cost and the supplier-conditions note block) keep their current rules and remain disabled until their prerequisites are verified; this feature adds none.
- Currencies other than EUR are kept per supplier and shown in their own currency. No exchange-rate rule exists today (audit item 19); rates come from Frankfurter (ECB reference rates, no key, daily), cached locally (research D3). Its data is provided as is, so converted amounts are for comparison and allocation, not accounting.
- "Minimum order units" is one concept stored under three names in the current code (supplier minimum quantity for delivery, product-level minimum units, cost-level minimum order quantity); the data model maps them.
- The spec is numbered 007 because 005 and 006 are already taken by parallel specs; the ticket's `specs/003-agent-04/` path is not used.
- Dependencies: the shared API contracts and integration are coordinated by Agent 00; the demonstration uses the Spanish interface backed by the real API, with synthetic fixtures.
- A single pull request delivers the audit, specs, implementation, tests and screenshots; no production deployment, merge to main, or real ERP write is part of this work.
