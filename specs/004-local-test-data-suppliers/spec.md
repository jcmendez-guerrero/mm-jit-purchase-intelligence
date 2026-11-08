# Feature Specification: Local Test Data Loading and Supplier Management

**Feature Branch**: `004-local-test-data-suppliers`

**Created**: 2026-11-08

**Status**: Draft

**Input**: User description: "Local-only test data and supplier management: load inventory, stock and movements from the same file formats the ERP's user interface exports, using the product code (SKU) as the main identifier; let buyers and admins add and configure suppliers and their purchasing conditions from the UI; use synthetic data shaped like the real exports for committed tests; real exports never committed or sent to the cloud."

## Context

The platform normally receives data from the ERP through its programming interface. That interface identifies products by an internal variant ID that staff cannot see anywhere in the ERP's user interface, while every export staff can produce identifies products by **SKU**. To test the whole system (demand, forecasting, proposals) with the owner's own current data before the ERP connection is validated, the platform needs a **local-only test path** that loads the three exports staff can produce: the inventory list, the stock-movements list and the supplier list. Separately, the platform today has no screen to create a supplier or define how it buys from them, so a buyer cannot configure the conditions the proposal engine relies on.

Out of scope: any ERP write other than the supplier-cost update of the main feature and the supplier-conditions note block defined in this feature (FR-027 to FR-032), sending orders to suppliers, loading real data in any cloud environment, and parsing free-text notes.

**Terms used in this spec**: *review list* is the single list in the data-quality screen where rows needing a person's decision appear, with two labelled sources (loader and platform); *quarantine* is the act of putting a row there; a *review item* is one entry; the *load result* is the set of counts shown after a load; *pending link in ERP* means a product or supplier has no real ERP id yet, so no ERP request is made.

## Clarifications

### Session 2026-11-08

- Q: Should real-file loading run only as a local command, or also as a screen upload? → A: Both: a local command and a screen upload, with the screen upload switched off (not reachable) in cloud configuration.
- Q: How do lead time, minimums and delivery conditions reach the ERP's supplier notes? → A: The app is the source of truth. The ERP holds only payment terms as structured data, and its notes can be edited by other tools or in the ERP console. The app writes its conditions into the supplier's ERP note as one clearly delimited, machine-readable block through the API, preserving all other note content untouched. On a discrepancy between the app and the block (or the ERP's payment terms) the buyer or admin gets an alert and decides which value is current. **This adds a second, human-initiated ERP write and a limited reading of the note; it requires a constitution amendment and an allowlist change before planning proceeds (see Assumptions).**
- Q: When the inventory export names a supplier for a product, should loading link them automatically? → A: Yes, only on an exact single match of the supplier name (ignoring case and accents); no match or several matches go to the review list (FR-033).
- Q: When a newer inventory export is loaded over existing products, what does it overwrite? → A: Stock quantities and descriptive data (name, category, brand, status) are overwritten from the file; costs, reorder points and target stock edited by a person in the app are kept and any difference is shown for the buyer to accept or ignore (FR-034).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Load inventory and stock from ERP exports locally (Priority: P1)

The owner places the inventory export (products and current stock) and the stock-movements export in a private local folder and loads them into a locally running copy of the platform. Products are identified by SKU. After loading, the dashboard, demand, forecasts and proposals work on that data exactly as they would with ERP-collected data.

**Why this priority**: Nothing else can be tested end to end without data shaped like the real business. It unblocks every other validation.

**Independent Test**: Load a synthetic inventory file and a synthetic movements file (same columns and formats as the real exports) into a clean local environment and verify the product count, stock totals and movement counts match the files, and that the dashboard shows them.

**Acceptance Scenarios**:

1. **Given** an inventory export with products, prices, costs, stock available/reserved/total, reorder point, target stock, status and lot, **When** it is loaded, **Then** each distinct SKU becomes one product with its stock, and the count loaded plus the count quarantined equals the number of data rows.
2. **Given** a movements export with date, SKU, warehouse, lot, expiry, type, reason, quantity and reference, **When** it is loaded after the inventory, **Then** movements are attached to products by SKU, reasons are mapped to the platform's movement reasons, and demand is computed as sales shipments minus customer returns.
3. **Given** a movement whose SKU is not in the loaded inventory, **When** loading, **Then** the row is placed in the review list with the reason, not dropped and not guessed.
4. **Given** the same files are loaded twice, **When** the second load finishes, **Then** no duplicate products or movements exist (the load is repeatable).
5. **Given** dates in the exports' Spanish day/month/year format, a 3-digit-year expiry, a missing lot, or a missing warehouse, **When** loading, **Then** valid rows are converted correctly (original text kept, normalised time stored) and malformed ones go to the review list.
6. **Given** a free-text notes column, **When** loading, **Then** only a "has note" indicator is kept and the text is never stored or used.

---

### User Story 2 - Create and configure suppliers from the UI (Priority: P1)

A buyer or admin opens the suppliers screen and adds a new supplier (commercial name, fiscal type, country, currency, payment terms, contact channel for orders), edits it later, and can deactivate it so it is no longer proposed. For each supplier they configure purchasing conditions: lead time, minimum order value or quantity, free-delivery threshold and delivery charge, order days. For each product they link the supplier, set its cost (with the Recargo de Equivalencia option), pack size/multiple and supplier product reference.

**Why this priority**: Today no supplier can be configured, so the proposal engine has nothing to allocate lines to. It is a blocker for real use, not only for testing.

**Independent Test**: In the UI, create a supplier, set its conditions, link two products with costs and pack sizes, generate a proposal, and verify lines for those products are allocated to that supplier honouring minimums and multiples; then deactivate the supplier and verify it is no longer proposed.

**Acceptance Scenarios**:

1. **Given** a buyer on the suppliers screen, **When** they add a supplier with the required fields, **Then** it appears in the list, is available for product linking, and the creation is recorded with who and when.
2. **Given** a supplier with a name duplicating an existing active supplier, **When** saving, **Then** the user is warned and must confirm or change it.
3. **Given** a supplier, **When** the buyer edits lead time, minimums, delivery threshold, payment terms or currency, **Then** the change is versioned and the next proposal uses it; earlier approved proposals are unchanged.
4. **Given** a product-supplier link with a cost entered without Recargo, **When** the buyer saves, **Then** the Recargo-inclusive cost is shown (1.4% for 10% VAT, 5.2% for 21% VAT) and the link follows the existing cost-provenance rules.
5. **Given** a supplier created in the platform with no counterpart in the ERP, **When** the buyer enters a cost, **Then** the pair is flagged "pending link in ERP" and no ERP request is made.
6. **Given** a supplier with open (non-exported) proposal lines, **When** an admin deactivates it, **Then** the user sees the affected lines and must confirm; the lines are flagged for reallocation, nothing is silently removed.
7. **Given** a viewer role, **When** they open suppliers, **Then** they can read but not add, edit or deactivate.

---

### User Story 3 - Import the supplier list from an export (Priority: P2)

The owner loads the supplier export locally to seed suppliers instead of typing them. Rows marked as customers are excluded; rows that are clearly not purchasing suppliers (utilities, software, insurance, telecoms) can be flagged as "non-purchasing" so they never appear in proposals but remain available for reference.

**Why this priority**: A convenience on top of Story 2; the real export mixes real merchandise suppliers with expense vendors and customers.

**Independent Test**: Load a synthetic supplier file containing suppliers, a customer row, duplicate-name rows, a foreign supplier with another currency and rows missing tax IDs; verify counts by category and that no tax ID or note text is stored.

**Acceptance Scenarios**:

1. **Given** rows with relationship type "Cliente", **When** importing, **Then** they are skipped and counted as excluded.
2. **Given** two rows with near-identical names (differing in accent or case), **When** importing, **Then** they are shown as possible duplicates for the buyer to merge or keep, never merged automatically.
3. **Given** a row with a non-EUR habitual currency, **When** importing, **Then** the currency is kept on the supplier and costs in that currency are not mixed with EUR without an explicit conversion.
4. **Given** a payment-terms value in free form ("7 días", "30"), **When** importing, **Then** it is converted to a number of days where unambiguous, otherwise left empty and listed for review.
5. **Given** tax ID, bank and IBAN columns and a notes column, **When** importing, **Then** they are discarded, and only a "has note" indicator is kept.
6. **Given** the buyer reviews the imported list, **When** they mark suppliers as purchasing or non-purchasing, **Then** the choice is saved and non-purchasing suppliers are excluded from proposals.

---

### User Story 4 - Safe synthetic fixtures and a local-only guarantee (Priority: P1)

A developer or the owner generates a synthetic inventory, movements and supplier set shaped like the real exports (same columns, formats, quirks and mix of products) with fictional names and SKUs. These are the only files that may be committed and used by automated tests. Real files are read only from a private local folder that is ignored by version control, and the real-file loading capability does not exist in any cloud deployment.

**Why this priority**: The repository is public and handles a real business's data; this protects the owner and keeps cloud costs and exposure at zero.

**Independent Test**: Generate the synthetic set, run the load tests against it, then run the repository safeguards (ignored paths, secret and data scanning) and the cloud configuration checks and verify none contain or enable real-file loading.

**Acceptance Scenarios**:

1. **Given** the generator, **When** run twice with the same seed, **Then** it produces identical files that include the quirks of the real exports (cost and price variations, lots with and without expiry, malformed expiry, unreferenced sales, duplicate-looking suppliers, customer rows, foreign suppliers).
2. **Given** a real export copied into the repository by mistake, **When** the safeguards run, **Then** the change is blocked before commit.
3. **Given** a cloud environment configuration, **When** the deployment checks run, **Then** the local file-loading capability is absent or disabled and any attempt to use it is refused and recorded.
4. **Given** a local load, **When** it completes, **Then** nothing is sent outside the local machine and no cloud storage or database is touched.
5. **Given** the local load tools, **When** pointed at a file inside the repository tree, **Then** they refuse unless it is under the synthetic fixtures location.

## Edge Cases

- Inventory SKU repeated on several rows (different lots): stock is summed per SKU and lots kept separately; conflicting prices or costs for the same SKU are flagged.
- SKU with different spelling or surrounding spaces/case between inventory and movements files: normalised for matching and the original kept.
- Product status inactive/discontinued but with stock or recent sales: loaded and flagged, not hidden.
- Negative stock, zero cost, or cost above price: loaded, flagged in data quality.
- Reserved stock higher than total: flagged, not corrected.
- Movements file spanning only a short period: the platform marks products as not eligible for forecasting rather than producing unreliable numbers.
- Decimal separators and thousands formats in Spanish locale, and quantity signs (outbound negative).
- File too large, wrong file type, extra or missing columns, header renamed, unexpected encoding: rejected with a clear Spanish message listing what is missing.
- Rows in a supplier file lacking tax ID, email or address: still importable (those fields are not needed).
- Supplier name containing a personal name (self-employed supplier): treated as ordinary data, never used in logs or examples.
- Two suppliers sold under the same group (e.g., different legal entities, same trade name): kept separate unless the buyer merges them.
- A product linked to a deactivated supplier: link kept for history, not offered for new proposals.
- The ERP note is edited in the ERP console or by another tool at the same moment as the app writes: the app re-reads before writing, detects the change, and asks for confirmation instead of overwriting.
- The note contains personal or unrelated information (for example about customers or pets): it is never stored, logged or shown by the app, and is written back unchanged.
- Inventory export where every supplier cell is empty: loading succeeds, products have no supplier link, and the bulk assignment tool (FR-035) is the route to a usable proposal.
- Supplier IDs in the supplier export are the ERP's contact numbers: they are kept as the supplier's ERP reference so later cost updates can target the right contact; this correspondence is verified in Gate 0 before any write.
- Movement timestamps arrive as local day/month/year text without seconds or time zone: they are interpreted as Spanish local time and the original text is kept.
- Switching from locally loaded data to ERP-collected data is not supported in this feature: the connector refuses to run against the real ERP while locally loaded products exist, and the owner must wipe the local data first (FR-038). Matching SKU-keyed local products to ERP variants is a follow-up feature.

## Requirements *(mandatory)*

### Functional Requirements

**Local data loading**

- **FR-001**: System MUST load a product catalogue and current stock from an inventory export file whose columns match the ERP's inventory export, identifying products by SKU.
- **FR-002**: System MUST load stock movements from a movements export file (Excel) whose columns match the ERP's movements export, attaching each to a product by SKU.
- **FR-003**: System MUST identify products by SKU everywhere people see or supply them (screens, search, exports, uploaded files, bulk assignment, messages) and MUST use the ERP's own ids only when calling the ERP's API, resolving them from the SKU through the synchronised catalogue. Locally loaded data has no ERP ids: the ids the platform assigns to it stay inside the platform.
- **FR-004**: System MUST map the exports' Spanish movement types and reasons to the platform's movement reasons and MUST list any unmapped value in the review list instead of guessing.
- **FR-005**: System MUST make loading repeatable: loading the same file again MUST NOT create duplicate products, movements or suppliers.
- **FR-006**: System MUST send every malformed, ambiguous or unmatched row to the review list with the file, row number and reason, and MUST show counts loaded, updated, unchanged, quarantined, excluded and services after each load. The review list has two labelled sources shown together in the data-quality screen: rows the loader cannot express in the platform's input shape (unmapped type or reason, unknown SKU, unreadable values) and rows quarantined by the platform's own checks (for example malformed expiry or missing warehouse), which the loader passes through unchanged so the normal quarantine handles them.
- **FR-007**: System MUST keep original timestamp text and a normalised UTC value, and MUST handle the exports' day/month/year dates, including invalid expiry dates, without silent correction.
- **FR-008**: System MUST store money as exact decimals, honouring Spanish number formats on input.
- **FR-009**: System MUST discard free-text notes (keeping a "has note" indicator), tax identifiers, and bank details at load time.
- **FR-010**: System MUST validate files by type, size, row count and required columns before parsing and MUST reject spreadsheets with macros, external links or formulas.
- **FR-011**: Users with the buyer or admin role MUST be able to run a local load both from a documented local command and from an upload in the web screen, and see its result in the interface; viewers MUST NOT. The screen upload MUST be available only when the platform runs in the local environment; in any cloud configuration the upload control MUST NOT be shown and the receiving capability MUST NOT be reachable (requests are refused and recorded).

**Supplier management**

- **FR-012**: Buyers and admins MUST be able to create, edit and deactivate suppliers from the interface; reactivation MUST be possible.
- **FR-013**: A supplier MUST capture commercial name, fiscal type (national, intra-community, foreign), country, currency, payment terms in days, order contact channel, and purchasing/non-purchasing classification; tax ID, bank and IBAN MUST NOT be captured.
- **FR-014**: Buyers and admins MUST be able to set per supplier: lead time, minimum order value, minimum order quantity, free-delivery threshold, delivery charge, and order days, each versioned with who and when.
- **FR-015**: Buyers and admins MUST be able to link products to a supplier and set per link: cost (with the Recargo option), pack size/multiple, minimum quantity, supplier product reference and preferred rank, following the existing cost provenance and staleness rules.
- **FR-016**: System MUST show a supplier-created-in-platform without an ERP counterpart as "pending link in ERP" and MUST NOT send any request to the ERP for it.
- **FR-017**: System MUST ensure deactivated or non-purchasing suppliers are never proposed, while keeping history, and MUST show open proposal lines affected before deactivation is confirmed.
- **FR-018**: System MUST warn on possible duplicate suppliers (same name ignoring case/accents) and never merge them automatically.
- **FR-019**: System MUST import a supplier export locally, excluding rows of type customer, converting payment terms to days where unambiguous, keeping non-EUR currency per supplier, and letting the buyer classify suppliers as purchasing or non-purchasing after import.
- **FR-020**: Supplier screens MUST appear only in Spanish with EUR and Spanish date/number formats, with all texts coming from the interface text catalogue.
- **FR-021**: All supplier and link changes MUST be recorded in the audit trail; a person MUST NOT approve a proposal they created or last edited, unchanged from the main feature.

- **FR-033**: When the inventory export names a supplier for a product, the system MUST link the product to that supplier automatically only if the name (compared ignoring case, accents and surrounding spaces) matches exactly one supplier; names matching several suppliers or none MUST go to the review list and no link is created. The export's cost MUST be stored on the link with source "inventory export" and its load time as verification time, following the existing cost-provenance rules; a name matching a deactivated or non-purchasing supplier MUST also go to review.

- **FR-034**: When a newer inventory export is loaded over existing products, the system MUST overwrite stock quantities and descriptive data (name, category, brand, status) from the file, MUST keep costs, reorder points and target stock that a person edited in the app, and MUST list each such difference so the buyer can accept the file's value or ignore it; the counts of overwritten, kept and differing values are shown after the load.

- **FR-035**: Because an inventory export may carry no supplier name at all (the owner's current export has none), buyers and admins MUST be able to assign a supplier to many products at once: by filter (category, brand, free text on SKU/name), by a selection, or by uploading a two-column file of SKU and supplier name. Each assignment follows FR-033 matching rules, shows a preview (products affected, conflicts with existing links) before it is applied, and is audited.
- **FR-036**: Items of type service (not physical stock) MUST be loaded and shown but excluded from stock, demand, forecasting and proposals, and counted separately in the load result.
- **FR-037**: System MUST keep the export's cost per SKU as a reference value (refreshed on every load) that is the default cost when a product is linked to a supplier (source "inventory export"), and MUST make the export's selling price available to the margin check, so cost reviews and proposals work on locally loaded data. In FR-034, "cost" means the cost on a product-supplier link.
- **FR-038**: The ERP connector MUST refuse to run against the real ERP while locally loaded products (surrogate ids) exist in the target database, with a Spanish message telling the owner to wipe the local data first.
- **FR-040**: The platform MUST NEVER put a locally assigned id into a request to the ERP (path, query or body). A write or lookup for a product or supplier without a real ERP id MUST be refused before a request is built and shown to the user as "pending link in ERP", with the SKU as the reference.
- **FR-039**: Every call between the loader, the BFF and the platform services MUST use authenticated, audience-scoped service identities (the local issuer in the local environment); an unauthenticated or wrong-audience call is refused.

**Supplier conditions in the ERP note**

- **FR-027**: The app MUST be the source of truth for supplier conditions the ERP has no field for (lead time, minimum order value/quantity, free-delivery threshold, delivery charge, order days). After a buyer or admin changes them and reviews the change, the system MUST write them into the supplier's ERP note as a single delimited, versioned, machine-readable block, only after fresh multi-factor confirmation, and record the write in the audit trail.
- **FR-028**: When writing, the system MUST read the current note, replace only its own delimited block (or append one if absent) and leave every other character of the note unchanged; if the block markers are damaged or duplicated, the system MUST NOT write and MUST raise a review item.
- **FR-029**: The system MUST NOT store, log, display or use for decisions any note content outside its own block; outside content is held in memory only for the duration of the write and only a "has note" indicator is kept.
- **FR-030**: The system MUST detect discrepancies between the app, the ERP note block and the ERP's structured payment terms, show an alert to buyers and admins with both values, who/when changed each where known, and let them choose which is valid; nothing is overwritten until they decide.
- **FR-031**: If the ERP write fails or the supplier has no ERP counterpart, the pending sync MUST be shown visibly and retried or flagged "pending link in ERP", and the app's values MUST remain in force for proposals meanwhile.
- **FR-032**: The new ERP write MUST be limited to the supplier note of a single supplier per request, MUST be refused by the connector for any other target, and MUST be verified against a non-production supplier record before it can reach the real ERP.

**Safety of real data**

- **FR-022**: Real exports MUST NEVER be committed; version-control and commit safeguards MUST block spreadsheets, CSVs and archives outside the synthetic fixtures location, and local real-file loading MUST read only from a private, ignored local folder.
- **FR-023**: The capability to load real files (command and screen upload) MUST be absent or disabled in cloud configurations and MUST refuse and record any attempt to use it there; files uploaded through the screen locally MUST be processed in memory or in a private local folder and deleted after the load, never kept in cloud storage; no real or synthetic local-load data may be uploaded to cloud storage or databases.
- **FR-024**: System MUST provide a deterministic generator of synthetic inventory, movements and supplier files that mimic the real exports' columns, formats, volume, mix of products and quirks, using only fictional names, SKUs, suppliers and amounts.
- **FR-025**: Automated tests MUST use only the synthetic files; tests MUST NOT read the private local folder.
- **FR-026**: Documentation MUST explain how to prepare the private local folder and load real exports locally, and how to wipe the local data afterwards.

### Key Entities

- **Product (by SKU)**: Sellable item identified by SKU, with name, category, brand, unit, tax rate, sale price, cost, status, reorder point, target stock; optionally linked later to an ERP variant ID.
- **Stock position**: Current available, reserved and total quantity per product (and warehouse/lot where given).
- **Lot**: Batch identifier with optional expiry per product.
- **Stock movement**: Dated quantity change with type, reason, warehouse, lot, reference and a "has note" indicator.
- **Supplier**: Purchasing counterparty with commercial data, currency, payment terms, classification (purchasing / non-purchasing), status (active / deactivated), origin (created in platform / imported / ERP), ERP link state.
- **Supplier conditions**: Versioned lead time, minimums, free-delivery threshold, delivery charge, order days.
- **Product-supplier link**: Supplier's offer for a product: cost with provenance, pack multiple, minimum quantity, supplier reference, rank.
- **Load run**: A record of one load: files, counts by outcome, who ran it, when.
- **Review item**: A quarantined or flagged row with file, row, reason and resolution status.
- **Synthetic data set**: Versioned fictional files used for tests, produced by the generator.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can load the full inventory and movements exports (about 3,000 products and about 1,700 movements) and see the dashboard populated in under 5 minutes.
- **SC-002**: After any load, loaded + updated + unchanged + quarantined + excluded + service rows equal the file's data rows (100% accounted for across both review sources, zero silently dropped).
- **SC-003**: Reloading the same files produces zero duplicates.
- **SC-004**: A buyer can create a supplier, set its conditions and link a product with a cost in under 3 minutes without help.
- **SC-005**: A generated proposal never allocates a line to a deactivated or non-purchasing supplier (0 occurrences across the test set).
- **SC-006**: 100% of the committed data files are synthetic: the safeguards detect and block a real-shaped export placed anywhere outside the fixtures location.
- **SC-007**: The cloud deployment checks confirm the real-file loading capability is absent in 100% of cloud configurations, and a local load generates zero outbound network traffic.
- **SC-008**: The synthetic generator reproduces every column of the three real export formats and every listed quirk, verified by tests, with identical output for the same seed.

## Assumptions

- The owner is the only person loading real files, on their own machine, and the local environment is disposable.
- The three exports (inventory, movements, suppliers) keep the column layout seen in the owner's current exports; a changed layout is rejected with a clear message rather than guessed.
- The exports' "Tipo/Motivo" values map to the platform's 15 documented movement reasons; unseen values go to review.
- The movements export covers a short period, so forecast eligibility will be limited until more history is available; this is expected and not a defect.
- Existing roles apply: buyers and admins manage suppliers and loads; approvers and viewers do not.
- Existing rules for cost provenance, Recargo de Equivalencia, the single permitted supplier-cost update and "pending link in ERP" are reused unchanged.
- **Dependency (blocking for FR-027 to FR-032):** the project constitution and rules currently allow only one ERP write (supplier cost) and forbid parsing notes. The owner has decided to extend this to a supplier-note block; the constitution, the ERP call allowlist and the notes rule must be amended with the owner's approval, and whether the ERP's supplier update supports writing the note must be verified on a non-production record, before planning those requirements. Loading from local files (Stories 1 and 4) and the supplier screens without ERP sync (Stories 2 and 3) do not depend on it.
- Supplier orders are still placed manually by the buyer outside the platform.
- Prices in the export are tax-inclusive or not according to the export's tax flag; the interpretation is shown to the user and confirmed once per load.
