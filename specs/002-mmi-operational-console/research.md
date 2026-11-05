# Research: MMI 002 — Operational Console

All items are decisions taken from the authoritative sources, the existing architecture and the code-backed gap inventory in `spec.md`. Items marked **Verify** are assumptions to confirm during the named phase; they are not facts.

## R1. Where do durable roles live?

- **Decision**: new `bff` schema with `user_roles`, `role_audit` and `role_mirror_outbox`; the BFF writes the role and the outbox row in one transaction, a relay calls procurement's existing authenticated `PUT /internal/users/{user_id}/roles` with retries; failures are visible in Admin. Procurement stays the authority for approval eligibility (it already checks its own mirror).
- **Rationale**: roles are an identity concern at the edge; the mirror endpoint exists; outbox is the established pattern.
- **Alternatives**: roles in procurement only (couples login to the purchasing service; synchronous dependency); Entra app roles as sole source (planned for production in 001 Phase 5 but not available locally and does not give an audited, mirrored local registry); keep in memory (the blocker).

## R2. Ownership of new configuration (ADR-018)

- **Decision**: procurement owns supplier terms, product-supplier overrides, purchase policy sets (service levels, budget caps, replenishment cadence, min/max) and scenarios. Forecast owns seed datasets, import pipeline, forecast parameters, backtests and accuracy. Inventory owns demand exclusions, censoring rules and aggregate read models. The BFF composes "policies" as three sections, each with its own revision, so there is no cross-schema transaction.
- **Rationale**: matches 001 ownership and Confluence section 4; keeps a rule next to the data it changes.
- **Alternatives**: one config service (new deployable, new cost, breaks "preserve services"); BFF-owned config (business rules in the BFF is forbidden).
- **Verify (Phase 1)**: 001 holds service levels in both inventory (`service_level_config`) and procurement (`/service-levels`). Phase 1 must read both and decide the single owner (proposed: procurement) and a migration for the other; do not duplicate.

## R3. Override precedence (ADR-019)

- **Decision**: per field, ERP-owned facts (stock, movements, ERP cost) come from the ERP; MMI-owned terms use the most specific approved local value valid on the run date (product-supplier override, then supplier, then conservative default flagged); uploaded estimates apply only where no actual or approved value exists, are labelled, and never replace ERP facts. Conflicts surface as an indicator, not silently.
- **Rationale**: Confluence section 4; lead time and minimum order are not writable via the ERP supplier PUT (verified V4), so they must be local.
- **Alternatives**: last write wins (hides conflicts); ERP always wins (cannot hold MMI-only terms).

## R4. Seed provenance and data kinds (ADR-020)

- **Decision**: three kinds stored apart from ERP movements: `observed_external` (history from another source), `estimated`, `manual_forecast`. Each dataset records uploader, time, source label, file checksum, mapping, validation summary, kind per row and a dataset version. Forecast reads actuals first; seeds fill only where history is insufficient and are flagged in the run. Synthetic and real data carry an explicit `origin` flag; activation refuses a dataset that mixes them.
- **Rationale**: ERP has about 1,640 movements, all in 2026; seasonal models need history. Never fabricate ERP transactions (Jira acceptance).
- **Alternatives**: insert seeds as movements (forbidden, fabricates facts); free blending (non-reproducible).

## R5. Upload hardening

- **Decision**: BFF enforces session, CSRF, role, content-length cap (initial 5 MB, configurable) and streams to forecast-service, which verifies the file signature (ZIP `PK` for XLSX, UTF-8/Windows-1252 text for CSV), rejects `.xlsm`/macro parts (`vbaProject.bin`), caps decompressed size and sheet/row/column counts, parses with openpyxl `read_only=True, data_only=True` and the stdlib CSV reader, never evaluates formulas, stores the original in a private encrypted container with retention (default 30 days after supersession), and parses in a scale-to-zero job.
- **Rationale**: Confluence section 6; controls without paid services.
- **Alternatives**: direct-to-blob SAS upload (extra surface, harder CSRF/role checks); Defender for Storage malware scanning (recurring cost; **Verify** feasibility within budget in Phase 6 — otherwise record the compensating controls as an accepted risk).

## R6. Formula-injection-safe output

- **Decision**: any exported or displayed text cell beginning with `=`, `+`, `-`, `@`, tab or carriage return is prefixed so it is inert; numeric cells are written as numbers; tested with hostile fixtures in CSV and XLSX.
- **Rationale**: standard OWASP mitigation; required by FR-027.

## R7. Dashboard aggregates and charts

- **Decision**: inventory maintains daily aggregate read models refreshed by the existing worker pass; forecast exposes accuracy; procurement exposes spend; the BFF merges card-level results only. Charts use Recharts (SVG) with a data-table toggle, keyboard focus and text summaries; filter options come from a single "filter options" endpoint per service. Inventory value is valued at the latest known unit cost per variant and labelled as such. **Verify (Phase 4)** with the owner that this valuation basis is acceptable versus current verified supplier cost.
- **Rationale**: no always-on analytics; meets 3 s budget with pre-aggregation.
- **Alternatives**: per-request aggregation of movements (slow); Power BI / Synapse (cost); canvas charts (poor accessibility).

## R8. Concurrency and versioning

- **Decision**: every editable resource has an integer `revision`; PUT requires `If-Match: "<revision>"`; mismatch returns 412 with the current version. Terms and policies are append-only effective-dated versions with `valid_from`/`valid_to`; "as of" resolution picks the version valid on the run date; overlapping windows are rejected.
- **Rationale**: Confluence section 4–5; matches existing append-only terms table and hash-chained audit.

## R9. Scenarios

- **Decision**: a scenario is a parameter delta applied to a read-only copy of current inputs; it runs the existing allocation engine in a mode that never writes to live tables; results store input version ids so recomputation is identical; promotion copies the chosen result into a draft proposal through the existing proposal creation path. Sensitivity = re-solve with ± a bounded change on each binding constraint, limited to the top N binding constraints to keep runtime within budget.
- **Rationale**: reuse CP-SAT engine; reproducibility principle.
- **Alternatives**: new optimiser (rewrite, rejected); client-side computation (business rules in the UI).

## R10. Localisation enforcement

- **Decision**: stable error keys from services; the SPA maps keys to es-ES; templates and exports use the same catalogue; a test scans the SPA and service message catalogues and fails on hard-coded user-facing strings or missing keys; exports use `es-ES` number/date formatting with EUR.

## R11. Cost guardrails

- **Decision**: no new always-on resources; imports and aggregate refresh run on the existing scale-to-zero jobs/workers; a test asserts replica and job caps and `minReplicas: 0` in the Bicep and compose definitions; one extra private container with lifecycle deletion. **Verify (Phase 6)** projected storage and job minutes with a worked estimate in `docs/architecture`.

## R12. Review of second-agent code (commit 3a664a0)

- **Decision**: Phase 0 performs a line-by-line security and quality review of the web and BFF code (session, CSRF, RBAC, role admin, refusal log, in-memory stores), records findings in the internal wiki (not this repository), and fixes or accepts each before operational UI ships.
- **Known starting points from the code**: role registry, refusal log and audit log in `services/api-bff/src/routes/{admin_roles,rbac}.py` are process memory; dev-login route exists and must be proven disabled outside local development.

## Open items carried from 001 (tracked, not decided here)

V6 request-budget split, V7 loss-reason cutover, 429 behaviour, real lots/supplier-list shapes, threat model (T130), regional cost review (T133), compose smoke test (T152). Owner decisions are needed; defaults from 001 remain.
