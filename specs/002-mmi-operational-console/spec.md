# Feature Specification: MMI 002 — Operational Console, Analytics, Supplier Configuration and Predictive Seed Import

**Feature Branch**: `claude/mmi-002-operational-console-ibqo4g`

**Created**: 2026-11-05

**Status**: Draft — for human review (no implementation before approval)

**Input**: Jira KAN-34; Confluence "MMI 002 — Operational Console…" (page 1998849), architecture baseline (1146881), verified implementation status (1802241); existing baseline PR #1 and `specs/001-mmi-purchase-intelligence/`.

## Context

Feature 001 delivered the backend pipeline (Siweb connector, inventory, demand, forecasting, supplier costs, proposals, approvals, cost writer) and a basic web app. The buyer still cannot run procurement without developer help: the dashboard shows risk counts and a table only, supplier commercial terms and policies cannot be edited from the interface, there is no way to load initial predictive data (only about 1,640 movements, all in 2026, exist, so seasonal forecasting is not yet possible), and user roles are not durable, which blocks real approvals.

This feature turns MMI into a configurable operational console. The ERP (Siweb360) stays the source of truth for catalogue, stock, movements and ERP supplier costs. MMI owns versioned operational configuration: supplier commercial terms, policies, forecasting assumptions, predictive seed datasets, scenarios and approvals. Imported estimates never overwrite ERP facts and never masquerade as ERP movements.

Out of scope: any ERP write other than the existing buyer-released, fresh-MFA supplier-cost update; sending orders to suppliers; creating ERP product-supplier links; production deployment or merge to main (separate, explicitly authorised steps); grooming supplies and treatment-recurrence prediction (as in 001).

### Existing baseline and gap inventory (code-backed, against the merged PR #1 state)

| Capability | State | Notes |
|---|---|---|
| Procurement: supplier order terms (min value/qty, free-delivery threshold, delivery charge, order weekdays, schedule), versioned and audited | **Exists** (backend; `PUT /suppliers/{id}/terms`) | Missing: lead time, pack multiples, discounts, payment terms, preference, validity windows, reliability, disable; product-supplier overrides; any UI |
| Procurement: cost versions, recargo, stale/jump rules, cost-write release | **Exists** | Reuse unchanged; the only ERP write stays here |
| Procurement: proposals, CP-SAT allocation, explanations, approvals, separation of duties, fresh MFA, order confirmation, exports | **Exists** | Missing: scenarios/what-if, budget caps as configuration, cost sensitivity, scenario comparison |
| Procurement: service levels with history; user-role mirror endpoint | **Exists** (service levels, `PUT /internal/users/{id}/roles`) | BFF never calls the mirror; submit-for-approval finds no approvers in the real stack |
| BFF: sessions, CSRF, RBAC checks, role admin | **Partial** | Role registry is in memory (lost on restart); not mirrored; code from the second agent (commit 3a664a0) not independently reviewed |
| Inventory: demand series, ABC/XYZ, risk, quality, exports | **Exists** (API: risk, variants, series/stock export) | Missing: aggregate dashboard endpoints (value, coverage, trend, accuracy), filter option lists (warehouses, categories, suppliers) |
| Forecast: runs, registry, backtests, policies by segment | **Exists** (worker/job, `GET /forecasts/latest`) | Missing: editable forecast parameters, seed datasets, import pipeline, run listing, accuracy API |
| Web app: dashboard, config, costs, proposals, quality screens | **Partial** | Dashboard has no charts and a hard-coded warehouse list; config only shows service-level history and edits roles; costs read-only; no terms editor, policy CRUD, import wizard or scenario UI |
| Spanish-only i18n, EUR/date formats | **Exists** (es-ES) | Must extend to all new screens, exports, errors, templates |
| Contracts (JSON Schema → generated types), per-service schemas and migrations | **Exists** | Every new API and event starts as a contract |
| Open from 001 | 001-T129 (Gate 0 V6/V7, 429), 001-T130 (threat model), 001-T133 (cost review), 001-T152 (compose smoke test) | Phase 0 blockers listed in FR-001 to FR-004 |

## Clarifications

### Session 2026-11-06

- Q: Which chart technology does the dashboard use? → A: Recharts (SVG) inside the existing React SPA, each chart with a data-table alternative, keyboard focus and a text summary. Python dashboard servers (Streamlit, Dash, HoloViz) were assessed and rejected for the buyer console because they add a second web stack, a second login and an always-on container. If richer interactions are needed later, Plotly.js inside the SPA is the contained alternative.
- Q: Is the constitution amendment v1.2.0 (median value, margin check, admin override inside the single permitted write) accepted as drafted? → A: Yes. ADR-006 and the implementation plan are updated to match; the formal ratification date is set when the amendment is merged.
- Q: What margin cap applies to a product whose cost is exactly EUR 50.00? → A: 20 %. A Recargo-inclusive cost below EUR 50.00 has the 30 % cap; EUR 50.00 and above has the 20 % cap.
- Q: May seed data make a "new" product forecastable, and under what condition? → A: Yes, only when the product's sole reason for being ineligible is "new", the seed rows cover at least half of the days in their span, and the combined history (seed plus actual) reaches the 56-day minimum. Actual ERP demand always prevails on any day it covers. The forecast is flagged `seed_used` and the proposal line says so.
- Q: Does the seed import run inside the upload request or as a background job? → A: Hybrid. A file of up to 10,000 rows is parsed and validated inside the request. A larger one (up to the 50,000-row cap) is queued for the worker; the buyer is told at once that it has been sent to the background, and an import status section lists every import with its stage (queued, parsing, validating, ready, failed), timings and any error, so the buyer can check it later. Re-running a stage is safe (idempotent).
- Q: What does the dashboard "category" filter mean? → A: Both. The demand group (ABC/XYZ plus the manual clinical-critical flag, computed by MMI) is available now. The ERP product family is a second filter that appears only once the connector, inventory schema and contracts carry it and it has been synchronised; until then it is absent rather than empty or hard-coded.
- Q: Which price is the selling price (PVP) for the margin check? → A: The variant price held in the ERP and synchronised into inventory (`variants.price`, the catalogue selling price in EUR). The price on stock movements is not used. A product-level cost update is checked against the lowest PVP among the product's variants, because that gives the tightest margin. A variant with no price is skipped; a product with no variant price has an unavailable margin, which blocks the release as in the edge case below. The ERP can hold the price with or without VAT depending on the product; the aim is for the variant price to be the net one, so all variant prices are treated as net of VAT and no VAT conversion is applied.
- Q: Which service is the only place where a person edits service levels? → A: Procurement (policy sets). Inventory keeps its computed defaults (critical 99 %, ABC 97/95/90 %, sparse 85 %) as a read-only fallback and its history stays readable. The inventory edit route and the BFF `PUT /config/service-levels` are removed; the existing inventory history may be imported once into policy sets.
- Q: Does the variant price include VAT? → A: It is treated as net of VAT for every product (the ERP may hold either form, the target is net), so PVP is used as is and a missing VAT rate never makes the margin unavailable. The margin is unavailable only when a product has no variant price at all, and then the release is blocked as in the edge case. An operator checks what the ERP actually returns for a sample of variants (net or gross) on the real system and records the result before go-live; the system does not read the real ERP from this repository.
- Q: How old can the selling price (PVP) be before the margin check treats it as stale? → A: More than 7 days since the variant price was last confirmed by a successful sync; the release is then blocked like a missing price (admin override still possible) and the price age is shown.
- Q: Should the old inventory service-level history be copied once into the procurement policy sets? → A: No. Policy sets start empty; inventory values stay read-only history so earlier proposals reproduce, and the computed defaults apply until a buyer sets a value.
- Q: Are ADR-018 (configuration ownership) and ADR-020 (seed provenance and activation) accepted? → A: Yes, accepted by the owner on 2026-11-07, including the accepted risk of no paid malware scanning. ADR-019 stays proposed.

### Session 2026-11-05 (resolved autonomously from the authoritative sources, for reviewer confirmation)

- Q: Where do supplier commercial terms that the ERP cannot hold (lead time, delivery schedule, pack multiples, discounts) live? → A: Locally in MMI as effective-dated versions; the ERP is never written for them (verified: lead time and minimum order are not writable through the ERP supplier PUT).
- Q: Which value wins when ERP, approved local override and imported estimate disagree? → A: Per field, a verified ERP fact is used for ERP-owned fields (stock, movements, ERP cost); an approved local override wins for MMI-owned fields; an uploaded estimate is used only where no actual or approved value exists and is always labelled. Conflicts are shown to the buyer.
- Q: At what unit cost is stock valued on the dashboard ("inventory value")? → A: At acquisition cost, not at the ERP movement price. The ERP movement price is the retail price (PVP), and the ERP holds only one unit cost per supplier although lots of one product can have different acquisition costs. MMI therefore keeps its own per-lot acquisition-cost record. The median of the lot acquisition costs is the value suggested to the buyer for the supplier-cost update (still reviewed by the buyer, released with fresh MFA, and audited, as in 001).
- Q: Where does MMI get the acquisition cost of each lot? → A: Automatically from the cost on the confirmed supplier order, attached to the lots when the receipt is matched. When the product arrives the buyer can update the lot cost; every change is audited. There is no separate lot-cost file import.
- Q: Which value goes to the ERP in the supplier-cost update? → A: Always the median of the acquisition costs of the lots in stock for that product-supplier pair (not a buyer-typed value; the buyer changes it only by correcting lot costs). The update is also subject to the margin rules below. Rules as stated by the owner (their exact application is pending the next clarification): products with cost below EUR 50 have a margin of up to 30%; products with cost above EUR 50 up to 20%; if the margin after the new cost is above 30% but was already 30% or more, it is left as it is (this covers purchase offers that raise margin); if the margin is below 30% and increases, it may increase up to 30%; the minimum margin is 15%.
- Q: When the median cost would put a product's margin outside the limits, what does the system do at the cost update? → A: A margin below 15% blocks the release unless an admin overrides it with a recorded reason. The cap rules (30% below EUR 50 cost, 20% above, "leave as is" when the margin was already at or above the cap) only flag and explain. The admin may set a cost value of their own judgement instead of the median, supported by explanatory tips in the screen (resulting margin, the rule that applies, the cost that gives exactly the minimum and the cap, and the lots behind the median); the override is recorded with the median, the chosen value and the reason.
- Q: How is the margin calculated for these rules? → A: By the business pricing formula PVP = (cost + Recargo) ÷ (1 − margin), so margin = 1 − (cost + Recargo) ÷ PVP, where cost + Recargo is the Recargo-inclusive cost (the form the ERP holds and the median uses) and PVP is the variant selling price held in the ERP (see Session 2026-11-06). The cost that gives a target margin is PVP × (1 − margin); the screen tips use this. Whether the ERP PVP includes VAT is verified before build (T066), and the formula is applied as stated.
- Q: How is "coverage days" calculated? → A: Stock on hand ÷ average daily forecast demand over the next 30 days; for a product that is not forecast-eligible, ÷ its average actual daily demand over the last 90 days. The dashboard labels which basis was used. Products with zero demand show "sin demanda" instead of a number.
- Q: When is the cost-update median computed, and how, including when there are no lots? → A (analysis remediation, recommendations accepted by the owner): a request is created when goods are received and matched to a confirmed order, or when the buyer enters a cost for a pair with no ERP cost. The value is the plain median of the Recargo-inclusive acquisition costs of the entries with remaining stock (mean of the two middle values when even, exact decimals, rounded half-up to whole cents). With no ERP cost and no lot, the buyer-entered cost is recorded as the opening entry and is the value; with no entry in stock, no request is created.
- Q: May the admin who sets a cost override also release that cost update to the ERP? → A: No. The admin who sets an override cannot release it; a different buyer must release it with fresh MFA, and the system refuses a release by the person who set the override.
- Q (owner statement, 2026-11-05): The system must constantly identify products by category and recommend a safe stock for each category; the value can be overridden under approval. For example, a product sold once a month that is lost if not in the store has a safe stock of 1 and at least 1 must be bought each month without anyone requesting it. → A: Recorded as FR-045 to FR-048. Categories are the existing ABC, XYZ, demand-pattern and manual clinical-criticality segments, re-evaluated on every demand update. The recommended safety stock follows FR-039. A per-product override of the recommendation needs approval by an authorised approver who is not the requester. An "always stocked" product carries a minimum stock floor and is replenished through the normal weekly proposal, which stays human-approved. The approval rule is decided in the next entry.
- Q: How strict is the approval of a safety-stock override? → A: Approval by any user with the approver role who is not the requester. No extra fresh MFA beyond the normal multi-factor sign-in.
- Q: How does procurement learn the remaining stock per lot for the median? → A: By an on-demand lookup. When it builds a cost-update request, procurement asks the inventory service for the lots in stock for that product-supplier pair, using an authenticated, audience-scoped service identity, and stores the lots used (with their quantities at that moment) with the request. If inventory is unavailable the request fails visibly and is retried; no stock copy is kept in procurement.
- Q: Which role may activate a predictive dataset and change policies? → A: Buyer or admin may upload, map and validate; activation and rollback need buyer-or-admin confirmation with an audit record; approving purchase proposals remains the approver role.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trustworthy approvals and durable access control (Priority: P1)

Before any operational screen is relied upon, the owner needs user roles to survive restarts and to be recognised by the purchasing side, so that a real proposal can be submitted, approved by an eligible different person with a fresh second factor, and survive a restart of the front-end orchestration layer.

**Why this priority**: Without it, submit-for-approval finds no approvers in the real deployment; every other story ends in a proposal that cannot be approved.

**Independent Test**: Start the full stack with synthetic users, assign roles, restart the orchestration layer, and run a proposal from draft to approved with two distinct users.

**Acceptance Scenarios**:

1. **Given** an admin assigns roles to a user, **When** the orchestration layer restarts, **Then** the assignments are still in force and the purchasing side lists the same eligible approvers.
2. **Given** only one active user holds the approver role who is also the proposal's creator, **When** the proposal is submitted, **Then** submission is refused with a Spanish explanation that two eligible people are required.
3. **Given** a submitted proposal, **When** its creator or last editor tries to approve, **Then** it is refused; **when** a different approver with a second factor verified in the last 5 minutes approves, **then** approval succeeds and is audited; **when** the second factor is older than 5 minutes, **then** approval is refused until re-verified.
4. **Given** the web and orchestration code that has not yet had an independent review, **When** a security review is completed, **Then** its findings are resolved or recorded as accepted risks before operational UI ships.
5. **Given** a role change, **When** it is saved, **Then** an audit entry records who, when, previous and new roles, and the change is mirrored to the purchasing side, with failures visible and retried.

---

### User Story 2 - Analytical dashboard with real data (Priority: P1)

A buyer or owner opens the dashboard and sees, from live data, business KPIs and interactive charts: inventory value, coverage days, stockout and expiry risk, proposed purchase spend, demand versus forecast with uncertainty, ABC/XYZ distribution, forecast accuracy and data-quality indicators. Filters (date range, category, supplier, warehouse) come from live data and every figure drills down to the product and supplier.

**Why this priority**: It is the main daily-use screen and the clearest proof that the console is driven by real data rather than a mirror of the ERP.

**Independent Test**: Load synthetic data, open the dashboard in each state (loading, populated, empty, failed) and verify values against known totals, filter effects and drill-downs, all in Spanish.

**Acceptance Scenarios**:

1. **Given** synthetic data with known totals, **When** the dashboard loads, **Then** at least four business KPIs and at least five distinct visualisations are shown with values equal to the known totals, Spanish labels, EUR and Spanish date/number formats, and a "last updated" timestamp.
2. **Given** the warehouses, categories and suppliers available in the data, **When** the buyer opens the filters, **Then** the options come from live data (no hard-coded warehouse), and applying them updates every KPI and chart consistently.
3. **Given** any chart element, **When** the buyer selects it, **Then** a drill-down shows the contributing products or suppliers and links to the product or supplier detail.
4. **Given** a product detail, **When** opened, **Then** actual demand, forecast with uncertainty, stock, risk reasons and the data used are shown, with actual ERP movements visually separate from imported estimates and manual forecasts.
5. **Given** no data, a failed source or stale data, **When** the dashboard loads, **Then** a clear Spanish empty, error or stale-data state appears instead of zeros or blank charts.
6. **Given** the company-wide proposal is canonical, **When** the warehouse filter is used, **Then** the per-warehouse view is labelled informational.
7. **Given** keyboard-only use or a screen reader, **When** charts are navigated, **Then** every chart has an accessible text or table alternative and meets accessibility checks.

---

### User Story 3 - Supplier and product-supplier commercial terms (Priority: P1)

The buyer maintains, without developer help, each supplier's commercial conditions and product-specific overrides: lead time, delivery weekdays and order cut-off, minimum order by units or value, free-shipping threshold, shipping cost, pack multiples, discounts, payment terms, preferred supplier, validity windows, reliability and manual disable. Each change is an effective-dated version with audit and a visible source (ERP, import or manual).

**Why this priority**: Supplier conditions drive allocation; today only part of them exist and none can be edited in the interface.

**Independent Test**: Edit terms for a synthetic supplier and one product override, reload, and generate a proposal; verify persistence, version history, audit and that the allocation reflects the new terms. Verify the ERP is untouched.

**Acceptance Scenarios**:

1. **Given** a supplier, **When** the buyer edits any supported term and saves, **Then** a new version is stored with effective date, author and source badge, earlier versions remain viewable, and the change is audited.
2. **Given** a product-supplier override (for example a different pack multiple or lead time), **When** saved, **Then** it takes precedence over the supplier-level value for that product only, and the precedence is shown.
3. **Given** invalid input (negative amounts, free-shipping threshold below minimum order, overlapping validity windows, impossible weekdays), **When** saving, **Then** it is refused with a specific Spanish error and nothing is stored.
4. **Given** two users edit the same record, **When** the second saves on stale data, **Then** the save is rejected with a conflict message showing the newer version.
5. **Given** a supplier is manually disabled or a term has expired, **When** the next proposal is generated, **Then** that supplier or term is not used, and the explanation says so.
6. **Given** any term change, **When** saved, **Then** no request is sent to the ERP; the existing buyer-released cost update is the only ERP write.
7. **Given** an ERP-sourced value and a local override disagree, **When** shown, **Then** both are visible with the winning value and a conflict indicator.

---

### User Story 4 - Editable inventory, replenishment and forecasting policies (Priority: P2)

The owner or buyer edits, in the interface, service levels by segment and by product, safety stock, minimum and maximum, clinical criticality, replenishment cadence, budget caps, demand exclusions, stockout-censoring rules and approved forecast parameters. Changes have a preview, a permission check, an effective date and audit, and can trigger a re-forecast and re-proposal.

**Why this priority**: Moves policy ownership from code and developers to the business.

**Independent Test**: Change a service level and a budget cap, preview the effect, activate, and verify the next proposal uses them, the audit shows the change, and a conflicting concurrent edit is rejected.

**Acceptance Scenarios**:

1. **Given** current policies, **When** the buyer changes a value, **Then** a preview shows affected products and the expected change in quantities and spend before saving.
2. **Given** a saved policy with a future effective date, **When** that date arrives, **Then** later forecast and proposal runs use it, earlier runs are unchanged, and each run records the policy version used.
3. **Given** a viewer, **When** attempting to edit, **Then** the action is refused and recorded.
4. **Given** a concurrent edit, **When** the second save is based on an outdated revision, **Then** it is rejected with a conflict explanation.
5. **Given** out-of-range values (service level outside 0–100%, negative safety stock, maximum below minimum), **When** saved, **Then** they are refused with Spanish messages.
6. **Given** a policy change, **When** the user chooses to apply it, **Then** a versioned re-forecast and re-proposal can be triggered, and unchanged inputs produce unchanged results.
7. **Given** products excluded from demand (for example one-off or promotional events), **When** the exclusion is saved with a reason, **Then** those periods are excluded from forecasting and the exclusion is visible and reversible.

---

### User Story 5 - Predictive seed data import with provenance and rollback (Priority: P2)

Because ERP history is short, the buyer uploads initial predictive data (CSV or XLSX) such as estimated or manually forecast demand. A guided flow covers a Spanish template download, column mapping, preview, row-level validation, quarantine of invalid rows, approval, versioned activation, a dry-run comparison, and rollback to the prior version. Imported data is always kept separate from actual ERP movements.

**Why this priority**: It unlocks forecasts on thin history and is the main way to supply the initial predictive base without code changes.

**Independent Test**: Upload synthetic CSV and XLSX files (valid, partly invalid, duplicate, malicious), run the full flow, activate, observe a new forecast run referencing the dataset version, then roll back.

**Acceptance Scenarios**:

1. **Given** a CSV or XLSX within size and type limits, **When** uploaded, **Then** content is verified by signature and not only by name, macros and formulas are never executed, and the file is held in private quarantine until validated.
2. **Given** a file, **When** the buyer maps columns (product or Siweb variant ID, dates, quantities, warehouse, provenance, kind: observed, estimated, manual forecast), **Then** a preview of the first rows and the mapping is shown before validation, and the mapping can be saved for reuse.
3. **Given** rows with unknown variants, negative quantities, impossible or out-of-range dates, duplicates or missing provenance, **When** validated, **Then** each is rejected or quarantined with a row-level Spanish reason, valid rows proceed, and nothing is silently dropped or corrected.
4. **Given** a validated dataset, **When** the buyer views the dry-run, **Then** a diff against the active dataset and a backtest comparison are shown before activation.
5. **Given** a confirmation by a buyer or admin, **When** the dataset is activated, **Then** activation is atomic, audited, produces a new dataset version, and triggers a forecast run that records the exact dataset and policy versions.
6. **Given** an active dataset, **When** rollback is requested, **Then** the previous version is restored atomically, audited, and a new forecast run reflects it; no data is deleted.
7. **Given** any imported data, **When** displayed or used, **Then** it is labelled imported or estimated and is never counted as an actual ERP movement, never written to the ERP, and synthetic and real observations are never mixed silently.
8. **Given** a file containing spreadsheet formula text in cells, **When** it is later exported or shown, **Then** it is neutralised so it cannot execute in a spreadsheet.
9. **Given** the same file uploaded twice, **When** the second upload is validated, **Then** the duplicate is detected and the buyer decides explicitly.

---

### User Story 6 - Procurement scenarios and explainable allocation (Priority: P2)

The buyer builds what-if scenarios (budget cap, supplier disabled, changed terms, different service level) and compares them with the baseline proposal: allocation by supplier, which conditions were used, why constraints bound (minimums, lead time, shipping, pack multiples, budget), cost sensitivity and budget utilisation. A chosen scenario becomes the proposal that follows the normal approval workflow, and results export to CSV or Excel.

**Why this priority**: It lets the buyer see the effect of supplier terms and budgets before committing and builds trust in recommendations.

**Independent Test**: Create scenarios that vary a minimum order, lead time, shipping cost, pack multiple and budget, and verify allocations change as expected with explanations; promote one scenario and run approval.

**Acceptance Scenarios**:

1. **Given** the baseline, **When** the buyer defines a scenario with changed parameters, **Then** it is computed without altering the live configuration or any ERP data, and shown beside the baseline.
2. **Given** a scenario, **When** results are shown, **Then** each supplier group lists lines, quantities, costs, order total, shipping, discounts applied, expected delivery, budget utilisation, and a plain-language reason for each binding constraint.
3. **Given** the same inputs and versions, **When** a scenario is recomputed, **Then** the result is identical, and the exact configuration and dataset versions are recorded.
4. **Given** a scenario selected for purchase, **When** promoted, **Then** it becomes a proposal needing the normal submit and different-person approval, and nothing is sent to suppliers.
5. **Given** a scenario or proposal, **When** exported to CSV or Excel, **Then** the file is Spanish, uses EUR and Spanish formats, and is safe against formula injection.
6. **Given** no feasible allocation (budget too low, all suppliers disabled), **When** computed, **Then** the shortfall and its causes are explained rather than returning an empty result.

---

### User Story 7 - Administration, reliability and cost visibility (Priority: P3)

The admin sees sync status and source freshness, import jobs, supplier-policy history, model runs, role management and cost indicators, and can safely re-run jobs that are permitted to be re-run.

**Why this priority**: Operators need to trust and recover the system, and the shared budget must stay within limit.

**Independent Test**: Trigger a failed sync, a failed import and a duplicate re-run; verify visibility, safe retry, no duplicate side effects and alerts.

**Acceptance Scenarios**:

1. **Given** the latest ERP collection, **When** the admin opens status, **Then** last success, record counts, freshness per source and failures are shown.
2. **Given** a failed or in-progress import or forecast run, **When** the admin views it, **Then** state, error and dataset or policy versions are shown, and a permitted re-run is idempotent.
3. **Given** the cost indicators, **When** viewed, **Then** estimated monthly spend versus the shared budget is shown, and guardrails (scale-to-zero, replica and job caps) are verified by automated checks.
4. **Given** any admin action, **When** performed, **Then** it is role-checked, audited and refused for non-admins.

---

### Edge Cases

- Upload exceeds the size limit, has a wrong extension with different signature, contains macros, formulas, or thousands of columns: refused or neutralised with a Spanish message.
- An XLSX with several sheets or merged cells; a CSV with unexpected delimiter, encoding or decimal comma: mapping wizard detects and asks, never guesses silently.
- A dataset overlapping periods that already have actual ERP movements: actuals prevail and the overlap is reported.
- Activation fails midway: nothing is partially applied; the previous version remains active.
- Rollback while a forecast run is in progress: run is superseded or completed safely, with the versions recorded.
- Two buyers editing the same supplier or policy simultaneously: second save is rejected with the newer version shown.
- A supplier term becomes valid in the future or expired in the past: proposals use only terms valid on the run date.
- A product has no supplier terms at all: conservative defaults are used and flagged for the buyer.
- Warehouses that appear or disappear in the ERP: filters follow live data; no stale hard-coded option.
- The user's second factor expires during a long review: approval needs re-verification, work is not lost.
- The orchestration layer restarts mid-approval or mid-import: state resumes from stored records.
- Daylight-saving transitions in imported timestamps: ambiguous or non-existent local times go to review, as for ERP movements.
- Budget cap is below the sum of mandatory (clinical-critical) needs: the shortfall is shown, not silently dropped.
- The selling price (PVP) needed for the margin check is missing or stale (the variant price was last confirmed by a successful sync more than 7 days ago): the margin check is shown as unavailable and the release is blocked until the price is known and fresh or an admin overrides with a reason. The price's age is always shown next to it.
- A lot in stock has no recorded acquisition cost, or lots of one product have very different costs: the value uses the labelled fallback, is counted in the estimated-cost indicator, and the median suggestion shows every lot it used.
- An always-stocked product has no valid supplier terms, or every supplier is disabled or below its minimum order: the line is still shown with the shortfall and its cause, not dropped.
- An override request is pending when a new recommendation is computed: the pending request shows the recommendation it was made against and is flagged if the recommendation has since changed.
- Free-text notes appear in an imported file: ignored; only a has-note indicator is kept.

## Requirements *(mandatory)*

### Functional Requirements

**Foundations and security (Phase 0 blockers)**

- **FR-001**: Roles MUST persist across restarts and be mirrored to the purchasing side through an authenticated internal channel, with visible, retried failures and an audit entry per change.
- **FR-002**: Submission for approval MUST be refused unless at least two active users could approve; approval MUST require a different user from the creator and last editor, the approver role, and a second factor verified within the last 5 minutes, verified end-to-end in the full stack.
- **FR-003**: Previously unreviewed web and orchestration code MUST be reviewed, with findings resolved or recorded as accepted risks, before operational UI is released.
- **FR-004**: Open 001 gates (request-budget split, loss-reason cutover decision, 429 behaviour, threat model, regional cost review, container smoke test) MUST be tracked and either closed or explicitly deferred with an owner before production use.

**Analytics**

- **FR-005**: The dashboard MUST show at least four business KPIs (inventory value at acquisition cost, coverage days, products at stockout risk or expiring value, proposed purchase spend) and at least five distinct visualisations (demand versus forecast with uncertainty, ABC/XYZ distribution, stockout and expiry risk, forecast accuracy, spend), all from live data.
- **FR-005b**: Coverage days MUST be stock on hand divided by average daily forecast demand for the next 30 days, or by average actual daily demand over the last 90 days when the product is not forecast-eligible; the basis MUST be labelled per product, and products with no demand MUST show a Spanish "no demand" state, never infinity or zero.
- **FR-006**: Filters for date range, category (the ABC/XYZ demand group and clinical-critical flag, plus the ERP product family once it is synchronised), supplier and warehouse MUST be populated from live data and apply consistently to every KPI and chart; server-side filtering and pagination MUST be used for lists.
- **FR-007**: Every KPI and chart MUST support drill-down to product and supplier detail and show data freshness; empty, loading, error and stale states MUST be explicit.
- **FR-008**: Views MUST distinguish actual ERP data from imported estimates and manual forecasts everywhere they appear.
- **FR-009**: Charts MUST have accessible text or table alternatives and be keyboard operable.

**Acquisition cost of stock**

- **FR-040**: The system MUST keep, in MMI's own data, an acquisition cost per product lot (variant, lot/batch, quantity received, unit acquisition cost, source, date), filled automatically from the cost on the confirmed supplier order when the receipt is matched to the lots, stored Recargo-inclusive (a net cost is converted with the Recargo rate of the product's VAT rate, as in 001), recorded from the buyer's own entry when the ERP has no cost and no lot exists, and correctable by the buyer when the goods arrive, with every correction audited, because ERP stock movements carry the retail price (PVP) and the ERP holds a single unit cost per supplier. ERP movement prices MUST NOT be used as cost.
- **FR-041**: Inventory value on the dashboard MUST be quantity on hand per lot multiplied by that lot's acquisition cost; the basis MUST be labelled. A lot with no recorded acquisition cost MUST be valued at the best available labelled fallback (current verified supplier cost) and counted in a "valued with estimated cost" indicator, never silently at zero or at PVP.
- **FR-042**: A supplier-cost update request MUST be created when goods are received and matched to a confirmed order, or when the buyer enters a cost for a product-supplier pair that has no ERP cost. Its value MUST be the plain (not quantity-weighted) median of the Recargo-inclusive acquisition costs of that pair's entries (per variant, supplier and lot) whose lot has remaining stock, obtained from the inventory service by variant and matched by lot when the request is built and recorded with it: the mean of the two middle values when the count is even, exact decimals, rounded half-up to whole cents; entries with no remaining quantity or no cost are excluded and listed. When the ERP has no cost and no lot exists, the buyer-entered cost is recorded as the pair's opening entry and is the value; when no entry has remaining stock, no request is created. The screen MUST show the entries used; the buyer changes the outcome only by correcting lot costs, and only an admin may replace the median under FR-044. Buyer review, fresh MFA, the separate writer and audit remain mandatory, and every update is evaluated against FR-043. For the cost value and its timing this supersedes scenarios 4c and 4d of specs/001-mmi-purchase-intelligence; their review, audit, retry and pending-link rules still apply.
- **FR-043**: Before each supplier-cost update the system MUST show the selling price (PVP) used, the margin before and after the new cost, and evaluate these rules, with margin = 1 − (Recargo-inclusive cost ÷ PVP), equivalent to PVP = Recargo-inclusive cost ÷ (1 − margin), and the EUR 50 threshold applied to the Recargo-inclusive cost: (a) maximum margin 30% when the cost is below EUR 50 and 20% when it is EUR 50 or more; (b) if the margin after the update is above its maximum but was already at or above it before, it is left as it is and flagged "margin kept (offer)"; (c) if the margin was below the maximum and increases, it may increase up to the maximum, and any excess is flagged; (d) a margin after the update below 15% blocks the release. Rules (a) to (c) only flag and explain; rule (d) blocks until an admin override under FR-044.
- **FR-044**: An admin MUST be able to set a cost value of their own for a blocked or flagged update, in place of the median. The screen MUST give explanatory tips (resulting margin, applicable rule, the cost that yields exactly 15% and the cap, and the lots behind the median). The override MUST require a reason, be audited with the median, the chosen value, margins before and after, who and when, and still pass buyer review, fresh MFA and the writer's own checks; it MUST NOT bypass the single permitted write or its allowlist. The admin who sets an override MUST NOT be the person who releases it: the release MUST be by a different buyer with fresh MFA, and a release by the person who set the override MUST be refused. If no other eligible buyer exists, the override stays pending.

**Categories, recommended safety stock and always-stocked products**

- **FR-045**: The system MUST re-evaluate each product's category (ABC, XYZ, demand pattern, and the manual clinical-criticality flag) whenever demand data updates, keep a history of category changes with the reason, and show the current category and its history on the product detail.
- **FR-046**: For every product the screen MUST show the recommended safety stock (derived from its category under FR-039) next to the effective value in force, and say whether the effective value is the recommendation or an approved override.
- **FR-047**: Overriding the recommended safety stock (or minimum/maximum) of a product MUST require a reason and approval by a user with the approver role who is not the requester (no additional fresh MFA beyond the normal multi-factor sign-in) before it takes effect; until then the recommendation stays in force. Requests, approvals, rejections and reversions MUST be audited, and the override MUST show who approved it and when.
- **FR-048**: A product MAY be marked "always stocked" with a minimum stock floor (for example 1 unit). For such a product the weekly proposal MUST include a replenishment line whenever stock is below the floor, even with no recent demand or when the product is not forecast-eligible, and MUST include at least one replenishment check each month so the floor is restored without anyone requesting it. Nothing is ordered automatically: the line follows the normal edit, submit and different-person approval workflow, and the explanation states that the floor rule produced it.

**Supplier configuration**

- **FR-010**: The buyer MUST be able to create, view, edit and disable, per supplier: lead time, delivery weekdays and order cut-off, minimum order (units and value), free-shipping threshold, shipping cost, pack multiples, discounts, payment terms, preferred status, validity window, reliability rating.
- **FR-011**: The buyer MUST be able to override those terms per product-supplier pair; the override takes precedence for that product only, and precedence MUST be visible.
- **FR-012**: Every terms change MUST create an effective-dated, immutable version with author, source badge (ERP, import, manual), reason and audit entry; history MUST be viewable.
- **FR-013**: Saves MUST use optimistic concurrency and reject stale edits with a conflict explanation; invalid input MUST be rejected with specific Spanish messages and stable error keys.
- **FR-014**: Saved terms valid on the run date MUST be applied by the allocation engine in the next proposal and scenario, and the explanation MUST cite the terms used.
- **FR-015**: Supplier terms MUST remain local to MMI; no ERP request is made for them. Field precedence between verified ERP fact, approved local override and uploaded estimate MUST be defined, applied consistently and shown with conflict indicators.

**Policy configuration**

- **FR-016**: Authorised users MUST be able to edit service levels (by segment and by product), safety stock, minimum/maximum, clinical criticality, replenishment cadence, budget caps, demand exclusions with reason, stockout-censoring rules and approved forecast parameters.
- **FR-017**: Each policy change MUST show a preview of affected products and effect, support an effective date, use revision-checked saves, be audited, and record the policy version in every later forecast and proposal run.
- **FR-018**: Policy changes MUST be able to trigger a versioned re-forecast and re-proposal on request; unchanged inputs MUST yield identical results.
- **FR-019**: Policy edits MUST be restricted to permitted roles; refused attempts MUST be recorded.

**Predictive seed import**

- **FR-020**: Authorised users MUST be able to upload CSV and XLSX files through an authenticated, CSRF-protected flow with size and type limits, file-signature verification, streaming parsing, no macro or formula execution, private encrypted quarantine storage and a documented retention period.
- **FR-021**: A Spanish template MUST be downloadable; a mapping wizard MUST map columns to product or Siweb variant ID, dates, quantities, warehouse, provenance and data kind (observed, estimated, manual forecast), with saved mappings.
- **FR-022**: The system MUST preview rows and mapping, validate every row (exact variant match, date range, negative quantities, duplicates, provenance), reject unmatched variants, quarantine invalid rows with Spanish reasons, and never silently correct or drop data. Files above 10,000 rows MUST be processed in the background: the buyer is told at once that the file was sent to the background, and an import status section MUST show every import with its stage, timings and any error.
- **FR-023**: Before activation the system MUST show a diff against the active dataset and a dry-run backtest comparison.
- **FR-024**: Activation MUST require buyer or admin confirmation, be atomic and audited, create a new dataset version and trigger a versioned forecast run; rollback MUST restore the prior version atomically without deleting data.
- **FR-025**: Imported data MUST be stored apart from ERP movements, labelled with provenance, never presented as actual demand, never written to the ERP, and synthetic and real observations MUST NOT be mixed silently.
- **FR-026**: All forecasts, scenarios and proposals MUST reference the exact dataset, policy and terms versions used.
- **FR-027**: Exports and displays of imported text MUST be formula-injection-safe.

**Scenarios and explanations**

- **FR-028**: The buyer MUST be able to create what-if scenarios varying budget, supplier availability, supplier terms and service levels, computed without changing live configuration, and compared with the baseline.
- **FR-029**: Scenario and proposal views MUST show, per supplier group, lines, quantities, costs, shipping, discounts, order total, expected delivery, budget utilisation, binding constraints with plain-language reasons, and cost sensitivity.
- **FR-030**: A selected scenario MUST be promotable to a proposal that follows the existing submit and different-person approval workflow; no order is sent to a supplier and no ERP write occurs except the existing buyer-released cost update.
- **FR-031**: Infeasible scenarios MUST explain the shortfall and its causes; results MUST be reproducible from recorded inputs.
- **FR-032**: Scenario and proposal results MUST be exportable to CSV and Excel in Spanish, with EUR and Spanish formats.

**Administration and cross-cutting**

- **FR-033**: Admins MUST see sync status and source freshness, import jobs, supplier-policy history, model runs and role management, and MUST be able to safely re-run permitted jobs idempotently.
- **FR-034**: Every mutation MUST enforce role-based access, be audited, and return stable localised error keys; monetary values MUST be exact decimals; timestamps MUST be stored in UTC with the original value where applicable; products MUST be keyed by Siweb variant ID.
- **FR-035**: All user-facing text, validation messages, exports, templates, notifications and help MUST be Spanish (es-ES) with EUR and Spanish date/number formats; an automated check MUST fail on untranslated or hard-coded strings.
- **FR-036**: Each service MUST keep its own schema, role, migrations and versioned contract; contracts MUST be defined before implementation; the front-end orchestration layer MUST contain no business rules and no cross-schema data access; existing reuse MUST be preferred over rewrites.
- **FR-037**: Free-text notes and supplier tax identifiers MUST NOT be parsed, stored or used, including in imports; malformed or ambiguous records MUST go to review.
- **FR-038**: The feature MUST stay within the shared EUR 120/month budget: no always-on analytics infrastructure, scale-to-zero, replica and job caps, and automated cost-guardrail checks.
- **FR-039**: Public-repository content MUST be synthetic only; no secrets, real identifiers, prices or imports.

### Key Entities *(include if feature involves data)*

- **Supplier terms version**: effective-dated commercial conditions for a supplier (lead time, schedule, minimums, shipping, discounts, payment terms, preference, validity, reliability, disabled flag) with author, source badge and reason.
- **Product-supplier terms override**: terms version scoped to one product and supplier, taking precedence for that product.
- **Policy set / policy revision**: versioned collection of service levels, safety stock, min/max, criticality, cadence, budget caps, exclusions, censoring rules and forecast parameters, with effective date and revision for concurrency.
- **Seed dataset**: versioned imported predictive data with provenance, data kind, status (uploaded, validated, approved, active, superseded, rolled back), file reference, mapping and checksum.
- **Seed row / quarantine entry**: one imported record and, when invalid, its Spanish rejection reason.
- **Column mapping**: saved association between file columns and canonical fields.
- **Scenario**: a parameter set computed against the baseline, with results, constraint explanations, sensitivity, and recorded input versions; may be promoted to a proposal.
- **Lot acquisition cost**: MMI-owned record of what a lot of a product actually cost to acquire (variant, lot, quantity, unit cost, source such as confirmed order, receipt, import or manual entry, date); basis for inventory value and for the suggested supplier-cost update.
- **Dashboard aggregate**: read model of KPIs, trends, distributions, accuracy and risks, with filters and freshness.
- **Role assignment**: durable user-to-role mapping with change history and mirror status.
- **Safety stock override request**: a product-level request to replace a recommended safety stock or minimum/maximum, with reason, requester, status (pending, approved, rejected, reverted), approver and decision time.
- **Stocking mode**: per-product setting (standard, always stocked, on request) with the minimum stock floor used by FR-048.
- **Audit entry**: tamper-evident record of who, when, what, before and after.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A buyer can configure a supplier's full commercial terms and one product override, and see them reflected in the next proposal, in under 10 minutes without developer help.
- **SC-002**: A buyer can complete a seed import (upload to activation) of a 1,000-product file in under 15 minutes, and roll it back in under 2 minutes.
- **SC-003**: 100% of dashboard KPIs match independently computed totals on the synthetic reference dataset, and the dashboard shows first meaningful content in under 3 seconds for a data set of about 1,000 products.
- **SC-004**: Zero hard-coded warehouse, supplier or category options remain; all filter options come from live data (verified by automated check).
- **SC-005**: 100% of imported rows are either accepted or listed with a Spanish rejection reason; zero rows silently dropped; zero imported values counted as ERP movements.
- **SC-006**: 100% of configuration, terms, import, role and approval changes have an audit entry; 100% of forecasts, scenarios and proposals reference the dataset, policy and terms versions used.
- **SC-007**: A proposal can be submitted and approved by two different users with a fresh second factor after an orchestration-layer restart; self-approval and stale-factor attempts are refused in 100% of tests.
- **SC-008**: Scenario comparison shows, for minimum order, lead time, shipping cost, pack multiple and budget changes, a different allocation with a stated reason in 100% of reference cases.
- **SC-009**: 100% of user-visible strings, errors and exports are Spanish with EUR and Spanish formats; the automated localisation check passes with zero exceptions.
- **SC-010**: Automated suites pass for contracts, service integration, database migrations (upgrade and downgrade), Spanish end-to-end browser flows, accessibility, security abuse cases and performance budgets, using synthetic data only.
- **SC-011**: Projected shared monthly spend stays at or below EUR 120 with scale-to-zero preserved, verified by cost guardrail checks.
- **SC-012**: 100% of supplier-cost updates whose margin would fall below 15% are blocked without an admin override, 100% of released updates equal the median of the recorded lot costs (or the audited admin override), and inventory value matches the independently computed quantity-times-lot-cost total on the reference data.

## Assumptions

- Users are a small team (fewer than 10) of viewers, buyers, approvers and admins; desktop browsers only.
- Existing services, schemas, contracts, queue/outbox mechanisms and Spanish i18n are reused; new capability is added to the service that already owns the data (procurement owns terms, policies and scenarios; forecast owns seed datasets and forecast parameters; inventory owns aggregates).
- Dashboard aggregates are computed on demand or by existing scheduled jobs; no new always-on analytics infrastructure.
- Seed files are modest in size (up to a few tens of thousands of rows); exact limits are set in planning.
- Malware scanning is applied where feasible within budget; otherwise compensating controls (signature checks, no execution, private quarantine) apply and the gap is recorded.
- Gate 0 V6, V7 and the real response shapes of lots and supplier lists remain open decisions owned by the business; defaults from 001 stay in force until closed.
- Link creation in the ERP stays out of scope; the supplier-cost write is unchanged.
- Delivery is by small, reviewable pull requests per phase (Phase 0 blockers, contracts and migrations, supplier and policy CRUD, import pipeline, analytics, scenarios, end-to-end and cost gates). PR #1 is not merged automatically, and nothing is deployed to production.
- Planning, tasks and implementation start only after this specification, the plan and the task list are reviewed by a human, as required by the authoritative Jira and Confluence sources.
- Proposed ADRs (configuration ownership, override precedence, seed provenance) will be written during planning.
