# Feature Specification: Data Quality and Forecast Intelligence (Agent 02)

**Feature Branch**: `claude/speckit-mmi-4-spec-2232c0`

**Created**: 2026-11-13

**Status**: Draft

**Input**: User description: "From the spec on MMI-4" (Jira MMI-4, "AGENT 02 | Data Quality & Forecast Intelligence", epic MMI-1; Confluence "MMI 003 — Agent 02 — Data Quality & Forecast Intelligence").

## Context

Buyers rely on the forecast to decide weekly purchases. Today they cannot see how good the history behind a forecast is, why a product received a given model, or how uncertain the number is. This feature makes data quality and forecast reliability visible and traceable, without changing who decides purchases (humans) or where the truth lives (Siweb360 for catalogue, stock, movements and ERP costs).

Scope (from the Jira/Confluence brief): historical coverage, anomalies, rejected movements, ABC/XYZ classification, intermittent demand, stockout censoring, model explainability, confidence and eligibility, backtesting, and source provenance.

Related features this one builds on and must not duplicate: 001 (forecast and proposals), 008 (predictive seed import; dataset versions and provenance labels), 004 (locally loaded UI exports, kept apart from ERP data), the business policy configuration (the console already on main from feature 002; feature 011 extends it and is not on main yet), 010 (admin audit viewer).

## Clarifications

### Session 2026-11-15

- Q: Should excluding an anomalous day need more than the buyer's own action? → A: A buyer or admin may decide alone, but excluding (or re-including) a day requires a recent second-factor check and is audited; no second person is needed. Accepting an anomaly as normal needs no second factor.
- Q: What should the proposal line show for a not-eligible or low-confidence product? → A: The existing conservative min/max quantity, labelled "not a forecast" with the reason, for the buyer to confirm or edit; no forecast figure is shown or stored.
- Q: How should stockout (censored) days be treated by the forecast? → A: They are left out of the data the forecast learns from; no demand is estimated or imputed for them in this feature.
- Q: Who may start a full-catalogue backtest, and how often? → A: Buyers and admins may start any backtest, but only one full-catalogue backtest may run at a time; a second request is refused with a Spanish message naming the running one, and an identical request reuses the existing result.
- Q: How long are forecast explanations, quality snapshots, anomaly decisions and backtest results kept? → A: 5 years in full detail, to align with the owner's regulatory data-storage requirement; nothing is dropped earlier.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Know how trustworthy a product's history is (Priority: P1)

A buyer opens a product and sees a data-quality summary: how many days of history exist, how much of the period is covered, which movements were rejected or quarantined and why, which days look anomalous, and which days were affected by a stockout. They can tell at a glance whether the history deserves trust.

**Why this priority**: Every other signal (model, confidence, proposal quantity) is only as good as the history; showing it is the foundation and the first thing buyers ask for.

**Independent Test**: Load a synthetic product with gaps, a rejected movement, an outlier day and a stockout period; the quality summary shows each with counts and Spanish reasons, and nothing is dropped silently.

**Acceptance Scenarios**:

1. **Given** a product with 90 days of movements and 12 days without data, **When** the buyer opens its quality summary, **Then** coverage is shown as days with data versus days in the period, and the gap days are listed.
2. **Given** movements rejected at ingestion (malformed or ambiguous), **When** the buyer opens the summary, **Then** the count, the reason in Spanish and a link to the review/quarantine list are shown, and no rejected movement contributes to demand.
3. **Given** a day whose quantity is far outside the product's normal range, **When** the summary is shown, **Then** the day is flagged as an anomaly with the rule that flagged it, and it is neither deleted nor silently corrected.
4. **Given** a period when the product had no stock, **When** the summary is shown, **Then** those days are marked as stockout-affected so the absence of sales is not read as zero demand.

---

### User Story 2 - See which model a forecast used and why (Priority: P1)

A buyer opens a forecast or a proposal line and sees the demand class of the product (ABC value class, XYZ variability class, and whether demand is intermittent), which forecasting method was chosen for that class, the confidence level, and whether the product is eligible for automatic suggestion or only for manual review. Every forecast names the model version, dataset version and configuration version it came from.

**Why this priority**: Explainability and version traceability are the completion gate for this feature and are what lets a buyer (and an auditor) reproduce or challenge a number.

**Independent Test**: Run a forecast over a synthetic catalogue spanning smooth, erratic and intermittent products; each result shows class, method, confidence, eligibility and the three version references, and re-running with unchanged inputs produces the same result.

**Acceptance Scenarios**:

1. **Given** a forecast result, **When** the buyer opens its explanation, **Then** it shows model version, dataset version(s), configuration/policy version, the history window used and the demand class in Spanish.
2. **Given** a product with sporadic sales, **When** its forecast is explained, **Then** it is labelled intermittent and the explanation states why a method suited to intermittent demand was used.
3. **Given** a product with too little or too poor history, **When** the forecast runs, **Then** it is marked not eligible with a Spanish reason and is excluded from automatic suggestions, never given an invented number.
4. **Given** unchanged inputs and versions, **When** the same forecast is recomputed, **Then** the result and explanation are identical.

---

### User Story 3 - See uncertainty, not just a point forecast (Priority: P1)

A buyer sees a forecast range (low–expected–high) and a confidence label next to every forecast, and sees that stockout-censored days were treated as lost demand rather than zero. Estimated, seeded or manual values are visibly distinguished from observed sales; no screen or export ever presents an estimate as an observed sale.

**Why this priority**: The acceptance criteria require uncertainty to be visible and forbid false observed sales; both protect purchasing decisions from over-confidence.

**Independent Test**: For a product with a stockout period and seeded days, the forecast shows a range and confidence, labels the seeded/estimated portion, and the history table never labels estimated values as observed.

**Acceptance Scenarios**:

1. **Given** any forecast, **When** it is displayed or exported, **Then** a range and confidence label accompany the expected value.
2. **Given** history that includes seed (feature 008) or estimated values, **When** it is displayed, **Then** each value carries its provenance label (observed, estimated, manual) and only ERP movements are labelled observed.
3. **Given** a stockout period, **When** the forecast is computed, **Then** censored days are not treated as zero demand and the explanation states how many days were censored.
4. **Given** wide uncertainty, **When** the proposal line is shown, **Then** the buyer sees a low-confidence warning and the line is not auto-suggested; it shows the conservative min/max quantity labelled "not a forecast".

---

### User Story 4 - Judge forecast accuracy with a backtest (Priority: P2)

A buyer or admin opens a backtest view for a product, category or the whole catalogue and sees how the chosen method would have performed on past periods against actual sales: error measures, bias, and how it compares with a simple baseline. Products where the method does not beat the baseline are flagged.

**Why this priority**: Backtesting justifies trust in the model and drives eligibility, but the product is usable without it once US1–US3 exist.

**Independent Test**: Run a backtest on synthetic history with a known pattern; error and bias match the expected values, and a product where the baseline wins is flagged.

**Acceptance Scenarios**:

1. **Given** at least the minimum history, **When** a backtest is run, **Then** results show error, bias and baseline comparison per product, with the periods and versions used.
2. **Given** a product whose method does not beat the baseline, **When** results are shown, **Then** it is flagged and its eligibility and confidence reflect the finding.
3. **Given** a backtest, **When** it runs, **Then** no stored forecast, proposal, stock figure or ERP data changes.

---

### User Story 5 - Portfolio view of data quality and classes (Priority: P2)

A buyer or admin sees, across the catalogue, the distribution of ABC/XYZ classes, intermittent products, products by eligibility, and the products with the worst data quality, and can filter by category and supplier to decide where to improve data first.

**Why this priority**: Turns per-product signals into a work queue; valuable but dependent on the earlier stories.

**Independent Test**: With a synthetic catalogue, totals by class and eligibility add up to the catalogue size and every figure drills down to the underlying product list.

**Acceptance Scenarios**:

1. **Given** a synced catalogue, **When** the portfolio view opens, **Then** counts by class and eligibility sum to the number of active products and each count opens its product list.
2. **Given** a filter by category or supplier, **When** applied, **Then** all figures recompute for that subset.
3. **Given** the viewer role, **When** the view opens, **Then** it is visible read-only; configuration changes remain restricted to buyers and admins.

---

### Edge Cases

- Product with no history at all: shown as not eligible with reason; no forecast figure invented.
- Product with history only from seed data (feature 008): labelled estimated/seeded, never observed; eligibility follows the rescue rule defined there.
- Movement with a missing or ambiguous SKU, duplicate movement, or malformed date: goes to quarantine/review, never dropped silently, never counted as demand.
- Returns, transfers and adjustments: excluded from demand unless the configured rule says otherwise, and reported in the quality summary.
- Stockout that spans the whole history window, or very short windows: marked as insufficient information, not as zero demand.
- Data loaded locally from UI exports (feature 004) has surrogate ids and must never be mixed with ERP-collected data in classes, backtests or counts.
- Class thresholds or policies change between two forecast runs: older forecasts keep their original configuration version and remain explainable.
- Two users trigger the same backtest or recomputation: idempotent, one result set per input version.
- Very large catalogues: classification and backtests run in the background with visible status and never block screens.
- Timestamps in other zones or formats: stored as UTC plus the original text.

## Requirements *(mandatory)*

### Functional Requirements

**Audit and reuse**

- **FR-001**: The work MUST begin with an audit of the latest main branch recording, for each capability in this spec, whether it is complete, partial, broken, missing or unverified, with file and line evidence, and MUST reuse working code (existing forecast runs, backtest, eligibility, policy and seed provenance) instead of rebuilding it.

**Data quality**

- **FR-002**: The system MUST compute, per product and period, historical coverage (days with data versus days in the period) and list the gap days.
- **FR-003**: The system MUST report per product the count and reasons of rejected, quarantined or ambiguous movements, with a link to the review list, and MUST NOT include them in demand.
- **FR-004**: The system MUST flag anomalous days using stated, deterministic rules, show which rule flagged each, and MUST NOT delete or silently correct the original value; a buyer or admin MAY mark an anomaly as accepted or excluded, recorded with who and when. Excluding a day, or reversing an exclusion, MUST require a recent second-factor check; accepting an anomaly as normal MUST NOT.
- **FR-005**: The system MUST identify stockout-affected days from stock history, treat them as censored (not zero demand) by leaving them out of the data the forecast learns from, without estimating demand for them, and show the number of censored days in the explanation.
- **FR-006**: The system MUST exclude from demand the movement types that are not sales (for example transfers, adjustments) according to configuration, and report excluded counts.

**Classification**

- **FR-007**: The system MUST classify each product by ABC (value contribution) and XYZ (demand variability) and flag intermittent demand, using thresholds taken from the business policy configuration, and MUST record the configuration version used.
- **FR-008**: The system MUST show, for each class combination, which forecasting method is applied and why, and MUST keep that mapping consistent between the explanation, the proposal and any export.

**Forecast explainability and versioning**

- **FR-009**: Every forecast MUST reference the model version, the dataset version(s) and the configuration/policy version that produced it, and MUST record them with the result.
- **FR-010**: The system MUST provide a Spanish explanation for each forecast covering history window, demand class, method, censored and anomalous days, provenance mix, confidence and eligibility.
- **FR-011**: Recomputing a forecast with unchanged inputs and versions MUST produce an identical result and explanation; any change in an input version MUST produce a new, separately retrievable result and never overwrite the old one.

**Uncertainty, confidence and eligibility**

- **FR-012**: Every forecast MUST show a range (low, expected, high) and a confidence label, derived from history quality and, where available, backtest accuracy; the derivation rule MUST be documented and testable.
- **FR-013**: The system MUST mark each product eligible, manual-review-only or not eligible, with a Spanish reason, based on history sufficiency, quality and confidence thresholds from policy; not-eligible products MUST get no forecast figure and manual-review-only products MUST NOT be auto-suggested. For both, and for low-confidence products, the proposal line MUST show the conservative min/max quantity labelled in Spanish as "not a forecast", with the reason, for the buyer to confirm or edit.

**Provenance and no false observed sales**

- **FR-014**: Every demand value shown or exported MUST carry one provenance label (observed, estimated, manual); only movements collected from the ERP MAY be labelled observed, and seed (feature 008), local-export (feature 004) and imputed values MUST never be presented as observed sales.
- **FR-015**: Any estimated or imputed value (none is created for censored days in this feature, but seed data already is) MUST be stored apart from ERP-derived demand so that removing them leaves ERP-derived data exactly as it was, and MUST NOT be written to the ERP.

**Backtesting**

- **FR-016**: The system MUST run backtests of the chosen method over past periods and report error, bias and comparison with a simple baseline per product, category and catalogue, recording the periods, dataset and configuration versions used.
- **FR-017**: A backtest MUST NOT change any stored forecast, proposal, stock figure or ERP data; results are stored as their own versioned records.
- **FR-018**: The system MUST flag products where the method does not beat the baseline and feed that finding into confidence and eligibility.

**Views, access and audit**

- **FR-019**: The system MUST provide a per-product quality and forecast-intelligence view, a backtest view and a portfolio view with filters by category and supplier, all in Spanish (es-ES) with Spanish number and date formats, and every aggregate MUST drill down to its products.
- **FR-020**: Buyers and admins MUST be able to run backtests, recompute classes and accept or exclude anomalies; viewers MUST have read-only access. Excluding or re-including an anomalous day requires a recent second-factor check (FR-004). Sensitive configuration changes remain governed by the existing business policy configuration controls, including fresh multi-factor authentication.
- **FR-021**: Anomaly decisions, recomputations and backtest runs MUST be audited (who, when, what, versions) without storing free-text notes, tax identifiers or personal data.

**Operation**

- **FR-022**: Long-running computations (classification, backtests over the full catalogue) MUST run in the background with visible status, retry on failure without partial results, and be idempotent when repeated. At most one full-catalogue backtest MAY run at a time; a second request MUST be refused with a Spanish message that identifies the running one, and a request with identical inputs MUST return the existing result instead of a new run.
- **FR-023**: All timestamps MUST be stored in UTC with the original text preserved; all amounts MUST be exact decimals; products MUST be keyed by the ERP variant identifier while users see and supply SKUs only.
- **FR-024**: The feature MUST NOT introduce always-on analytics services or cross-service database access, and MUST stay within the shared monthly cost target.
- **FR-025**: Forecast explanations, data-quality snapshots, anomaly decisions and backtest results MUST be retained in full detail for 5 years and MUST NOT be deleted or overwritten earlier; after 5 years they MAY be removed by a documented, audited retention job. Storage growth from this retention MUST fit within the cost target in FR-024.

### Key Entities

- **Data-quality snapshot**: per product and period; coverage, gap days, rejected/quarantined counts with reasons, anomaly count, stockout-censored days, excluded-movement counts; tied to dataset and configuration versions.
- **Anomaly flag**: a day, the rule that flagged it, the original value, and the buyer's decision (pending, accepted, excluded) with who and when.
- **Demand class**: per product; ABC class, XYZ class, intermittent flag, the thresholds' configuration version, and the method mapped to it.
- **Forecast explanation**: model version, dataset version(s), configuration version, history window, class, method, censored and anomalous days, provenance mix, range, confidence and eligibility with reason.
- **Eligibility decision**: eligible / manual-review-only / not eligible, with reason and the thresholds applied.
- **Backtest run and result**: periods, versions, per-product error, bias, baseline comparison and flag; immutable once finished.
- **Provenance label**: observed, estimated or manual, attached to every demand value.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of forecasts, in screens and in the existing proposal export, show model, dataset and configuration versions, a range and a confidence label.
- **SC-002**: 0 values from seed, local-export or imputed sources are labelled observed in any screen or export, verified by automated checks over a synthetic catalogue covering all sources.
- **SC-003**: A buyer can find why a product has a given forecast, class, confidence and eligibility in under 1 minute starting from the proposal line.
- **SC-004**: 100% of rejected or ambiguous movements in a test set appear in the quarantine/review list with a Spanish reason; none is dropped silently or counted as demand.
- **SC-005**: Recomputing any forecast with unchanged inputs yields an identical result in 100% of test cases.
- **SC-006**: For a synthetic catalogue of 5,000 products, the portfolio view loads within 3 seconds and a full-catalogue backtest completes in the background within 15 minutes, with status visible throughout.
- **SC-007**: Counts by class and eligibility in the portfolio view equal the number of active products in 100% of test cases, and each count opens the matching product list.
- **SC-008**: Backtest runs leave stored forecasts, proposals, stock and ERP data byte-for-byte unchanged in 100% of test cases.
- **SC-009**: The demonstration shows the complete flow (quality summary, class and method, range and confidence, backtest) in the Spanish UI backed by the real API, with automated tests passing on synthetic fixtures only.

## Assumptions

- Siweb360 remains the source of truth for catalogue, stock, movements and ERP costs; this feature only reads synced data and owns its own derived records.
- The default location for this feature's new artifacts is `specs/018-data-quality-forecast-intelligence`; the Jira brief names `specs/003-agent-02`, but the repository's sequential numbering already uses 003 for another feature, so the sequential number is used and the brief's name is recorded here for traceability.
- ABC/XYZ thresholds, minimum history, confidence and eligibility thresholds and the rules for excluded movement types are configured through the business policy configuration (the policy console already on main from feature 002, and feature 011 once merged); this feature consumes them and adds defaults only where none exist.
- Seed datasets (feature 008) and locally loaded UI exports (feature 004) already carry origin and provenance labels that this feature reuses.
- The forecast service already provides forecast runs, eligibility and a backtest runner; the audit in FR-001 decides what is reused versus extended.
- Shared contracts (events, schemas) that must change are negotiated through the integration owner (Agent 00); this spec assumes only additive changes.
- Only synthetic fixtures are used in tests and demos; real exports stay local and are never committed.
- No production deployment, merge to main, or ERP write is part of this feature; humans continue to decide all purchases.
