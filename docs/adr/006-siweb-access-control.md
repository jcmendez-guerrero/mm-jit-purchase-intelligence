# ADR-006: Siweb access control on our side

- Status: proposed (amended 2026-11-04)

## Context and problem statement
Siweb issues one full-scope token per company, so read-only behaviour cannot be enforced by the ERP. It must be enforced by this system.

## Decision outcome
- Reader (`siweb-connector`): compiled-in closed list of GET paths, single approved host, no redirects, token from Key Vault only.
- **One permitted write**, `PUT /inventory/products/{id}/suppliers/{contact_id}` (supplier cost), only in `siweb-cost-writer`, only when the buyer enters a missing cost or confirms an order at a different cost. It has its own identity and Key Vault access, a closed allowlist containing only that operation, buyer review with fresh MFA before sending, read-modify-write of the cost field only, read-after-write verification, hash-chained audit (who, when, previous, new, outcome) and visible bounded retries.
- If Siweb has no product-supplier record, no call is made (`pending_link`).
- Everything else is refused before a request is built and counted as a security event.

### Consequences
- Good: ERP stays the source of truth for supplier cost; blast radius limited by code path, identity and egress rules.
- Bad: the writer holds a full-scope token (residual risk recorded in the internal threat model); PUT semantics must be verified on a non-production record first (Gate 0, V4 / task T135).
