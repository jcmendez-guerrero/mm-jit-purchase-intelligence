# Feature Specification: Mundo Mascotix Intelligence — Inventory Intelligence & Weekly Purchasing Platform

**Feature Branch**: `001-mmi-purchase-intelligence`

**Created**: 2026-11-04

**Status**: Draft

**Input**: User description: "we need to build the system based on implementation plan docs/architecture/implementation-plan.md and the architecture (Confluence CDE page 1146881, Architecture Specification v1.0)"

## Context

Mundo Mascotix is a veterinary pharmacy and pet shop with roughly 1,000 product variants, less than six months of sales history, and weekly supplier ordering. Its ERP (Siweb360) remains the system of record. Today, purchasing decisions are made without a systematic view of demand, stock risk, expiry or supplier cost. This feature delivers an independent platform that reads ERP data, understands demand and stock risk, and produces explainable weekly purchase proposals that a human approves and exports. It is read-only toward the ERP except for one narrowly scoped, human-initiated action: updating a supplier's cost on a product after the buyer enters or confirms it.

Out of scope for this feature: grooming supplies (ordered on demand, never stocked), pet-treatment recurrence prediction (deferred, requires a privacy assessment), creating or changing purchases, stock, prices, invoices or any other ERP record (the only permitted ERP write is the supplier-cost update described in FR-040), and synchronisation of tickets, invoices, contacts, employees or accounting data.

## Clarifications

### Session 2026-11-04

- Q: Should purchase proposals be produced once for the whole company, or separately for each warehouse? → A: One company-wide proposal; demand and stock aggregated across warehouses, with a per-warehouse breakdown shown for information only.
- Q: Who may approve a proposal, and can one person hold both buyer and approver roles? → A: One person may hold both roles, but cannot approve a proposal they created or last edited; approval requires at least two active users.
- Q: What export format should the approved proposal use for placing supplier orders? → A: CSV and Excel exports are available, but the primary use is reading the approved proposal in the application: the buyer then places the order manually with each supplier (supplier ordering is not integrated). The system must therefore allocate lines to suppliers by considering unit cost, combined order cost, delivery time and minimum order value/quantity for delivery, and present the result grouped by supplier.
- Q: How much stockout risk is acceptable when setting safety stock, and should it differ by product type? → A: Target service level per segment: highest for products manually marked clinically critical, higher for ABC class A, lower for class C and sparse/slow items; the buyer can change the targets at any time, and changes apply to later proposals and are auditable.
- Q: How will the buyer load supplier price lists and order terms? → A: The system always holds a cost per supplier, reading it from the ERP first; if none exists the buyer enters it (checkbox: cost includes Recargo de Equivalencia or not; if net, the system calculates it using 1.4% for 10% VAT and 5.2% for 21% VAT products). ERP costs include Recargo. When the buyer enters a missing cost, or confirms an order with a different cost, the system updates the supplier cost in the ERP. This replaces the earlier read-only rule with one narrow, human-initiated write. File-based price-list import remains supported as an additional source.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trustworthy inventory and movement data (Priority: P1)

The data steward / owner needs an up-to-date, reconciled copy of catalogue, warehouses, stock levels, lots with expiry and stock movements from the ERP, collected safely and without ever changing anything in the ERP. This is the foundation: nothing downstream is trustworthy without it.

**Why this priority**: Every other capability depends on complete, correct, auditable source data. Early capture also starts accumulating history while the rest is being built.

**Independent Test**: Run the collection against a simulated ERP (synthetic data with realistic quirks) and verify the stored counts reconcile with the totals the ERP reports, that nothing outside the approved read operations and the single approved supplier-cost update is ever requested, and that bad records are quarantined rather than used.

**Acceptance Scenarios**:

1. **Given** a nightly collection window, **When** the collection runs, **Then** warehouses, products, variants with stock totals and new stock movements since the last checkpoint are stored, and record counts reconcile with the totals reported by the ERP.
2. **Given** a one-off historical backfill larger than a single night's request budget, **When** it runs, **Then** it resumes across several nights without duplicates or gaps and never exceeds this system's agreed share of the ERP request limit.
3. **Given** any attempt (by code, configuration or a faulty change) to call an ERP operation that modifies data other than the approved supplier-cost update, or a path/host outside the approved list, **When** the request is made, **Then** it is refused before leaving the system and a security signal is recorded.
4. **Given** a record with a malformed date, a missing warehouse, or a sale movement without a recognisable document reference, **When** it is imported, **Then** it is placed in a review list with the reason, excluded from downstream decisions, and not silently corrected.
5. **Given** a product that disappears from the ERP's active list after several consecutive collections, **When** the threshold is reached, **Then** it is marked discontinued and stops appearing in new proposals.
6. **Given** supplier tax identifiers and free-text notes in source data, **When** data is stored, **Then** those fields are discarded and only a "has note" indicator is kept.

---

### User Story 2 - Reliable demand picture per product (Priority: P1)

The buyer needs to see real customer demand per product, per day and per warehouse, derived from stock movements, with losses (expiry, damage, theft, unexplained write-offs) shown separately and never mistaken for sales.

**Why this priority**: Purchasing quality is bounded by demand quality. The business already decided that demand comes from stock movements, not tickets.

**Independent Test**: Load synthetic movements covering all reason types and verify the demand series equals customer shipments minus customer returns, that every other movement type appears only in its own series, and that days when stock was at or below zero are flagged as censored.

**Acceptance Scenarios**:

1. **Given** movements of every reason type, **When** demand is computed, **Then** demand equals sales shipments minus customer returns; transfers, adjustments, supplier flows, production, counts and initial stock are excluded and kept as separate series.
2. **Given** negative adjustments before the reason-cutover date (default 2026-09-19, configurable), **When** losses are classified, **Then** all are shown as "unclassified loss"; **given** adjustments after the cutover, **Then** expiry/damage/theft are trusted and negative adjustments with no reason are shown as "unspecified loss".
3. **Given** post-cutover losses, **When** the buyer views data quality, **Then** the share of negative adjustments lacking a structured reason is displayed as a staff-training signal.
4. **Given** a product that was out of stock for several days, **When** history is rebuilt, **Then** those days are marked as stockout-censored and not treated as zero demand.
5. **Given** a sales movement flagged for review, **When** it has not been confirmed, **Then** it is excluded from demand and visible in the review list.

---

### User Story 3 - Product classification and forecast eligibility (Priority: P2)

The buyer and owner need each product classified by value (ABC), variability (XYZ) and demand pattern (smooth, intermittent, lumpy, new, discontinued), with an honest indicator of whether enough reliable data exists to forecast it. Demand is very sparse (most products sell rarely, mostly one unit at a time), so the system must choose appropriate stocking policies per segment instead of over-promising forecasts.

**Why this priority**: Prevents misleading SKU-level forecasts and drives which replenishment policy applies to each product.

**Independent Test**: Run on synthetic catalogue with known demand profiles and verify each is classified correctly, backtests compare policies on stockout and overstock outcomes, and ineligible products are flagged rather than forecast.

**Acceptance Scenarios**:

1. **Given** the demand history, **When** classification runs, **Then** each product gets an ABC/XYZ segment and a demand-pattern label, visible with its rationale.
2. **Given** a product with too little or ambiguous history, **When** forecasts are generated, **Then** it is marked "not forecast-eligible" and falls back to a conservative min/max policy with the reason shown.
3. **Given** candidate policies, **When** backtests run on rolling historical windows, **Then** results are expressed in stockout and overstock cost terms, and a more complex method is adopted for a segment only where it shows a measurable gain.
4. **Given** a product manually marked clinically critical, **When** policies are applied, **Then** the marking is respected and never inferred automatically.

---

### User Story 4 - Supplier costs and terms with provenance (Priority: P2)

The buyer needs the current cost, lead time, minimum order and pack size for each product-supplier pair, with a clear indication of where each value came from, when it was last verified and whether it is stale.

**Why this priority**: Proposals are only as credible as their costs; the ERP provides partial data without timestamps, so provenance is essential.

**Independent Test**: Import costs from the ERP, a price-list file and manual entry; verify versions are retained, sources labelled, stale values flagged, and an abnormal cost jump blocks proposals until confirmed.

**Acceptance Scenarios**:

1. **Given** supplier costs from the ERP, a price-list file and manual entry, **When** they are stored, **Then** each is kept as an immutable, versioned record with source and verification time; the ERP import time counts as its verification time.
2. **Given** a cost older than the staleness threshold, **When** a proposal uses it, **Then** it is flagged as stale and the buyer can mark it verified.
3. **Given** a new cost that jumps abnormally versus the prior version, **When** it is imported, **Then** proposals using it are blocked until the buyer confirms it.
4. **Given** a product whose variants differ in pack size, **When** the buyer records a per-variant override, **Then** it takes precedence over the product-level ERP value.
5. **Given** last-paid cost history, **When** displayed, **Then** it is never presented as a guaranteed current offer.

---

### User Story 5 - Explainable weekly purchase proposal, approval and export (Priority: P1)

The buyer receives a weekly proposal of what to order from which supplier and how much, with a plain-language explanation for every line. The buyer can edit it, submit it, and a different authorised person approves it. The approved proposal is exported for ordering. The system never creates orders in the ERP; the only ERP update is the supplier cost, entered or confirmed by the buyer.

**Why this priority**: This is the end-user value of the whole platform and the definition of done: a buyer approves and exports a weekly proposal unaided.

**Independent Test**: With synthetic data, generate a proposal, edit lines, submit, approve with a different user, export, and verify the explanation, audit trail and separation of duties at every step.

**Acceptance Scenarios**:

1. **Given** current stock, demand, supplier terms and inbound orders, **When** the weekly proposal is generated, **Then** each line shows suggested quantity, supplier, cost and its source, forecast or policy used, safety stock, constraints applied (minimums, pack multiples, budget, shelf life, lead time), risk and confidence.
2. **Given** a proposal, **When** the buyer edits quantities or suppliers, **Then** changes are recorded with who and when, and constraints are re-validated.
3. **Given** a submitted proposal, **When** the person who created or last edited it tries to approve it, **Then** the action is refused; **when** a different authorised approver, freshly re-authenticated with a second factor, approves it, **then** the approval is recorded as a distinct auditable state change.
4. **Given** an approved proposal, **When** the buyer opens it, **Then** it is shown grouped by supplier (lines, quantities, costs, order total, expected delivery date) so the buyer can place each order manually with the supplier; **when** the buyer exports it, **then** CSV and Excel files are produced, the proposal is marked exported, and nothing is written to the ERP by the export.
4c. **Given** a product-supplier pair with no cost in the ERP, **When** the buyer enters a cost with "includes Recargo de Equivalencia" unchecked, **Then** the system shows the cost including Recargo (1.4% for 10% VAT, 5.2% for 21% VAT products) and, after the buyer reviews and confirms, updates the ERP with the Recargo-inclusive cost and records the change.
4d. **Given** a buyer confirming an order with a supplier at a cost different from the ERP's, **When** the buyer confirms, **Then** the actual quantities and costs are recorded and, after the buyer reviews the change, the ERP supplier cost is updated; if the ERP update fails it is retried visibly and flagged until it succeeds.
4e. **Given** a product-supplier pair for which the ERP holds no supplier record at all, **When** the buyer enters a cost, **Then** the cost is kept in the system, the pair is flagged "pending link in ERP" with no ERP request made, and the buyer is told to create the link in the ERP; once the link exists and the buyer re-releases the change, the cost is written.
4a. **Given** a product available from several suppliers, **When** the proposal is generated, **Then** lines are allocated to suppliers considering unit cost, the combined cost of each supplier's order, lead time against the protection horizon, and each supplier's minimum order value or quantity for delivery (including any free-delivery threshold and delivery charge); the explanation states why the supplier was chosen and what alternatives were compared.
4b. **Given** a supplier whose combined order falls below its minimum for delivery, **When** the proposal is generated, **Then** the system either tops the order up with items that are needed soon, moves lines to another supplier, or flags the shortfall for the buyer's decision, and shows the cost impact of each option.
5. **Given** a later stock receipt matching an exported order, **When** movements are collected, **Then** the receipt is matched to the order so inbound quantities are no longer double-counted.
6. **Given** products with expiring lots or on-hand stock already covering the protection horizon, **When** the proposal is generated, **Then** order quantities reflect that and the explanation says so.
7. **Given** the same inputs and rule versions, **When** a proposal is regenerated, **Then** the result is identical and the recorded inputs allow it to be reproduced.

---

### User Story 6 - Spanish-language insight and risk dashboard (Priority: P2)

Staff (viewer, buyer, approver, admin roles) use a Spanish web interface to see stock health, upcoming expiries, stockout risks, demand and loss data, data-quality issues and supplier costs, with a daily risk evaluation between weekly proposals.

**Why this priority**: Makes the data actionable and lets staff catch issues between weekly cycles.

**Independent Test**: Sign in as each role and verify permitted views/actions, Spanish text and es-ES formatting everywhere, and that risk alerts appear for synthetic stockout/expiry cases.

**Acceptance Scenarios**:

1. **Given** any screen, message, error, export header, notification or accessibility label, **When** displayed, **Then** it is in Spanish (es-ES) with EUR and Spanish date/number formats, and an automated check fails on any untranslated string.
2. **Given** each role, **When** a user attempts an action, **Then** viewers can only read, buyers can create and edit proposals, approvers can approve, and admins manage access; unauthorised attempts are refused and recorded.
3. **Given** a daily risk evaluation, **When** a product is at risk of stockout or has lots near expiry, **Then** it is surfaced on the dashboard with an explanation.
4. **Given** multiple warehouses including an "unassigned" bucket, **When** the buyer views stock and demand, **Then** both per-warehouse and company-wide views are available.

---

### User Story 7 - Safe, observable, budget-bounded operation (Priority: P2)

The owner and operator need confidence that the platform runs safely and within the shared monthly budget: failures are detected, quota and cost are monitored, secrets are protected, and recovery has been rehearsed. A shadow period proves the recommendations before the team relies on them.

**Why this priority**: The ERP token is shared and full-scope and the budget is shared with another application, so operational safeguards are a precondition for production use.

**Independent Test**: Run the platform locally with no cloud credentials and end-to-end synthetic data; trigger failures (rate-limit denials, duplicate or forged messages, failed syncs) and verify detection, alerts and safe behaviour.

**Acceptance Scenarios**:

1. **Given** a clean checkout and no cloud credentials, **When** the developer starts the complete system with one command, **Then** all components run against synthetic data and a simulated ERP exhibiting real quirks (three pagination styles, newest-first paging with inserts, rate-limit and auth errors, timezone-less timestamps).
2. **Given** the shared request limit, **When** collection runs, **Then** it stays within this system's agreed share, backs off on denials, and alerts when denials occur.
3. **Given** a failed collection, a stuck or poisoned message, or unexpected cost, **When** it happens, **Then** an alert is raised and no partial data is promoted.
4. **Given** a repeated or replayed internal message, **When** received, **Then** it is processed at most once in effect.
5. **Given** monthly spend approaching the shared budget, **When** 50%, 80% and 100% thresholds are crossed, **Then** alerts are sent.
6. **Given** a backup, **When** a restore drill is run, **Then** data is recovered within the recovery targets and the drill is recorded.
7. **Given** the 4–8 week shadow period, **When** it ends, **Then** proposals compared with actual buyer decisions and outcomes are available for review before go-live.

---

### Edge Cases

- ERP returns fewer pages than reported, or paging shifts while new movements arrive: the run uses a frozen end time, deduplicates by movement identifier, and reconciles counts.
- Movement timestamps lack a timezone: the original string and a normalised UTC value are both kept; a documented assumption is validated before production use.
- A product's variants share a supplier cost record but differ in pack size.
- A warehouse is missing on a movement: it is assigned to an explicit "unassigned" warehouse.
- History is shorter than expected (under six months): more products fall back to conservative policies.
- A stock reconstruction disagrees with a forward daily snapshot: the discrepancy is flagged and the affected products are not forecast-eligible.
- Purchase receipts reference orders in two styles (plain identifier and "Compra #n"): both are matched.
- The ERP token is rotated or expires: collection fails safely, alerts, and resumes after rotation without data loss.
- Product names or notes contain text that looks like instructions: treated strictly as data.
- Two buyers edit the same proposal at once: the second save is rejected or merged visibly, never silently overwritten.
- The cutover date for loss reasons is changed: history is reclassified consistently and the change is auditable.
- Approver unavailable: proposals stay pending; no self-approval path exists.

## Requirements *(mandatory)*

### Functional Requirements

**Data collection & integrity**

- **FR-001**: System MUST collect warehouses, products, variants with stock totals, lots/expiry levels, stock movements and supplier cost/lead-time/minimum-order data from the ERP on a recurring schedule, plus a resumable one-off movement backfill.
- **FR-002**: System MUST only perform read operations against an approved, closed list of ERP paths on the approved ERP host, plus the single supplier-cost update permitted by FR-040; any other request MUST be refused before it is sent and recorded as a security event.
- **FR-003**: System MUST keep its ERP request usage within a configured share of the shared limit, run heavy collection in a night window, and back off and alert on denials.
- **FR-004**: System MUST checkpoint progress, deduplicate records, and reconcile stored counts with ERP-reported totals for every run.
- **FR-005**: System MUST quarantine malformed or ambiguous records (invalid dates, missing references, sale movements without a document reference) in a review list with reasons, and exclude them from decisions until resolved.
- **FR-006**: System MUST mark products absent from the ERP's active list after a configurable number of consecutive collections as discontinued.
- **FR-007**: System MUST discard supplier tax identifiers and free-text notes before storage (keeping only a "has note" indicator) and MUST NOT collect tickets, invoices, contacts, employees, time tracking or accounting data.
- **FR-008**: System MUST retain raw source payloads (after field removal) immutably, with bounded retention (expired payloads are deleted automatically on a documented schedule) and restricted access.
- **FR-009**: System MUST key all products by the ERP's variant identifier, treating SKU codes as attributes only.

**Demand**

- **FR-010**: System MUST compute demand per variant, day and warehouse as customer sales shipments minus customer returns, and keep all other movement types as separate series.
- **FR-011**: System MUST classify losses using a configurable reason-cutover date (default 2026-09-19): before it, negative adjustments are "unclassified loss"; after it, expiry/damage/theft are trusted and reasonless negative adjustments are "unspecified loss". Losses MUST NOT count as demand.
- **FR-012**: System MUST show the share of post-cutover negative adjustments lacking a structured reason as a data-quality metric.
- **FR-013**: System MUST reconstruct daily on-hand history and mark days at or below zero stock as censored demand.
- **FR-014**: System MUST NOT parse or infer decisions from free-text notes or product names.

**Classification & forecasting**

- **FR-015**: System MUST classify each product by ABC, XYZ and demand pattern, and record explicit, manually set clinical-criticality and expiry policies.
- **FR-016**: System MUST determine per product whether it is forecast-eligible and MUST NOT publish product-level forecasts from ambiguous or insufficient data.
- **FR-017**: System MUST evaluate stocking and forecasting methods by rolling-window backtests judged on stockout and overstock outcomes, version forecast runs, and express forecast uncertainty.

**Supplier costs**

- **FR-018**: System MUST store supplier costs as immutable versioned records with source (ERP, price-list file, manual), verification time, currency, pack size, lead time and minimum order, and MUST store supplier-level terms (minimum order value, minimum quantity for delivery, free-delivery threshold, delivery charge, order days and delivery schedule) maintained by the buyer.
- **FR-019**: System MUST flag stale costs by a configurable rule, let the buyer mark costs verified, and block proposals that use a cost with an unconfirmed abnormal jump.
- **FR-020**: System MUST NOT present last-paid or historical cost as a current supplier offer.
- **FR-040**: System MUST update the supplier cost in the ERP (the only permitted ERP write) in exactly two cases, each initiated by a buyer action and shown for review before sending, with the buyer re-confirming through fresh multi-factor authentication before it is released: (a) the ERP has a product-supplier record with no cost and the buyer enters one (if the ERP holds no record linking that product and supplier, the system MUST keep the cost locally, flag the pair "pending link in ERP" for the buyer to create in the ERP, and MUST NOT attempt to create the link unless the ERP behaviour has been verified and the decision recorded); (b) the buyer confirms an order with a supplier and the cost the buyer provides for that order differs from the cost held in the ERP. The value written MUST be the cost including Recargo de Equivalencia, matching how the ERP holds it. Each write MUST record who, when, previous and new value and outcome; a failed write MUST be retried visibly and never silently dropped; the write MUST be limited to the supplier-cost operation, changing only the cost value and leaving every other ERP field on the record as it was read immediately before the write, and its identity and permissions MUST be separate from the read-only collection.
- **FR-041**: System MUST hold a cost for every active product-supplier pair it proposes to order from. It MUST first use the cost read from the ERP, and if none exists MUST require the buyer to enter one before the pair can be used in a proposal.
- **FR-042**: When the buyer enters a cost, System MUST provide a checkbox stating whether the entered cost already includes Recargo de Equivalencia. If it does not (net cost), System MUST calculate and show the cost including Recargo using the product's VAT rate: 1.4% for products at 10% VAT and 5.2% for products at 21% VAT. Costs read from the ERP are treated as already including Recargo; the net cost can be derived from them for comparison and display.
- **FR-043**: System MUST let the buyer confirm, per supplier, that an order has been placed (a step after approval), recording the actual quantities and costs agreed; confirmed orders replace proposal quantities as the inbound quantities used by later proposals.

**Proposals & approval**

- **FR-021**: System MUST generate a single company-wide weekly purchase proposal (demand and stock aggregated across all warehouses, with a per-warehouse breakdown shown for information only, not as separate orders), using a protection horizon of seven days plus supplier lead time, accounting for available stock, inbound orders arriving in time, expiring lots, safety stock, and the constraints of cost, minimum order, pack multiple, budget, shelf life and manual overrides.
- **FR-022**: System MUST explain every proposal line: quantity, supplier, cost and source, forecast or policy used, safety stock, constraints, risk and confidence.
- **FR-023**: Users with the buyer role MUST be able to edit proposal lines, with every change recorded and constraints re-validated.
- **FR-024**: System MUST require approval by an authorised user who neither created nor last edited the proposal (one person may hold both buyer and approver roles, but never act as both on the same proposal; any edit after submission resets approval eligibility), with fresh multi-factor re-authentication, recorded as a distinct state transition in a tamper-evident audit trail.
- **FR-025**: System MUST present approved proposals grouped by supplier for manual ordering, offer CSV and Excel exports, and MUST NOT send orders to suppliers or create, change or delete any ERP record other than the supplier-cost update in FR-040.
- **FR-038**: System MUST allocate proposal lines among suppliers by jointly considering unit cost, each supplier order's combined cost, lead time, minimum order value/quantity for delivery, free-delivery thresholds and delivery charges, pack multiples and budget; when a supplier minimum is not met it MUST propose top-up, reallocation or a flagged shortfall with cost impact; and every allocation MUST be explained and overridable by the buyer.
- **FR-039**: System MUST set safety stock from a target service level per segment (highest for clinically critical products, higher for ABC class A, lower for class C and sparse/slow items), with sensible defaults; authorised buyers MUST be able to change segment targets, and per-product overrides, at any time; each change MUST be recorded (who, when, old and new value), apply to subsequently generated proposals only, and be shown in the explanation of affected lines.
- **FR-026**: System MUST match later stock receipts to exported orders so inbound quantities are accurate.
- **FR-027**: System MUST record the inputs, rule and model versions behind each proposal so it can be reproduced.

**Interface, access & localisation**

- **FR-028**: All user-facing content MUST be in Spanish (es-ES) by default with EUR and Spanish date/number formats, while storing UTC timestamps and ISO currency codes internally; no hard-coded untranslated strings, enforced by automated tests.
- **FR-029**: System MUST enforce viewer, buyer, approver and admin roles on every action, authenticate users with multi-factor sign-in, and refuse and record unauthorised attempts. Admins MUST be able to assign and revoke roles (each change audited), and the system MUST refuse to put a proposal into approval when fewer than two active users could satisfy the separation-of-duties rule, telling the buyer why.
- **FR-030**: System MUST provide dashboards for stock health, stockout and expiry risk (evaluated daily), demand, losses, data quality, supplier costs and import review lists, with per-warehouse and company-wide views.

**Operations, security & cost**

- **FR-031**: System MUST run entirely locally from a single command without cloud credentials, using synthetic data and a simulated ERP that reproduces real-world quirks.
- **FR-032**: System MUST never commit or use real exports, raw ERP responses, credentials, personal data or real commercial records as test fixtures; secret scanning MUST run on every change.
- **FR-033**: Internal asynchronous messages MUST be authenticated, schema-validated, deduplicated, retried with bounded backoff, and routed to a poison queue with an alert on repeated failure.
- **FR-034**: Each component MUST own its data and expose it only through versioned, tested contracts; no component may read another's data store directly.
- **FR-035**: System MUST emit operational signals (sync freshness, queue age, request-quota use, denials, failed runs, cost) without logging secrets or personal data, and alert on failures, poison messages, unexpected cost and suspicious approvals.
- **FR-036**: System MUST operate within the shared monthly budget by reusing existing shared platform resources, scaling to zero when idle, capping parallelism, and alerting at 50%, 80% and 100% of the shared total.
- **FR-037**: System MUST support backup and a rehearsed restore, a shadow period of 4–8 weeks, and operational runbooks before production use.

### Key Entities

- **Product / Variant**: A catalogue item and its sellable variants, keyed by the ERP variant identifier, with status (active/discontinued), criticality and expiry policy.
- **Warehouse**: A stock location, including an explicit "unassigned" bucket.
- **Stock Snapshot / Lot**: Point-in-time stock per variant and warehouse, with batch and expiry detail.
- **Stock Movement**: A signed quantity change with reason, reference, lot, expiry and cost; classified as demand, loss or other flow.
- **Demand Series**: Per variant, day and warehouse customer demand, with censoring flags and separate loss series.
- **Import Error / Review Item**: A quarantined record with reason and resolution status.
- **Sync Run / Checkpoint**: A collection execution, its progress marker, counts and reconciliation outcome.
- **Segment & Policy**: ABC/XYZ/demand-pattern classification, forecast-eligibility, stocking policy and target service level per product (segment default with optional per-product override, editable at any time with change history).
- **Forecast Run / Backtest Result**: Versioned forecast outputs, uncertainty and economic evaluation.
- **Supplier**: A vendor (no tax identifiers stored) with order-level terms: minimum order value, minimum quantity for delivery, free-delivery threshold, delivery charge, order days and delivery schedule.
- **Supplier Cost**: Versioned per product-supplier (and optional variant override) cost with source, verification time, lead time, minimum order, pack size and staleness status.
- **Inbound Order**: A per-supplier order derived from an approved proposal and placed manually by the buyer, later matched to receipts.
- **Purchase Proposal / Proposal Line**: A weekly recommendation with explanation, constraints, inputs used and lifecycle state (draft, submitted, approved, exported).
- **Approval / Audit Event**: A tamper-evident record of who did what and when, including separation-of-duties checks.
- **User / Role**: A person with viewer, buyer, approver or admin permissions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A buyer can review, edit, obtain approval for and export a weekly purchase proposal unaided (no developer help) in under 30 minutes of active work.
- **SC-002**: 100% of proposal lines show a complete explanation (quantity, supplier, cost source, policy/forecast, constraints, risk, confidence).
- **SC-003**: Zero ERP data-modifying requests other than the buyer-initiated supplier-cost update ever reach the ERP; 100% of disallowed request attempts in tests are refused and recorded, and 100% of permitted cost updates have a matching buyer action and audit record.
- **SC-004**: Stored record counts reconcile with ERP-reported totals for 100% of collection runs after 7 consecutive clean nights, and for 14 consecutive days before integration is declared complete.
- **SC-005**: The system's ERP request usage never exceeds its agreed share of the shared hourly limit, and the other application experiences no quota denials attributable to this system.
- **SC-006**: Within the shadow period, proposals that follow the system's recommendations show fewer stockouts and no more overstock cost than the buyer's actual decisions on the same products, as reviewed by the owner before go-live.
- **SC-007**: No product-level forecast is shown for any product marked not forecast-eligible; 100% of quarantined records are excluded from demand until resolved.
- **SC-008**: 100% of user-facing screens, messages and exports are in Spanish, verified by automated checks.
- **SC-009**: No proposal can be approved by its creator, and 100% of approvals carry a verified re-authentication and an audit record.
- **SC-010**: A new developer can start the full system locally with one command, with no cloud credentials, and run the complete test suite successfully on the first attempt.
- **SC-011**: Combined monthly spend of this system and the existing application stays within the EUR 120 target; alerts fire at 50%, 80% and 100%.
- **SC-012**: A backup restore drill completes within the recovery targets (data loss ≤ 24 h for regenerable analytics, restoration within 4–8 h) before production go-live.
- **SC-013**: Collection or processing failures are detected and alerted within one hour of occurring.

## Assumptions

- Raw source payloads are kept for 90 days by default (configurable) and then deleted automatically; derived data is retained separately under its own rules.

- The ERP (Siweb360) remains the system of record; this platform is read-only toward it except for the supplier-cost update in FR-040 (decided in clarification). The ERP's documented supplier-cost update operates per product, not per variant; if variant-level costs in this system differ for one product, the buyer is warned and chooses which value is written.
- A single full-scope ERP token shared with another Mundo Mascotix application exists; read-only behaviour is enforced on this system's side, and an agreed request-share (proposed ≤ 500 requests/hour, night window) is still to be confirmed with the other application.
- Demand comes from stock movements, not tickets; grooming supplies are out of scope.
- Behaviours of the real ERP (movement timezone, document reference types for ticket sales, history depth, page sizes, rate-limit responses) are unverified and treated as assumptions until a short live check (Gate 0) confirms them; the design must tolerate the alternatives.
- Reason-cutover date defaults to 2026-09-19 until the exact date is confirmed.
- Proposals are generated at company level with per-warehouse stock and demand visibility (decided in clarification); per-warehouse proposals are not part of this release.
- Supplier pack sizes, discounts and price lists beyond the ERP are maintained via price-list file import and manual entry; the ERP stores supplier cost including Recargo de Equivalencia (1.4% for 10% VAT products, 5.2% for 21% VAT products, as stated by the business). Other VAT rates (e.g. 4%) and the source of each product's VAT rate are not yet specified; products with an unknown VAT rate cannot have a net cost converted and require the buyer to enter the cost including Recargo. Further landed-cost tax treatment is pending accountant confirmation.
- Roles are assigned by admins; a person may hold both buyer and approver roles (decided in clarification). At least two active users with approval ability are needed for any proposal to be approved.
- The users are a small team (a few staff) using modern desktop browsers; mobile support is out of scope for the first release.
- Existing shared infrastructure (database server, container environment, registry, secrets store, monitoring) is reused where capacity allows.
- Multi-supplier allocation by cost, combined order cost, delivery time and delivery minimums is in scope for this release (decided in clarification). Supplier order terms are entered by the buyer, as the ERP does not hold them. Orders are placed manually with suppliers; no supplier integration or ordering automation is included.
- Pet-treatment recurrence and optional ERP purchase drafts are deferred to a later release.
- Delivery proceeds in phases (verify & decide → foundation → early capture → integration → demand → procurement MVP → production with shadow period); user stories above can be delivered and demonstrated independently in priority order.
