# ADR-005: Siweb shared rate-limit budget and schedule

- Status: proposed
- Date: 2026-11-04

## Context and problem statement

The ERP allows 1,000 requests/hour per company token, shared with another application. Exhausting it breaks both.

## Decision outcome

MMI uses at most ~500 requests/hour (to be agreed with the other application), enforced by a token bucket in the connector. Heavy jobs run in a night window; historical backfill is spread over several nights; `date_to` is frozen per run. Quota denials back off and raise an alert.

### Consequences

- Good: predictable usage, no impact on the other application.
- Bad: initial backfill takes several nights; the split is an assumption until verified (Gate 0, V6).
