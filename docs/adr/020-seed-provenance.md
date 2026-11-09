# ADR-020: Predictive seed datasets, provenance and activation

- Status: accepted (owner, 2026-11-07)
- Date: 2026-11-05
- Feature: specs/002-mmi-operational-console

## Context and problem statement

ERP history is short (about 1,640 movements, all in 2026), so seasonal forecasting needs an initial predictive base. Imported estimates must never look like ERP transactions, and uploads are an attack surface in a public-repository, shared-budget project.

## Decision outcome

- Seeds live in forecast-service tables apart from ERP-derived demand, in three kinds: observed_external, estimated, manual_forecast, each with provenance and an `origin` flag (synthetic or real). A dataset cannot mix origins.
- Lifecycle: uploaded, validated, active, superseded or rolled back, or rejected (the `approved` state is never set; see the MMI-7 amendment). Activation and rollback are atomic, audited, need buyer or admin confirmation, never delete data, and enqueue a versioned forecast run that records the dataset version.
- Actuals prevail over seeds in overlapping periods; the overlap is reported.
- Upload hardening: authenticated, CSRF-protected, size and type limits, signature verification, macro and formula rejection, decompression limits, private encrypted container with retention, parsing in a scale-to-zero job. Paid malware scanning was evaluated (implementation plan section 10): not enabled; compensating controls are in place and the residual risk is recorded as an accepted risk, confirmed by the owner on 2026-11-07 (revisit if uploads become frequent, non-staff users get upload rights, or the budget allows scanning).
- Exports neutralise spreadsheet formula prefixes.

### Consequences

- Good: forecasts on thin history without falsifying ERP facts; full rollback; reproducible runs.
- Bad: forecast code must read two sources and label output; extra storage container (lifecycle-limited).
- Rejected: writing seeds as movements (fabrication); free blending (non-reproducible).

## Amendment (MMI-7, 2026-11-09)

- **Two people.** The uploader and whoever chose the mapping or ran validation cannot activate a dataset. The one exception is an owner or admin who gives a reason from a short list (only person available, urgent need, other) and may add a short detail: the activation is allowed and audited apart as `seed.self_activated`, so a one-person shop can still work. Activation and rollback need fresh multi-factor authentication.
- **Rollback needs a reason from a list** (wrong figures, wrong file, test, replaced by a newer file, other) and may add a short free-text detail of at most 100 characters. The chosen reason is shown to everyone and recorded in the audit trail; the detail is shown to admins only and never audited, so the free-text rule of the constitution is kept (owner decision, 2026-11-09). Two simultaneous rollbacks end with one success and one `import_conflict`. Refused governance attempts are logged as `SEED_REFUSED` with actor, action and dataset.
- **Products are identified by SKU.** Files carry the SKU; the importer resolves the ERP variant id from the synchronised catalogue and never trusts a variant id from the file. A SKU that matches more than one product (identical, or differing only by case or spaces) is quarantined as ambiguous, never resolved by chance, because the ERP does not guarantee unique SKUs. Unknown SKUs are quarantined too.
- **ERP exports are not seed files.** Files recognised as ERP exports are refused (they are local-only under the constitution). Seed files with real-origin business estimates may still be uploaded in the cloud under this ADR.
- **Unlabelled rows are quarantined,** never defaulted to a label (owner decision, 2026-11-09).
- Specification: `specs/008-mmi-7-predictive-seed-import/`.
