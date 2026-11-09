# Feature Specification: Predictive Seed Import and Dataset Governance (Agent 05)

**Feature Branch**: `claude/mmi-7-specification-c0756a` (Jira MMI-7, epic MMI-1 "MMI 003 | Product completion — parallel agent execution")

**Created**: 2026-11-08

**Status**: Draft

**Input**: User description: "get the specification of <https://mundomascotix.atlassian.net/browse/MMI-7>" — Jira MMI-7 "AGENT 05 | Predictive Seed Import & Dataset Governance" and its linked Confluence page. Scope there: CSV/XLSX upload, templates, column mapping, SKU matching, duplicates, quarantine, preview, provenance observed/estimated/manual, dry-run backtest, activation, rollback and asynchronous jobs. Acceptance: an end-to-end import changes the subsequent forecast, rollback works, imported data never becomes an ERP movement, security tests pass.

## Context

Demand history in the ERP is short and sparse, so some products cannot be forecast honestly. The owner holds estimates and spreadsheets the ERP does not. Feature 002 (user story 5) and ADR-020 already decided how such **predictive seed datasets** are governed, and the repository already contains a first implementation: import routes in the API gateway (template, mappings, upload, validate, quarantine, dry-run, activate, reject, rollback, jobs) and seed handling in the forecast service. What is **not yet evidenced** is that the whole chain works end to end in the real interface and is proven by tests.

This feature is therefore a **completion and verification unit**, not a greenfield build. It must (1) audit what exists on the latest main branch and record each capability as complete, partial, broken, missing or unverified with file evidence, (2) close the gaps against the requirements below, reusing working code, and (3) prove the acceptance criteria with automated tests and a demonstration in the Spanish interface using synthetic data.

Baseline rules inherited from ADR-020 and feature 002, and kept here: seeds live apart from ERP-derived demand; there are three kinds of seed data (observed external, estimated, manual forecast), each with provenance and an origin flag (synthetic or real) and a dataset cannot mix origins; the lifecycle is uploaded, validated, active, superseded or rolled back, or rejected (activation is the approval); actual ERP demand always prevails over seed values on any day it covers; seed data may rescue a product only when its sole reason for being ineligible is "new", the seed rows cover at least half the days of their span, and the combined history reaches the minimum.

Out of scope: any write to the ERP; creating or faking ERP movements, stock or costs; sending orders to suppliers; changing the forecasting methods beyond accepting a seed dataset as input; parsing free-text notes; paid malware scanning (accepted risk recorded in ADR-020).

**Terms used in this spec**: a *seed dataset* is one uploaded file's content once checked, with a version and a lifecycle state; a *seed row* is one demand value for one product and day; *provenance* is the label saying a value is *observed* (an external observation, not an ERP record), *estimated* or *manual*; a *dry run* is a trial comparison with and without a dataset that changes nothing stored; *activation* makes a dataset influence forecasts; *rollback* withdraws it; *quarantine* puts a row on the review list (the quarantine list of the data-quality screen) with its reason.

## Clarifications

### Session 2026-11-08

- Q: Who may activate a dataset when the only buyer or admin is also its uploader and validator? → A: A different person by default; the owner/admin may self-activate only with a written reason, fresh multi-factor authentication and a distinct audit record.
- Q: Which people are blocked from approving activation? → A: The uploader and whoever chose the mapping or ran validation. The unused "approved" state is dropped; activation is the approval.
- Q: What do forecasts return to after rollback? → A: The dataset that was active before (none if there was none); rollback is a clean undo of one activation.
- Q: May real-origin seed files be uploaded in the cloud? → A: Yes, per ADR-020 (private container, origin flag), because they are the owner's own estimates; ERP exports stay local-only.
- Q: Is a row with no stated provenance treated as estimated or quarantined? → A: Quarantined (decided by the owner 2026-11-09), consistent with the constitution rule that ambiguous source data is not normalised into trusted input.
- Q: May an ERP export be uploaded as a seed file? → A: No; files recognised as ERP exports are refused (they are local-only under the constitution).
- Q: How are vague limits fixed? → A: Reuse the feature 002 size, row, decompression and sheet caps; "responsive" means every screen request answers within 2 seconds while a job runs.

### Session 2026-11-09 (corrections after code review)

- Q: What happens to a SKU that two products share exactly? → A: It is ambiguous like a SKU that differs only by case or spaces: every row carrying it is quarantined, none is resolved to either product. The platform does not assume the ERP keeps SKUs unique.
- Q: Must a file give the same result whether it is checked in the request or in the background? → A: Yes, the same accepted and quarantined rows for the same file and catalogue.
- Q: What if two people roll back at the same moment? → A: Exactly one rollback succeeds; the other is told about the conflict (same rule as two activations).
- Q: How are the reasons for a rollback or a self-activation handled, given the rule on free text? → A: Owner decision 2026-11-09: a pick-list choice plus a short free-text detail. The pick-list choice is what the list and the audit trail show; the detail is limited in length, shown to admins only and never written to the audit trail.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import a seed file and review it before anything changes (Priority: P1)

A buyer downloads a template, fills it with expected demand and uploads it. The platform checks the file, lets the buyer map columns if they differ from the template, matches each row to a product by SKU, flags duplicates and bad rows, and shows a preview of exactly what would be imported, stating that nothing has changed yet.

**Why this priority**: Without a trustworthy way in, nothing else works; a checked and previewed dataset already delivers value by exposing data problems.

**Independent Test**: Upload a synthetic file with valid rows, a duplicate SKU/day pair, an unknown SKU and a malformed number; verify the preview lists accepted, duplicate and quarantined rows each with a reason, and that no forecast changes.

**Acceptance Scenarios**:

1. **Given** a buyer on the import screen, **When** they download a template, **Then** they receive a CSV or Excel template in Spanish with required columns named and a clearly fictional example row.
2. **Given** a file whose column names differ from the template, **When** it is uploaded, **Then** the buyer maps each detected column to an expected field and may save the mapping for reuse.
3. **Given** rows referencing SKUs, **When** the file is validated, **Then** each row is matched to a catalogue product by SKU, and unknown or ambiguous SKUs go to quarantine with file, row number and reason.
4. **Given** repeated SKU and day pairs, **When** the file is validated, **Then** duplicates are shown together and none is silently chosen.
5. **Given** a validated dataset, **When** the buyer opens the preview, **Then** it shows counts (accepted, duplicate, quarantined), a sample of rows with provenance, the origin, and an explicit "nothing has changed yet" statement.
6. **Given** a viewer-role user, **When** they try to upload, map, validate, activate or roll back, **Then** the action is refused and recorded.

---

### User Story 2 - Dry run, then activate, and see the forecast change (Priority: P1)

Before a dataset influences anything, the buyer runs a dry run that shows how forecasts would differ with and without it. An authorised person then activates it, and subsequent forecast runs for the covered products use it.

**Why this priority**: This is the feature's purpose and its first acceptance criterion: an end-to-end import changes the subsequent forecast, as a deliberate, evidenced decision.

**Independent Test**: Import a synthetic dataset for a "new" product with a known pattern; run the dry run and verify no stored forecast changes; activate; verify the next forecast run for that product differs, is flagged as using seed data and records the dataset version, while uncovered products are unchanged.

**Acceptance Scenarios**:

1. **Given** a validated dataset, **When** the buyer starts a dry run, **Then** the result shows per product and in total the difference in forecast and in stockout/overstock outcome, and changes no stored forecast, proposal, stock figure or ERP data.
2. **Given** products whose history is too thin to judge, **When** the dry run completes, **Then** they are listed as not assessable, not given an invented score.
3. **Given** a dataset that passed the dry run, **When** an authorised person with fresh multi-factor authentication activates it, **Then** it becomes active, the previous active dataset becomes superseded, the activation is audited, and a versioned forecast run that records the dataset version is queued.
4. **Given** an active dataset, **When** a forecast or proposal line is explained, **Then** it states that seed data contributed, which dataset and version, and the provenance of the contributing values.
5. **Given** the person who uploaded a dataset or who chose its mapping or ran its validation, **When** they try to activate it, **Then** it is refused until a different authorised person does it, unless the owner/admin gives a reason (one choice from a short list, plus an optional short free-text detail) and fresh multi-factor authentication, in which case the self-activation is allowed and recorded as such.
6. **Given** a product that has enough actual ERP history, **When** a seed covers the same days, **Then** actual demand prevails, the overlap is reported, and the product is not rescued.

---

### User Story 3 - Roll back an activated dataset (Priority: P1)

If an activated dataset proves wrong, a buyer or admin withdraws it and forecasts return to what they would have been without it, with a record of why.

**Why this priority**: Rollback is an acceptance criterion and is what makes activation safe.

**Independent Test**: Record a covered product's forecast, activate a synthetic dataset, roll it back, run the forecast again, and verify the result equals the recorded one; verify the dataset is kept with state "rolled back" and an audit entry.

**Acceptance Scenarios**:

1. **Given** an active dataset, **When** an authorised user with fresh multi-factor authentication rolls it back with a reason (one choice from a short list, plus an optional short free-text detail), **Then** it stops influencing forecasts, a new versioned forecast run is queued, and the rollback is audited.
2. **Given** a rolled-back dataset, **When** forecasts next run, **Then** covered products' results equal those obtained just before it was activated (the previously active dataset's result, or no seed influence if there was none), given unchanged ERP data.
3. **Given** forecasts produced while the dataset was active, **When** viewed later, **Then** they still show which dataset version they used.
4. **Given** a rolled-back dataset, **When** the buyer re-imports a corrected file, **Then** it becomes a new dataset and nothing is deleted or overwritten.

---

### User Story 4 - See dataset state, provenance and quarantine at a glance (Priority: P2)

A buyer, admin or the owner can list all datasets with state, version, origin, uploader, approver, dates, counts and provenance mix, open any dataset to see its rows and quarantined rows with reasons, and download the quarantine list.

**Why this priority**: Governance visibility keeps the data honest, but the import-activate-rollback flow works before it is polished.

**Independent Test**: Import two datasets of different kinds, activate one, roll it back; verify the list and detail views show correct states, labels and history, and that the quarantine list downloads with formula-neutral content.

**Acceptance Scenarios**:

1. **Given** several datasets, **When** a user opens the list, **Then** each shows state, version, origin, kind, uploader, approver, dates, counts and provenance mix.
2. **Given** any seed value anywhere, **When** displayed, **Then** it carries exactly one provenance label and is never presented as an ERP movement, stock level or cost.
3. **Given** a row with no stated data type or no source label, **When** the file is validated, **Then** the row is quarantined with a Spanish reason and is never given a default label.
4. **Given** a file mixing synthetic and real origin, **When** validated, **Then** it is rejected because a dataset cannot mix origins.

---

### User Story 5 - Large files import in the background (Priority: P2)

A buyer uploads a large file and is not blocked: files above the in-request limit are queued, progress and result are visible in an import status section, and a retry is safe.

**Why this priority**: Real files may be large; a frozen screen pushes people away from the governed path. Small files work without it.

**Independent Test**: Submit a synthetic file above the in-request row limit and below the hard cap; verify an immediate "sent to background" message, visible stages, a final result, and that repeating the submission creates no second dataset.

**Acceptance Scenarios**:

1. **Given** a file above the in-request row limit, **When** it is submitted, **Then** the buyer is told at once it runs in the background and sees its stage (queued, parsing, validating, ready, failed) with timings.
2. **Given** the same file or action submitted twice, **When** the second arrives, **Then** no duplicate dataset, rows or activation results are created.
3. **Given** a job that fails midway, **When** the buyer opens it, **Then** a Spanish failure reason and a retry are shown and no partial dataset is active.
4. **Given** an idle platform, **When** no job is queued, **Then** no dedicated compute is running for this feature.

---

### Edge Cases

- Empty file, header-only file, more rows than the hard cap, wrong type, or a type that does not match the file's real content: rejected before parsing with a Spanish message.
- Excel file with macros, formulas, external links, hidden sheets or a decompression bomb: rejected; formulas are never evaluated.
- CSV with another delimiter or encoding, or Spanish number and date formats: read correctly or rejected with a precise message; never silently reinterpreted.
- Negative, non-numeric, absurdly large quantity, or a date outside the allowed horizon: row quarantined with a reason.
- SKU that matches a discontinued product, two products by case or whitespace variants, or two products with exactly the same SKU: sent to quarantine as ambiguous, never resolved to either product.
- Dataset activated, then a SKU is retired from the catalogue: affected rows are flagged and stop contributing without altering the dataset's history.
- Two people act on the same dataset at once, or two activations or two rollbacks race: exactly one succeeds; the other sees a clear conflict message.
- Rollback requested for a dataset that is not active: refused, nothing changes.
- Cells or exports beginning with a formula prefix: neutralised so a downloaded quarantine list cannot execute anything.
- Files with free-text notes, tax identifiers or personal data: those columns are discarded at load; they are never stored, logged or shown.

## Requirements *(mandatory)*

### Functional Requirements

**Audit and baseline**

- **FR-001**: The work MUST begin with an audit of the latest main branch that records, for each capability in this spec, whether it is complete, partial, broken, missing or unverified, with file and line evidence, and MUST reuse working code instead of rebuilding it.

**Import, templates and mapping**

- **FR-002**: Buyers and admins MUST be able to upload a seed file in CSV or Excel format from the web interface; viewers MUST NOT. Files recognised as ERP exports (inventory, movements or supplier export shapes) MUST be refused as seed files with a Spanish message.
- **FR-003**: The system MUST offer downloadable CSV and Excel templates in Spanish with required and optional columns documented and fictional example values only.
- **FR-004**: The system MUST validate files by type (including by content), size, row count and required columns before parsing, and MUST reject spreadsheets with macros, external links, formulas or decompression beyond the feature 002 caps (file size, rows, columns, sheets, expanded size); formulas MUST never be evaluated.
- **FR-005**: The system MUST let the user map file columns to expected fields and save the mapping for reuse.
- **FR-006**: The system MUST accept Spanish number and date formats, store quantities and any money as exact decimals, keep original date text beside a normalised UTC value, and never silently correct invalid values.

**Matching, duplicates and quarantine**

- **FR-007**: The system MUST match each row to a product by SKU through the synchronised catalogue; users see and supply SKUs only, never ERP internal ids. A SKU that matches more than one product, whether written identically or differing only by upper/lower case or spaces, MUST NOT be resolved to any of them: every row carrying it goes to quarantine as ambiguous.
- **FR-008**: The system MUST detect duplicate rows within a file and against the product's other seed data and present them for decision; none is chosen silently.
- **FR-009**: The system MUST put every malformed, ambiguous or unmatched row in quarantine with file, row number and Spanish reason, MUST never drop a row silently, and MUST offer the quarantine list as a download with formula prefixes neutralised.
- **FR-010**: The system MUST discard free-text notes, tax identifiers and personal data from files at load time and MUST NOT store, log, display or use them.

**Provenance and origin**

- **FR-011**: Every seed value MUST carry exactly one provenance label from observed, estimated or manual; a row with no stated label MUST be quarantined with a reason (never defaulted to a label), so no ambiguous value becomes trusted input.
- **FR-012**: Every dataset MUST carry an origin flag (synthetic or real) and MUST NOT mix origins.
- **FR-013**: Where actual ERP demand covers a day, it MUST prevail over any seed value for that day, and the overlap MUST be reported to the user.

**Preview, dry run, activation, rollback**

- **FR-014**: The system MUST show a preview before activation with counts, a row sample, provenance mix, origin and an explicit statement that nothing has changed yet.
- **FR-015**: The system MUST provide a dry run comparing forecast and stockout/overstock outcomes with and without the dataset, MUST change no stored forecast, proposal, stock figure or ERP data, and MUST list products with too little history as not assessable.
- **FR-016**: Activation MUST require buyer or admin role, fresh multi-factor authentication and a person other than the dataset's uploader and the person who chose its mapping or ran its validation; the only exception is an owner/admin self-activation with a reason (one choice from a short list, plus an optional short free-text detail), recorded distinctly in the audit. Activation MUST be atomic, audited, supersede the previously active dataset and queue a versioned forecast run recording the dataset version.
- **FR-017**: After activation, forecast runs for covered products MUST use the dataset only under the rescue rule in the Context (sole reason "new", density at least half, combined history reaches the minimum), MUST flag the product as using seed data, and MUST leave other products unchanged.
- **FR-018**: Forecast and proposal explanations MUST state when seed data contributed, which dataset and version, and the provenance of the values.
- **FR-019**: Buyers and admins MUST be able to roll back an active dataset with fresh multi-factor authentication and a reason (one choice from a short list, plus an optional short free-text detail); two rollbacks at the same moment MUST end with exactly one success and a clear conflict message for the other; rollback MUST be atomic, audited, delete nothing, queue a versioned forecast run, and restore the previously active dataset (or no seed influence if there was none) so covered products' forecasts equal those obtained just before the activation, given unchanged ERP data.
- **FR-020**: Datasets MUST be versioned and immutable once validated; a correction MUST be a new dataset, and superseded, rolled-back and rejected datasets MUST stay viewable.

**Separation from the ERP**

- **FR-021**: Seed data MUST NEVER be written to the ERP, appear in any ERP-bound request, or be presented as an ERP movement, stock level or cost anywhere in screens or exports.
- **FR-022**: Seed data MUST be stored apart from ERP-derived demand so that removing every seed dataset leaves ERP-derived data exactly as it was.
- **FR-023**: Data loaded locally from the ERP's interface exports (feature 004) and seed data MUST each keep their own origin label and MUST NOT be mixed in a way that makes one appear to be the other.

**Background jobs**

- **FR-024**: A file up to the in-request row limit MUST be processed during the request; a larger one, up to the hard cap, MUST be queued with the buyer told at once, and an import status section MUST show each import's stage, timings and any error. For a given file and catalogue the outcome (accepted and quarantined rows, with their reasons) MUST be the same whichever way it is processed.
- **FR-025**: Re-running any stage or resubmitting the same file or action MUST be idempotent: no duplicate dataset, rows or results.
- **FR-026**: A failed or interrupted job MUST leave no partially active dataset and MUST show a Spanish failure reason and a retry option.
- **FR-027**: Jobs MUST respect concurrency and size caps, and no dedicated compute may run when no job is queued.

**Security, audit and language**

- **FR-028**: Viewers MAY read lists and details; buyers and admins MAY upload, map, validate and dry-run; activation and rollback follow FR-016 and FR-019. Every refused attempt MUST be recorded.
- **FR-029**: Every state change (upload, validation, mapping, dry run, approval, activation, rollback, rejection) MUST be audited with actor, UTC time and dataset version, without file contents or free text (a chosen reason is recorded as its pick-list value, never the free-text detail).
- **FR-030**: Uploads MUST be treated as hostile: authenticated, protected against cross-site request forgery, size and type limits, signature check, safe parsing, no execution of file content; abuse MUST be refused and recorded.
- **FR-031**: The whole interface for this feature MUST be Spanish (es-ES) only, with EUR and Spanish date and number formats and no hard-coded user-facing strings.
- **FR-032**: Committed tests, fixtures and demonstrations MUST use synthetic data only.
- **FR-033**: A reason for a rollback or an owner/admin self-activation MUST be one choice from a fixed short list (rollback: wrong figures, wrong file, test, replaced by a newer file, other; self-activation: only person available, urgent need, other), plus an optional free-text detail of at most 100 characters. Everyone who can open the dataset list sees the chosen reason; only admins see the detail; the audit trail never holds the detail.

### Key Entities *(include if feature involves data)*

- **Seed Dataset**: a versioned unit with kind (observed external, estimated, manual forecast), origin (synthetic or real), state (uploaded, validated, active, superseded, rolled back, rejected), file reference and checksum, mapping used, uploader, approver, UTC timestamps, counts and provenance mix.
- **Seed Row**: one quantity for one product and day, with SKU as supplied, resolved product, original date text, provenance label, file row number and outcome.
- **Quarantine Entry**: a row that could not be accepted, with file, row number and Spanish reason.
- **Column Mapping**: a saved association between file columns and expected fields.
- **Import Job**: a background unit with stage, timings, idempotency key, result and failure reason.
- **Dry-Run Result**: per-product and total comparison with and without a dataset, including not-assessable products and the age of the data used.
- **Activation Record**: who activated or rolled back which version, when, why, and, for a rollback or an owner/admin self-activation, the chosen reason (and the short detail, visible to admins only).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the synthetic test set, after activation 100% of rescuable covered products have a different next forecast flagged as using seed data, and 100% of uncovered products are unchanged.
- **SC-002**: On the synthetic test set, after rollback 100% of covered products' forecasts equal their pre-activation values.
- **SC-003**: Automated checks over the full flow find zero seed values presented or sent as ERP movements, stock or costs.
- **SC-004**: A buyer can complete a seed import from template to activation for a 1,000-product file in under 15 minutes and roll it back in under 2 minutes.
- **SC-005**: 100% of malformed, ambiguous (including SKUs shared by two products), unmatched and duplicate rows in a test file appear in the preview or quarantine with a reason; zero rows are lost.
- **SC-006**: A file at the hard row cap finishes validation within 5 minutes while every screen request still answers within 2 seconds, and resubmitting it creates no second dataset.
- **SC-007**: Every seed value shown carries exactly one provenance label, and 100% of explanations that used seed data name the dataset and version.
- **SC-008**: 100% of attempts to activate or roll back by a viewer, by the uploader or validator acting alone (without the audited owner/admin override), or without fresh multi-factor authentication are refused and recorded.
- **SC-009**: All hostile-file tests (macros, formulas, external links, decompression bombs, mislabelled type, formula-prefix injection, oversized files) pass, with zero execution of file content and zero leakage of free-text or personal data.
- **SC-010**: The feature adds no always-on compute and no idle cost.
- **SC-011**: The audit of the main branch is delivered as a table of capabilities with status and file evidence, and every capability marked partial, broken, missing or unverified is resolved or explicitly listed as a known limitation in the pull request.
- **SC-012**: A test file produces the same accepted and quarantined counts and the same reasons whether it is checked during the request or in the background, and every row whose SKU matches two products is quarantined as ambiguous.

## Assumptions

- Roles are the existing buyer, admin and viewer; no new roles are introduced.
- The catalogue is already synchronised and SKUs resolve through it; surrogate-id data from feature 004 stays separate.
- Forecasting methods exist (feature 001); this feature changes only the governed seed input, its dry-run comparison and its explanations.
- A seed dataset carries daily demand quantities per product; prices and supplier data are out of scope.
- Limits (in-request row limit about 10,000 rows, hard cap about 50,000, file size, concurrency, minimum history) follow feature 002 and are confirmed in planning.
- Only one dataset is active at a time; activating another supersedes the current one (ADR-020), so overlap between active datasets does not arise.
- Self-approval is refused for activation (project rule: approver is not the creator or last editor, read here as the uploader or validator), except the audited owner/admin override in FR-016 for a one-person shop.
- Seed files are the owner's own estimates, not ERP exports, so real-origin seed files may be uploaded in the cloud under ADR-020 (private container, origin flag); ERP exports stay local-only under the constitution.
- Shared API contracts and integration are coordinated with Agent 00; this feature changes only the forecast and gateway seed-import areas and the matching interface screens, and does not edit files owned by other agents.
- No production deployment, merge to main, destructive operation or real ERP write is part of this work.
- The feature directory is `008-mmi-7-…` (Jira key plus number 008) because lower numbers are already taken by parallel agents' specs.
- The ERP does not guarantee that SKUs are unique, and the platform does not assume it (the inventory data has no uniqueness rule on SKU).
- The 100-character limit and the admins-only visibility of the free-text detail are defaults chosen when recording the owner's "pick list and short free text" decision; they can be changed without changing the pick-list rule.
