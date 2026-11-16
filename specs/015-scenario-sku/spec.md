# Feature Specification: SKU in scenario changes and result lines

**Feature Branch**: `claude/speckit-mmi-15-spec-724de9` (spec directory `015-scenario-sku`)

**Created**: 2026-11-16

**Status**: Draft

**Input**: User description: "implement specification from jira MMi-15" — the scenario changes and result lines carry the product SKU so the scenarios screen never shows the Siweb variant id (Jira MMI-15, epic MMI-1; owner request 3 of `specs/012-ux-navigation-localization/evidence/owner-requests.md`). Number 014 is already used by two other open specs (MMI-14 and MMI-16), so this directory takes 015.

## Clarifications

### Session 2026-11-16

- Q: Should `sku` always be present in a change or line, or may it be omitted? → A: Always present, `null` when unresolved; the schema marks it required and a missing field is rejected. If the frozen-baseline gate refuses a required field in v1, the contract moves to v2 (decided through Agent 00).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Buyer reads a scenario by SKU (Priority: P1)

A buyer opens a finished scenario and compares it with the baseline. In the list of changes (which products moved supplier or quantity) and in the result lines of each supplier order, every product is identified by its SKU, the code the pharmacy staff already use. No internal Siweb number appears.

**Why this priority**: This is the whole request. Project rule 5 says people see and type the SKU and never the Siweb id; today the scenarios screen is a recorded exception in the web baseline because the data carries only the id.

**Independent Test**: Create a scenario from synthetic data whose products have SKUs in the synced catalogue, open the scenarios screen, and check that every change row and every result line shows its SKU and that no variant id is visible.

**Acceptance Scenarios**:

1. **Given** a ready scenario with changes, **When** the buyer opens it, **Then** each change row shows the SKU of its product.
2. **Given** a ready scenario with supplier orders, **When** the buyer opens the line table of a supplier, **Then** each line shows the SKU of its product.
3. **Given** the scenarios screen is rendered, **When** its content is inspected, **Then** the Siweb variant id is not displayed in the change rows or the line table.
4. **Given** two scenarios that contain the same product, **When** both are opened, **Then** the product shows the same SKU in both.

---

### User Story 2 - Items without a resolvable SKU stay readable (Priority: P2)

A change or line may refer to a product whose SKU is not in the catalogue (removed, never synced, or a locally loaded product without one). The buyer still sees the row, with a clear "no SKU" marker, and the scenario neither fails nor loses the row.

**Why this priority**: A scenario is a decision aid and an audit record; a missing SKU must never hide a row or block the comparison (project rule 6, never drop data silently).

**Independent Test**: Build a scenario that includes one product with no SKU on record; confirm the scenario is ready, the row is listed with the marker, and totals are unchanged.

**Acceptance Scenarios**:

1. **Given** a change for a product with no SKU on record, **When** the scenario is opened, **Then** the row is listed with the Spanish "not applicable" marker.
2. **Given** a result line for a product with no SKU on record, **When** the scenario is opened, **Then** the line is listed with the same marker and its quantities and totals are correct.
3. **Given** an existing scenario created before this change, **When** it is opened, **Then** its lines show their SKU when the catalogue has one, and the marker otherwise; nothing breaks.

---

### User Story 3 - Contract and guardrails reflect the change (Priority: P3)

The owner of the procurement service updates the shared contract first, so consumers, generated types and contract tests describe the new SKU field, and the web screen's temporary exception for the variant id is removed.

**Why this priority**: The project is contract-first (rule 9); without the schema change and the removed baseline entries the fix is neither verifiable nor protected from regression.

**Independent Test**: Run the contract gate and the web unit test that scans for variant-id display; both pass with the scenarios entry removed from the baseline.

**Acceptance Scenarios**:

1. **Given** the updated schema, **When** the contract tests run, **Then** a change and a line with a SKU, and a change and a line with a null SKU, are accepted, and a change or line that lacks the field is rejected.
2. **Given** the web baseline of known variant-id displays, **When** this feature lands, **Then** the scenarios entry (2 places) is gone and the display test still passes.

---

### Edge Cases

- A change that exists only before or only after (product added or dropped by the scenario): the SKU is still shown.
- A scenario that the optimiser could not make feasible still lists its changes and lines with SKUs.
- The product's SKU changes in the catalogue after the scenario was created: the scenario shows the SKU current at read time (A3).
- A scenario with no changes: the empty state is unchanged.
- Surrogate ids (9,000,000 range) from locally loaded UI exports: they resolve to their SKU like any other, and the surrogate id is never shown.
- A SKU that is empty or whitespace is treated as unresolved (null), never shown as blank.
- Exporting a scenario keeps working and is unchanged: the CSV/Excel export already carries the SKU and the ERP-facing variant id column, as in the proposal export, so it is out of scope. Comparing scenarios keeps working; identical inputs still produce the identical result hash (the SKU is presentation data and does not change the optimisation).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every change in a scenario summary MUST include a `sku` value next to its internal product identifier.
- **FR-002**: Every result line of every supplier in a scenario MUST include a `sku` value next to its internal product identifier.
- **FR-003**: The `sku` value MUST be the SKU of that product in the synced catalogue at the time of the request, and MUST be `null` when it cannot be resolved.
- **FR-004**: The scenarios screen MUST show the SKU in the change rows and in the line table, and MUST NOT display the Siweb variant id in either place.
- **FR-005**: Rows with a null SKU MUST still be listed, with a Spanish "not applicable" marker, so no change or line is hidden.
- **FR-006**: The SKU MUST be resolved by the procurement service from data it already keeps; the gateway only passes the field through and does no resolution or arithmetic (ADR-023).
- **FR-007**: Scenarios created before this change MUST show SKUs when opened, without being recomputed and without changing their result hash, totals, quantities or status.
- **FR-008**: The JSON Schema for scenario changes and result lines MUST be updated before any code, with `sku` required and nullable (always present, `null` when unresolved), and the generated types and contract tests MUST cover a SKU, a null SKU and a missing field (rejected).
- **FR-009**: The scenarios entry (2 places) MUST be removed from the web variant-id baseline, and the test that scans for variant-id display MUST keep passing.
- **FR-010**: The change MUST be additive at the payload level: consumers that ignore unknown fields keep working, and the existing variant identifier stays in the payload for API use.
- **FR-011**: Resolving SKUs MUST NOT add a request to Siweb, store new personal or free-text data, or alter the optimisation, its inputs or its outputs other than the added field.
- **FR-012**: Any new user-facing text (the "not applicable" marker and its accessible label) MUST be in the es-ES catalogue, with no hard-coded strings.

### Key Entities

- **Scenario change**: One product whose supplier or quantity moved between the baseline and the scenario; has the before and after supplier and quantity, the reasons, and now the SKU.
- **Scenario result line**: One product line within a supplier's order in the scenario result; has quantity, unit cost, line total, clinical-critical flag, and now the SKU.
- **Product reference**: The internal identifier of a catalogue product (Siweb `variant_id`, or a surrogate id for locally loaded data); used only between services, never shown to people.
- **SKU**: The code people see and type for a product; resolved from the product reference via the synced catalogue.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of scenario changes and result lines that refer to a catalogue product, the buyer sees the SKU and no Siweb id.
- **SC-002**: 0 occurrences of the variant id in the rendered scenarios screen, verified by the automated display test with no remaining exception for this screen.
- **SC-003**: 100% of changes and lines without a resolvable SKU remain visible with the "not applicable" marker; the number of rows shown equals the number of rows in the scenario.
- **SC-004**: Opening a scenario of 200 lines takes no longer than before the change plus 0.5 seconds.
- **SC-005**: The contract gate and all contract tests pass, including the three cases in FR-008; the result hash of an unchanged scenario is identical before and after.

## Assumptions

- **A1**: Procurement owns scenarios (the Jira note names its scenario store); Agent 00 confirms the owner and registers the contract-matrix entry once it exists.
- **A2**: Procurement already keeps the SKU next to the product reference (Jira MMI-15 states this), so no new synchronisation with Siweb is needed.
- **A3**: The SKU shown is the current catalogue SKU at read time, not a snapshot taken when the scenario was created; this also makes older scenarios work (FR-007).
- **A4**: Only scenario changes and result lines are in scope. The policy history (MMI-14), the product-supplier terms route (MMI-16) and the data-quality items (MMI-13) are separate features.
- **A5**: Roles, MFA, audit behaviour and scenario computation are unchanged; the new field is read-only presentation data.
- **A6**: The new field is required and nullable: null when unresolved, a string otherwise. If the frozen-baseline gate does not accept a required field in v1, the contract version is bumped to v2 per the integration README.
- **A7**: Tests use synthetic fixtures from `packages/testing` only.
- **A8**: The related web task (T054 of feature 012) waits for this contract and removes the baseline entry; the user-facing screen change is part of this feature's done criteria per the Jira ticket.
- **A9**: The scenario export (CSV/Excel) is out of scope: it already has a SKU column and keeps its existing columns.
