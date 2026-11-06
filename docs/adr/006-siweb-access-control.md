# ADR-006: Siweb access control on our side

- Status: proposed (amended 2026-11-04; amended 2026-11-06 for MMI 002, constitution v1.2.0 accepted by the owner)

## Context and problem statement

Siweb issues one full-scope token per company, so read-only behaviour cannot be enforced by the ERP. It must be enforced by this system.

## Decision outcome

- Reader (`siweb-connector`): compiled-in closed list of GET paths, single approved host, no redirects, token from Key Vault only.
- **One permitted write**, `PUT /inventory/products/{id}/suppliers/{contact_id}` (supplier cost), only in `siweb-cost-writer`, only when goods are received and matched to a confirmed order, or when the buyer enters a cost for a pair that has none in Siweb (MMI 002: the value is the median of the Recargo-inclusive lot acquisition costs with stock remaining; margin below 15 % blocks the release unless an admin sets a value with a reason; the admin who sets it cannot release it; a different buyer releases it with a fresh second factor; the writer's own checks and this allowlist are unchanged). It has its own identity and Key Vault access, a closed allowlist containing only that operation, buyer review with fresh MFA before sending, read-modify-write of the cost field only, read-after-write verification, hash-chained audit (who, when, previous, new, outcome) and visible bounded retries.
- If Siweb has no product-supplier record, no call is made (`pending_link`).
- Everything else is refused before a request is built and counted as a security event.

### Consequences

- Good: ERP stays the source of truth for supplier cost; blast radius limited by code path, identity and egress rules.
- Bad: the writer holds a full-scope token (residual risk recorded in the internal threat model); PUT semantics had to be verified first (Gate 0, V4 / T135). Verified on 2026-11-04/05 on a test product (the ERP has no non-production environment): the PUT upserts, merges, ignores lead time, minimum order and unknown fields, and accepts fractional cents; see research.md V4.
- Open: egress is restricted by the application (closed allowlist: one host, one PUT, one supplier-list read). A network-level FQDN rule would need Azure Firewall, which does not fit the shared EUR 120/month budget. Revisit if the budget changes.
