# Feature Specification: SKU in the policy history of the administration status

**Feature Branch**: `claude/jira-mmi-14-spec-edc3ba` (spec directory `014-policy-history-sku`)

**Created**: 2026-11-16

**Status**: Draft

**Input**: User description: "implement spec for jira MMI-14" — SKU in the policy history of GET /admin/status so the administration screen never shows the Siweb variant id (Jira MMI-14, epic MMI-1; owner request 2 of `specs/012-ux-navigation-localization/evidence/owner-requests.md`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Administrator reads the policy history by SKU (Priority: P1)

An administrator opens the administration status screen and reads the history of purchasing-policy overrides. Each row that refers to a product shows the product's SKU, the code the pharmacy staff already use. No internal Siweb number appears anywhere in the column.

**Why this priority**: This is the whole request. Project rule 5 says people see and enter the SKU and never the Siweb id; today the history column is a known exception that feature 012 had to record in a baseline because the data does not carry the SKU.

**Independent Test**: Seed the history with synthetic overrides that point at catalogue products, open the screen as an administrator, and check that every product row shows its SKU and that no variant id is visible.

**Acceptance Scenarios**:

1. **Given** a policy history row for a product that exists in the synced catalogue, **When** the administrator opens the status screen, **Then** the row shows that product's SKU.
2. **Given** several rows for different products, **When** the screen loads, **Then** each row shows its own SKU, and the SKU matches the catalogue entry for that product.
3. **Given** the screen is rendered, **When** the page content is inspected, **Then** the Siweb variant id is not displayed in the policy history column.

---

### User Story 2 - Rows without a resolvable SKU stay readable (Priority: P2)

Some history rows cannot show a SKU: the row is not about a single product (for example a category or global policy), or the product is no longer in the catalogue. The administrator still sees the row, with a clear "no SKU" state, and the screen does not fail.

**Why this priority**: History is an audit trail; a missing SKU must never hide or break a row (project rule 6, never drop data silently).

**Independent Test**: Seed one row without a product reference and one whose product is absent from the catalogue; load the screen and confirm both rows appear with the empty-SKU marker.

**Acceptance Scenarios**:

1. **Given** a history row with no product reference, **When** the screen loads, **Then** the row is shown and the SKU cell displays the Spanish "not applicable" marker.
2. **Given** a history row whose product cannot be resolved to a SKU, **When** the screen loads, **Then** the row is shown with the same marker and the other cards on the screen are unaffected.

---

### User Story 3 - Contract and guardrails reflect the change (Priority: P3)

The owner of the service updates the shared contract first, so that consumers, generated types and contract tests describe the new SKU field, and the web screen's temporary exception for the variant id is removed.

**Why this priority**: The project is contract-first (rule 9); without the schema change and the removed baseline entry the fix is not verifiable or protected from regression.

**Independent Test**: Run the contract gate and the web unit test that scans for variant-id display; both pass with the baseline entry for this screen removed.

**Acceptance Scenarios**:

1. **Given** the updated schema, **When** the contract tests run, **Then** a history row with a SKU, one with a null SKU and one without the field (an older producer) are accepted, and a SKU that is not text or is empty is rejected.
2. **Given** the web baseline of known variant-id displays, **When** this feature lands, **Then** the entry for the policy history column is gone and the display test still passes.

---

### Edge Cases

- The same product appears in many history rows: every row shows the same SKU.
- The product's SKU changes in the catalogue after the override was made: the row shows the SKU current in the catalogue at read time (A3).
- The history is empty: the card shows its existing empty state and nothing else changes.
- The service that owns the history is unavailable: the card shows its existing "unavailable" state; no partial or id-only rows are shown.
- Surrogate ids (9,000,000 range) from locally loaded UI exports: rows resolve to their SKU like any other, and the surrogate id is never shown.
- A SKU value that is empty or whitespace is treated as unresolved (null), never shown as blank.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every policy history row returned to the administration status screen that refers to a product MUST include a `sku` value next to its internal product identifier.
- **FR-002**: The `sku` value MUST be the SKU of that product in the synced catalogue at the time of the request, and MUST be `null` when the row has no product reference or the product cannot be resolved.
- **FR-003**: The administration screen MUST show the SKU in the policy history column and MUST NOT display the Siweb variant id there or anywhere on the screen.
- **FR-004**: Rows with a null SKU MUST still be listed, with a Spanish "not applicable" marker, so no history is hidden.
- **FR-005**: The SKU MUST be resolved by the service that owns the product data, not by the gateway; the gateway only passes the field through and does no resolution or arithmetic (ADR-023).
- **FR-006**: The JSON Schema for the history row MUST be updated before any code, and the generated types and contract tests MUST cover a row with a SKU, a row with a null SKU, a row without the field (accepted, because the change is additive), and a SKU that is a number or an empty string (refused).
- **FR-007**: The entry for the policy history column MUST be removed from the web variant-id baseline, and the test that scans for variant-id display MUST keep passing.
- **FR-008**: The change MUST be additive: existing consumers that ignore unknown fields keep working, and the existing variant identifier stays in the payload for API use.
- **FR-009**: Resolving SKUs MUST NOT add a request to Siweb, store new personal or free-text data, or change what the history records.
- **FR-010**: Any new user-facing text (the "not applicable" marker and its accessible label) MUST be in the es-ES catalogue, with no hard-coded strings.

### Key Entities

- **Policy history row**: One recorded change or state of a purchasing-policy override; has a status, a scope, timestamps, and, when about a single product, a product reference.
- **Product reference**: The internal identifier of a catalogue product (Siweb `variant_id`, or a surrogate id for locally loaded data); used only between services, never shown to people.
- **SKU**: The code people see and type for a product; resolved from the product reference via the synced catalogue.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of policy history rows that refer to a catalogue product, the administrator sees the SKU and no Siweb id.
- **SC-002**: 0 occurrences of the variant id in the rendered administration status screen, verified by the automated display test with no remaining exception for this screen.
- **SC-003**: 100% of rows without a resolvable SKU remain visible with the "not applicable" marker; the number of rows shown equals the number of rows in the history.
- **SC-004**: The administration status screen loads with no perceptible slowdown: opening it with a history of 200 rows takes no longer than before the change plus 0.5 seconds.
- **SC-005**: The contract gate and all contract tests pass, including the row cases in FR-006.

## Assumptions

- **A1**: The policy history is served by the procurement service (the gateway forwards `GET /policy-overrides` to it), so procurement owns the change; the Jira note said "owner to confirm"; Agent 00 confirmed on PR 27 that procurement (`policy_override_request`, owner `procurement-service` in the matrix) owns it.
- **A2**: Procurement already keeps the SKU next to the product reference (Jira MMI-15 states this for `product_refs`), so no new synchronisation with Siweb is needed.
- **A3**: The SKU shown is the current catalogue SKU at read time, not a snapshot taken when the override was made.
- **A4**: Only the policy history in `GET /admin/status` is in scope. Scenario changes and lines (MMI-15) and the product-supplier terms route (MMI-16) are separate features.
- **A5**: Only administrators can reach this screen; roles, MFA and audit behaviour are unchanged.
- **A6**: The new field is nullable and optional in the schema (so older producers stay valid, FR-008): null for rows without a product or an unresolved one, a string otherwise; the current procurement service always sends it; the contract version bump follows the integration README.
- **A7**: Tests use synthetic fixtures from `packages/testing` only.
