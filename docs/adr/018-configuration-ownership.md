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

### Service-level ownership (T006 / T085) — decided 2026-11-06: procurement (option A)

The owner confirmed **procurement-service**. Remaining work: remove inventory `PUT /service-levels` and the BFF `PUT /config/service-levels`, and optionally import the inventory history once. Applied as follows:

- Editing moves to procurement `policy_sets` (effective-dated, revisioned, audited; scopes product > segment > global).
- The proposal builder uses the procurement value when one is in force on the run date and otherwise the inventory-computed target (clinical-critical 99 %, ABC A/B/C 97/95/90 %, sparse 85 %), which stays as the **default**, not as an editable source.
- Inventory's `service_level_config` and `PUT /service-levels` are left in place, read-only in the UI, so earlier proposals keep reproducing; no data is copied or deleted. A later migration can import its history into `policy_sets` once the owner confirms.
- Rolling back is a matter of deleting the procurement policy rows; nothing in inventory was changed.

### Consequences

- Good: no new deployable or Azure cost; rules stay beside their data; restart-safe roles.
- Bad: one new schema/role (`bff`); a policy "save all" is several calls, so the UI shows per-section results and conflicts.
- Rejected: a central config service (new cost and boundary); roles inside procurement (couples login to purchasing); in-memory roles (the PR #1 blocker).
