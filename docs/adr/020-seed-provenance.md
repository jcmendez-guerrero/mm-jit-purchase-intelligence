# ADR-020: Predictive seed datasets, provenance and activation

- Status: proposed
- Date: 2026-11-05
- Feature: specs/002-mmi-operational-console

## Context and problem statement

ERP history is short (about 1,640 movements, all in 2026), so seasonal forecasting needs an initial predictive base. Imported estimates must never look like ERP transactions, and uploads are an attack surface in a public-repository, shared-budget project.

## Decision outcome

- Seeds live in forecast-service tables apart from ERP-derived demand, in three kinds: observed_external, estimated, manual_forecast, each with provenance and an `origin` flag (synthetic or real). A dataset cannot mix origins.
- Lifecycle: uploaded, validated, approved, active, superseded or rolled back, or rejected. Activation and rollback are atomic, audited, need buyer or admin confirmation, never delete data, and enqueue a versioned forecast run that records the dataset version.
- Actuals prevail over seeds in overlapping periods; the overlap is reported.
- Upload hardening: authenticated, CSRF-protected, size and type limits, signature verification, macro and formula rejection, decompression limits, private encrypted container with retention, parsing in a scale-to-zero job. Paid malware scanning is evaluated in Phase 6; if not affordable, compensating controls are recorded as an accepted risk.
- Exports neutralise spreadsheet formula prefixes.

### Consequences

- Good: forecasts on thin history without falsifying ERP facts; full rollback; reproducible runs.
- Bad: forecast code must read two sources and label output; extra storage container (lifecycle-limited).
- Rejected: writing seeds as movements (fabrication); free blending (non-reproducible).
