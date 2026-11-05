# ADR-018: Ownership of operational configuration and durable roles

- Status: proposed
- Date: 2026-11-05
- Feature: specs/002-mmi-operational-console

## Context and problem statement

MMI 002 adds buyer-editable supplier terms, policies, forecast parameters, seed datasets and scenarios, and needs roles that survive restarts. Each service must keep its own schema; the BFF must not hold business rules.

## Decision outcome

- procurement-service owns supplier terms, product-supplier overrides, purchase policy sets (service levels, min/max, cadence), budget caps and scenarios.
- forecast-service owns seed datasets, the import pipeline, forecast parameters, backtests and accuracy.
- inventory-service owns demand exclusions, stockout-censoring rules and dashboard aggregate read models.
- api-bff owns only identity data in a new `bff` schema (user roles, role audit, role-mirror outbox) and mirrors roles to procurement through its authenticated internal endpoint. Procurement remains the authority for approval eligibility.
- The policy console is one screen over three independently revisioned sections; there is no cross-service transaction. Service levels currently exist in inventory and procurement; Phase 1 designates one owner (proposed: procurement) and migrates the other.

### Consequences

- Good: no new deployable or Azure cost; rules stay beside their data; restart-safe roles.
- Bad: one new schema/role (`bff`); a policy "save all" is several calls, so the UI shows per-section results and conflicts.
- Rejected: a central config service (new cost and boundary); roles inside procurement (couples login to purchasing); in-memory roles (the PR #1 blocker).
