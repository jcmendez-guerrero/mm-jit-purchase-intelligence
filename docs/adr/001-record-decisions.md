# ADR-001: Record decisions with MADR

- Status: proposed
- Date: 2026-11-04

## Context and problem statement

Architecture choices (access control, data policy, cost) must stay traceable in a public repository without exposing environment details.

## Decision outcome

Record material decisions as MADR files in `docs/adr/`. Each ADR states context, options, outcome and consequences, and contains no secrets or environment-specific identifiers. Changes to accepted ADRs are made by a new or amending ADR and noted in the decisions log of `docs/architecture/implementation-plan.md`.

### Consequences

- Good: reviewable history; constitution governance can point to ADRs.
- Bad: small upkeep cost per decision.
