# Feature Specification: SKU Route for Product-Supplier Overrides

**Feature Branch**: `claude/mmi-16-spec-implement-139980`

**Created**: 2026-11-16

**Status**: Draft

**Input**: User description: "implement spec for MMI-16" — Jira MMI-16 ("SKU route for the product-supplier overrides, so people stop typing the Siweb variant id", epic MMI-1, labels agent-08, mmi-012, rule-5, sku) and request 4 in `specs/012-ux-navigation-localization/evidence/owner-requests.md`. Numbers 010 to 015 are taken or reserved elsewhere (014 by PRs 27 and 31, 015 by PR 29), so this spec is **016**.

## Context

Project rule 5 says people see and enter the SKU; Siweb ids stay inside the platform. Feature 011 (PR 22) already moved the stocking, override and recommendation routes to the SKU ("the ERP variant id is resolved inside procurement and never shown"). One gap is left: the buyer's per-product, per-supplier commercial terms (the "product-supplier overrides") are still read and saved at an address that carries the numeric variant id, so the override screen asks the person to type that number. Feature 012 (MMI-10) changes only the web app, so the owner of the service has to change the route first.

This is a small, contract-first change: the same two operations (read the terms, save the terms), addressed by SKU, **replacing** the variant-id route in one step (as PR 22 did). The app has no production data, so there is no need to keep the old route alive. Behaviour, permissions, concurrency control and the terms themselves do not change.

In scope besides the service: the smallest web change that keeps the override screen working (it asks for the SKU, calls the SKU route, and its known-exception entries are removed). This overlaps feature 012 task T050 for that one screen; whichever lands second takes the other's version.

Out of scope: any change to what the terms contain or how they are used in proposals; other routes and screens that still use ids (policy and demand sections of T050); new roles; any ERP request.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read the product-supplier terms by SKU (Priority: P1)

A buyer (or viewer, approver, admin) asks for the product-supplier terms of a product with a supplier using the product's SKU and the supplier's identifier. They get the same terms as today, with no Siweb variant id anywhere in the answer.

**Why this priority**: Without the read route by SKU the screen cannot stop asking for the variant id.

**Independent Test**: Request the terms for a synthetic SKU and supplier; compare with the stored terms for that product; confirm the answer holds no variant id.

**Acceptance Scenarios**:

1. **Given** a synced product with a known SKU and a supplier that has terms for it, **When** a permitted user reads the terms by SKU, **Then** the terms (and the optional "as of" view) are returned as before, and no variant id appears.
2. **Given** a SKU that is not in the catalogue, **When** the terms are read, **Then** the request is refused with the stable error code `sku_unknown`, which has a Spanish message.
3. **Given** a SKU that matches more than one product, **When** the terms are read, **Then** the request is refused with `sku_ambiguous` and nothing is guessed.

---

### User Story 2 - Save the product-supplier terms by SKU (Priority: P1)

A buyer saves product-supplier terms for a product and supplier using the SKU. Saving keeps today's rules: buyer role only, version check (`If-Match`), idempotency key, audit.

**Why this priority**: Saving is the other half of the override screen; both are needed to remove the variant id from the person's view.

**Independent Test**: Save terms by SKU with a stale and a current version; replay the same idempotency key; check the audit entries show the SKU and no variant id.

**Acceptance Scenarios**:

1. **Given** a buyer and a known SKU, **When** the terms are saved with the current version, **Then** they are stored exactly as before and the answer carries the new revision and no variant id.
2. **Given** a stale version, **When** saving, **Then** the same refusal as today is returned (no change stored).
3. **Given** a viewer, approver or admin without the buyer role, **When** saving, **Then** the request is refused as today.
4. **Given** an unknown or ambiguous SKU, **When** saving, **Then** the request is refused with `sku_unknown` or `sku_ambiguous` and nothing is stored or audited as a change.

---

### User Story 3 - Remove the variant-id route and ask for the SKU on screen (Priority: P1)

The old variant-id route is removed in the same change. The override screen asks the person for the SKU and uses the SKU route, so no path takes a variant id and nobody types one.

**Why this priority**: Removing the route breaks the screen unless the screen moves with it; leaving the old route would keep the rule-5 gap.

**Independent Test**: Open the override screen as a buyer, enter a synthetic SKU, read and save terms; request the old path and see it is unknown.

**Acceptance Scenarios**:

1. **Given** this feature has landed, **When** a request is made to the old variant-id path, **Then** it fails as unknown and the contract matrix, schema and any generated API description no longer list it.
2. **Given** a buyer on the override screen, **When** they enter a SKU and a supplier, **Then** the terms are read and saved by SKU and no field asks for a numeric id.
3. **Given** an unknown SKU is entered, **When** the terms are requested, **Then** the Spanish message for `sku_unknown` is shown.

### Edge Cases

- A SKU with characters that need encoding in an address (spaces, slashes, accents): it is accepted and resolved exactly, never altered.
- A NUL byte in the SKU is refused before any route runs (existing guard, `invalid_input`).
- The supplier does not exist or has no terms for the product: same answers as today, only the product is addressed differently.
- A product exists but has no synced variant yet: treated as unknown (`sku_unknown`), not as a server error.
- Local-load products (surrogate ids from 9,000,000): the SKU resolves to the surrogate id inside procurement; the id is still never returned, and the existing "pending link" refusal for ERP requests is unaffected.
- The "as of" date: behaves as today (same format, same refusal for a bad value).
- The supplier has no terms for the product: the answer is the same empty view as today, only addressed by SKU.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The gateway MUST offer read and save of product-supplier terms addressed by SKU and supplier identifier.
- **FR-002**: The variant id MUST be resolved from the SKU inside procurement, from the synced catalogue, and MUST NOT appear in any request or response of the route, nor in its audit entries (saved and refused) or logs. The identifier used for idempotency and the internal change notification is internal and not shown to people.
- **FR-003**: An unknown SKU MUST be refused with the stable error code `sku_unknown`; a SKU matching several products with `sku_ambiguous`; both MUST have Spanish messages in the web catalogue.
- **FR-004**: Roles, version check (`If-Match`), idempotency key and audit behaviour MUST stay as they were before the change (viewer, buyer, approver and admin read; only the buyer saves).
- **FR-005**: The terms returned and stored MUST be identical to what the variant-id route returned and stored for the same product and supplier, and existing saved terms MUST stay reachable by their SKU.
- **FR-006**: The old variant-id route MUST be removed from the gateway, the procurement client and service, the contract matrix and any generated API description in this change, and the override screen MUST ask for the SKU.
- **FR-007**: The response schema, the contract matrix entries and, if the project publishes one, the generated API description MUST be updated first (contract-first) and be covered by contract tests; the matrix entries are registered through Agent 00.
- **FR-008**: Tests MUST use synthetic SKUs and suppliers only.

### Key Entities

- **Product-supplier terms** (also called overrides): the buyer's commercial terms for one product with one supplier (as already defined); now addressed by SKU.
- **SKU**: the product code people see and type; the only product key on the route.
- **Variant id**: the ERP identifier, internal to procurement and the connector; never shown.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A buyer reads and saves product-supplier terms using only the SKU: 0 steps ask for a numeric id.
- **SC-002**: 100% of the route's responses, audit entries and logs checked in tests contain no variant id.
- **SC-003**: For every synthetic product and supplier in the test fixtures, the terms read by SKU equal the stored terms (0 differences).
- **SC-004**: An unknown or ambiguous SKU is refused with a stable code that shows a Spanish message in 100% of cases checked.
- **SC-005**: 0 gateway routes for product-supplier terms take a variant id in the path, and the override screen has 0 fields asking for a numeric id (verified by the contract matrix and the existing id-display checks).

## Assumptions

- The SKU lookup used by the stocking, override and recommendation routes (PR 22) is reused; `sku_unknown` and `sku_ambiguous` already exist in the shared error catalogue and Spanish text.
- The supplier identifier in the path stays as it is today.
- The app has no production data, so the old route is removed in the same change; no deprecation period is needed. The final path is `/product-suppliers/{sku}/{supplier_id}/terms`.
- Only the override screen moves in this change; the other screens of feature 012 T050 are untouched.
- Agent 00 registers the matrix entry when it exists; until then the change is noted in an Agent 00 contract note.
- No ERP request is involved; Siweb stays read-only apart from the two permitted writes, which this feature does not touch.
