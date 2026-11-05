# ADR-019: Precedence between ERP facts, local overrides and uploaded estimates

- Status: proposed
- Date: 2026-11-05
- Feature: specs/002-mmi-operational-console

## Context and problem statement

The same quantity can come from Siweb, from a buyer-approved local value, or from an uploaded estimate. Verified: lead time and minimum order are not writable through the ERP supplier PUT, so they must live locally.

## Decision outcome

Per field, never globally:

1. ERP-owned facts (stock, movements, ERP supplier cost) always come from the ERP. Nothing local or imported overwrites them; the only ERP write is the existing buyer-released, fresh-MFA supplier-cost PUT.
2. MMI-owned terms use the most specific approved local value valid on the run date: product-supplier override, then supplier terms, then a conservative default that is flagged.
3. Uploaded estimates apply only where no actual or approved value exists, carry their kind and provenance, and are labelled wherever shown.
4. A disagreement between layers is recorded and displayed (conflict indicator); it is never resolved silently. Every result records the version ids used.

### Consequences

- Good: explainable, reproducible, ERP untouched.
- Bad: more states to display; conflict handling needs UI and tests.
- Rejected: last-write-wins (hides conflicts); ERP-always-wins (cannot hold MMI-only terms).
