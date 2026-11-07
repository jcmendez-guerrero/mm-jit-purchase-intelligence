# Tasks: MMI 002 — Operational Console, Analytics, Supplier Configuration and Predictive Seed Import

**Input**: Design documents from `/specs/002-mmi-operational-console/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Status**: For human review. Per Jira KAN-34 and Confluence 1998849, no task below may be started until spec, plan and tasks are approved. PR #1 is not merged by this work; nothing is deployed to production; no real ERP write occurs.

**Tests**: Included and written first within each story (constitution Principle V; Confluence AC7). Synthetic fixtures only.

**Organization**: Grouped by user story. Story phases run in the delivery order of plan.md (US1 → US3 → US4 → US5 → US2 → US6 → US7) because US1 unblocks real approvals and US2 consumes data produced by US3–US5. Each story phase is one small reviewable PR.

## Format: `- [ ] [ID] [P?] [Story] Description with file path`

- **[P]**: parallelisable (different files, no dependency on incomplete tasks)
- **[USn]**: user story from spec.md
- Existing code is extended, not rewritten (see plan.md "existing components").
- Task IDs are stable identifiers, not file order: T018–T060 were added after clarification and sit in the phase where they belong.

---

## Phase 1: Setup

**Purpose**: Tooling and fixtures shared by all stories.

- [X] T001 [P] Add chart and accessibility dev dependencies (Recharts, @axe-core/playwright) and a bundle-size budget check in apps/web/package.json and apps/web/vite.config.ts
- [X] T002 [P] Add upload-handling dependency (python-multipart) and size-limit settings to services/api-bff/pyproject.toml and services/forecast-service/pyproject.toml
- [X] T003 [P] Create synthetic seed fixtures (valid CSV, valid XLSX, partly invalid, duplicate rows, unknown variants, negative quantities, mixed origin, macro workbook, wrong signature, oversized, formula cells) in packages/testing/fixtures/seeds/
- [X] T004 [P] Create synthetic supplier-terms and policy fixtures (multiple suppliers, overrides, overlapping windows, expired and future terms) in packages/testing/fixtures/terms/
- [X] T005 [P] Record the cost-guardrail baseline (replica caps, minReplicas 0, job caps) as machine-readable limits in infra/bicep/guardrails.json

---

## Phase 2: Foundational (blocks all stories)

**Purpose**: Contracts, migrations, ownership decisions and localisation keys. Contract-first (AGENTS rule 9).

- [X] T006 DECIDED 2026-11-06: procurement owns editing (follow-up: remove inventory PUT /service-levels and BFF PUT /config/service-levels, optional one-time history import) — Resolve duplicated service-level ownership: read services/inventory-service/src (service_level_config) and services/procurement-service/src (service-levels), decide single owner, and update docs/adr/018-configuration-ownership.md with the migration path
- [X] T007 [P] Add JSON Schemas for supplier terms, product-supplier terms, policy sets, budget caps, demand rules in packages/contracts/dto/
- [X] T008 [P] Add JSON Schemas for seed datasets, mappings, validation results, forecast parameters, accuracy in packages/contracts/dto/
- [X] T009 [P] Add JSON Schemas for scenarios, results, sensitivity and dashboard aggregates in packages/contracts/dto/
- [X] T010 [P] Add event schemas forecast.seed.activated.v1, procurement.terms.changed.v1, procurement.scenario.ready.v1, inventory.rules.changed.v1 and the additive forecast.completed.v1 fields in packages/contracts/events/
- [X] T011 Regenerate Pydantic and TypeScript types and update the compatibility baseline in packages/contracts/ (codegen.toml, baseline/, python/, apps/web/src/api/generated)
- [X] T012 [P] Write contract tests (schema validity, additive compatibility of forecast.completed, example payloads) in packages/contracts/tests/test_mmi002_contracts.py
- [X] T013 Reconcile new BFF routes with existing ones (no duplicates) and finalise specs/002-mmi-operational-console/contracts/bff-api.delta.openapi.yaml and contracts/service-apis.md
- [X] T014 [P] Add stable error-key catalogue (machine-readable in packages/contracts/errors/error_codes.json; services return codes only) and es-ES messages (web catalogue for errors; forecast-service catalogue for the import template; other services get a catalogue when they render artifacts) in services/procurement-service/src/locale/, services/forecast-service/src/locale/, services/inventory-service/src/locale/, services/api-bff/src/locale/ and apps/web/src/i18n/es-ES/
- [X] T015 [P] Add localisation check that fails on hard-coded user-facing strings or error keys without an es-ES message in apps/web/tests/unit/i18n-coverage.test.ts and infra/tests/test_error_keys_localised.py
- [X] T016 Write migration for schema bff (user_roles, audit_events, role_mirror_outbox) in services/api-bff/migrations/ with alembic.ini and a bff database role in infra/postgres/init.sql and infra/compose.yaml (Azure database roles are provisioned outside the Bicep modules, so none is added there)
- [X] T017 Write procurement migrations 0005 (extended supplier_terms, product_supplier_terms), 0006 (policy_sets, budget_caps, stocking_settings, policy_override_requests), 0007 (scenarios, results, sensitivity, version columns on proposals) in services/procurement-service/migrations/versions/
- [X] T018 [P] Add JSON Schema lot-acquisition-cost and event procurement.lot_cost.changed.v1 in packages/contracts/dto/ and packages/contracts/events/
- [X] T019 Write forecast migrations 0003 (seed_datasets, seed_mappings, seed_rows, seed_quarantine, import_jobs) and 0004 (forecast_parameters, forecast_accuracy, version columns on forecast_runs) in services/forecast-service/migrations/versions/
- [X] T020 Write inventory migration 0005 (the next free number; segment_history, demand_exclusions, censoring_rules, agg_daily_kpis, agg_demand_trend, agg_abc_xyz) in services/inventory-service/migrations/versions/
- [X] T021 Extend the PostgreSQL migration test to cover upgrade and downgrade of every new migration and schema-versus-definition parity in infra/tests/test_migrations_postgres.py
- [X] T022 [P] Add append-only and hash-chained audit usage for the bff, forecast and inventory new tables (reuse procurement audit chain pattern) in services/api-bff/src/audit.py, services/forecast-service/src/audit.py, services/inventory-service/src/audit.py
- [X] T023 Write procurement migration 0008 (lot_acquisition_costs, suggested_median_cost on cost_write_requests) and inventory lot_cost_projection migration in services/procurement-service/migrations/versions/ and services/inventory-service/migrations/versions/
- [X] T024 Add private encrypted seed-file container with lifecycle deletion to the existing storage account in infra/bicep/modules/ and the Azurite equivalent in infra/compose.yaml
- [X] T025 Update docs/architecture/implementation-plan.md decisions log and docs/adr/README.md to reference ADRs 018–020 as proposed

**Checkpoint**: contract and migration tests green; stories may proceed.

---

## Phase 3: User Story 1 — Trustworthy approvals and durable access control (P1)

**Goal**: roles persist and are mirrored to procurement; two-person approval with fresh second factor works in the real stack.

**Independent Test**: assign roles, restart the BFF, run a proposal from draft to approved with two users (quickstart scenario 1).

### Tests first

- [X] T026 [P] [US1] Test roles persist across a BFF restart and last admin cannot be removed in services/api-bff/tests/test_roles_persistence.py
- [X] T027 [P] [US1] Test role change writes role, audit and outbox row atomically, retries failed mirror calls, and surfaces failures in services/api-bff/tests/test_role_mirror_outbox.py
- [X] T028 [P] [US1] Test non-admin role changes and viewer mutations are refused and recorded durably in services/api-bff/tests/test_rbac_refusals.py
- [X] T029 [P] [US1] Test dev-login is unavailable unless the local-development flag is set in services/api-bff/tests/test_dev_login_disabled.py
- [X] T030 [P] [US1] Test submission refused with fewer than two eligible approvers, self-approval refused, stale second factor refused, fresh second factor accepted in services/procurement-service/tests/test_approval_eligibility.py
- [X] T031 [US1] Write full-stack test as real processes (dev issuer, procurement-service, api-bff) on a real PostgreSQL: assign roles, restart api-bff, submit and approve with different users, confirm refusals, in infra/tests/test_approval_e2e.py (RUN_E2E_LOCAL=1 and MMI_PG_EXTERNAL_PORT; a Docker Compose variant remains for CI)

### Implementation

- [X] T032 [US1] Implement bff table definitions and repository in services/api-bff/src/db/tables.py and services/api-bff/src/db/roles.py
- [X] T033 [US1] Replace the in-memory user registry, refusal log and audit log with the persistent store in services/api-bff/src/routes/admin_roles.py and services/api-bff/src/routes/rbac.py
- [X] T034 [US1] Implement the role-mirror relay (outbox to procurement PUT /internal/users/{id}/roles with audience-scoped identity, bounded retries) in services/api-bff/src/worker.py and services/api-bff/src/clients/procurement.py
- [X] T035 [US1] Harden procurement's internal role endpoint (service identity audience check, schema validation, audit) in services/procurement-service/src/users/directory.py and services/procurement-service/src/api/
- [X] T036 [US1] Return Spanish explanations for approval.fewer_than_two_approvers and approval.self_not_allowed through services/procurement-service/src/approvals/workflow.py and apps/web/src/features/proposals/
- [X] T037 [US1] Add role and mirror-status management UI (durable, shows mirror lag and failures) in apps/web/src/features/admin/RolesScreen.tsx
- [X] T038 [US1] Perform the security review of commit 3a664a0 (web and BFF); fixes carry regression tests in services/api-bff/tests/, apps/web/tests/unit/ and infra/tests/; the findings summary goes to the internal wiki (not this repository, per AGENTS.md); remaining items are listed as accepted or open in the hand-over report
- [X] T039 [US1] Track open 001 gates (V6 budget split, V7 cutover, 429 behaviour, 001-T130 threat model, 001-T133 cost review, 001-T152 compose smoke test) with owner and status in docs/architecture/implementation-plan.md

**Checkpoint**: US1 independently demonstrable; real approvals possible.

---

## Phase 4: User Story 3 — Supplier and product-supplier terms (P1)

**Goal**: buyer edits full commercial terms and per-product overrides; the next proposal uses them; ERP untouched.

**Independent Test**: quickstart scenario 2.

### Tests first

- [X] T040 [P] [US3] Test validation rules (negative amounts, threshold below minimum, overlapping windows, invalid weekdays, impossible lead time) in services/procurement-service/tests/test_terms_validation.py
- [X] T041 [P] [US3] Test effective-dated append-only versions, as_of resolution and history in services/procurement-service/tests/test_terms_versions.py
- [X] T042 [P] [US3] Test product override precedence over supplier terms and conflict indication with ERP values in services/procurement-service/tests/test_terms_precedence.py
- [X] T043 [P] [US3] Test optimistic concurrency (If-Match, 412 with current version) in services/procurement-service/tests/test_terms_concurrency.py
- [X] T044 [P] [US3] Test allocation uses lead time, pack multiples, discounts, validity windows, preferred flag and manual disable, and cites terms in the explanation in services/procurement-service/tests/test_allocation_terms.py
- [X] T045 [P] [US3] Test no request is built for any ERP path or method when terms change (connector and writer allowlist tests unchanged) in services/siweb-connector/tests/ and services/siweb-cost-writer/tests/
- [X] T046 [P] [US3] Test viewer cannot edit and refusal is audited in services/api-bff/tests/test_suppliers_rbac.py
- [X] T047 [P] [US3] Test lot acquisition costs are stored Recargo-inclusive (net costs converted), append-only, non-negative, never taken from ERP movement price, and emit lot_cost.changed in services/procurement-service/tests/test_lot_costs.py
- [X] T048 [P] [US3] Test the median cost (odd, even and single entry; rounding half-up to cents; entries with zero remaining quantity or no cost excluded; no entry in stock creates no request; buyer-entered opening entry when the ERP has no cost; Recargo-inclusive storage) shows the lots used, is the only value that can be released, and the cost write still needs buyer release, fresh MFA and writer re-check in services/procurement-service/tests/test_median_cost_suggestion.py
- [X] T049 [P] [US3] Test the lot lookup: lots in stock fetched with an audience-scoped identity when the request is built, lots and quantities stored with the request, inventory unavailable fails visibly and retries, no stale stock used in services/procurement-service/tests/test_lot_lookup.py
- [X] T050 [P] [US3] Write Spanish browser test: edit terms, reload, see persistence and history, conflict message on stale save in apps/web/tests/e2e/suppliers.spec.ts

### Implementation

- [X] T051 [US3] Extend terms model, validation and versioned save (lead time, cut-off, delivery weekdays, discounts, payment terms, preference, validity, reliability, disabled, source, reason) in services/procurement-service/src/terms/service.py and services/procurement-service/src/db/tables.py
- [X] T052 [US3] Implement product-supplier overrides with most-specific-wins resolution and conflict detection in services/procurement-service/src/terms/overrides.py
- [X] T053 [US3] Add revision and If-Match handling to terms routes (GET/PUT /suppliers/{id}/terms, /product-suppliers/{variant}/{supplier}/terms) in services/procurement-service/src/api/terms.py
- [X] T054 [US3] Make the allocation engine read effective terms for the run date and record terms version ids on proposals in services/procurement-service/src/allocation/ and services/procurement-service/src/proposals/
- [X] T055 [US3] Emit procurement.terms.changed.v1 through the outbox in services/procurement-service/src/terms/service.py
- [X] T056 [US3] Implement the lot acquisition cost ledger (record automatically from confirmed order costs at receipt matching, buyer-entered opening entry when the ERP has no cost, buyer correction on arrival with audit) and emit procurement.lot_cost.changed.v1 in services/procurement-service/src/costs/lot_costs.py and services/procurement-service/src/orders/
- [X] T057 [US3] Compute the median cost and attach it, with its lot references, as the only value of the cost-write request, creating the request at receipt matching or at buyer entry for a pair with no ERP cost in services/procurement-service/src/costs/median_suggestion.py and services/procurement-service/src/api/costs.py
- [X] T058 [US3] Implement the inventory lots-in-stock lookup route returning remaining quantity per lot in services/inventory-service/src/api/lots.py
- [X] T059 [US3] Implement the procurement lookup client with bounded retry, visible failure and storage of the lots used in services/procurement-service/src/costs/lot_lookup.py
- [X] T060 [US3] Show the median, the lots behind it and a lot-cost correction action (no free cost entry) in the cost-write review screen in apps/web/src/features/costs/ with es-ES strings
- [X] T061 [P] [US3] Test margin = 1 − cost÷PVP on Recargo-inclusive cost (including the cost for exactly 15% and each cap as PVP × (1 − margin)) and the rules: cap below and above EUR 50, kept-as-is when already at or above the cap, increase up to the cap, flag on excess, block below 15%, and unavailable margin when PVP is missing in services/procurement-service/tests/test_margin_rules.py
- [X] T062 [P] [US3] Test admin override: only admin, reason required, release by the override setter refused and release by a different buyer with fresh MFA accepted, pending when no other eligible buyer exists, audit holds median, chosen value, margins and MFA time, still passes buyer review and writer checks, and the writer allowlist is unchanged in services/procurement-service/tests/test_margin_override.py and services/siweb-cost-writer/tests/
- [X] T063 [US3] Implement the margin evaluator (PVP lookup, margins before/after, rule flags, block below 15%) in services/procurement-service/src/costs/margin.py and wire it into the cost-write release path in services/procurement-service/src/api/costs.py
- [X] T064 [US3] Implement the admin override (value, reason, audit fields) in services/procurement-service/src/costs/override.py and expose it through services/api-bff/src/routes/costs.py
- [X] T065 [US3] Build the margin panel with explanatory tips (margin before/after, rule, cost for exactly 15% and the cap, lots behind the median) and the admin override form in apps/web/src/features/costs/ with es-ES strings
- [X] T066 [US3] PVP source decided 2026-11-06 and implemented (operator check on the real ERP tracked in implementation-plan §9): the variant price (`variants.price`). Remaining: switch GET /pvp in services/inventory-service/src/api/lots.py from the movement price to the variant price, make an unavailable margin block the release (spec edge case), and record the operator check that sample variant prices from the real ERP are net of VAT (decided: treated as net, no VAT conversion)
- [X] T067 [US3] Accepted by the owner 2026-11-06 (amendment merge pending). Confirm in planning that writing the median, or an admin-set cost, inside the same review, MFA, audit and writer chain is within constitution Principle I (which names the buyer as the one who enters or confirms the cost), or propose an amendment in .specify/memory/constitution.md via a separate reviewed change
- [X] T068 [P] [US3] Test the cost-update request timing and no-lots cases (request created at receipt match, opening entry when the ERP has no cost, no request when nothing is in stock) in services/procurement-service/tests/test_cost_update_timing.py
- [X] T069 [US3] Add BFF client methods and routes for supplier list/search, terms and overrides with role checks in services/api-bff/src/clients/procurement.py and services/api-bff/src/routes/suppliers.py
- [X] T070 [US3] Build supplier list, terms editor, override editor, history and source badges in apps/web/src/features/suppliers/ with es-ES strings in apps/web/src/i18n/es-ES/suppliers.json
- [X] T071 [US3] Show terms used and precedence in proposal line explanations in apps/web/src/features/proposals/

**Checkpoint**: US3 demonstrable; proposals reflect edited terms.

---

## Phase 5: User Story 4 — Editable policies (P2)

**Goal**: authorised users edit service levels, safety stock, min/max, criticality, cadence, budgets, exclusions, censoring and forecast parameters with preview, effective dates and audit.

**Independent Test**: quickstart scenario 3.

### Tests first

- [X] T072 [P] [US4] Test policy range validation and revision conflicts in services/procurement-service/tests/test_policies.py
- [X] T073 [P] [US4] Test effective dating: earlier runs unchanged, later runs use the new version and record it in services/procurement-service/tests/test_policy_effective_dates.py
- [X] T074 [P] [US4] Test preview of affected products and spend change without saving in services/procurement-service/tests/test_policy_preview.py
- [X] T075 [P] [US4] Test demand exclusions and censoring rules change forecast inputs and are reversible in services/inventory-service/tests/test_demand_rules.py
- [X] T076 [P] [US4] Test clinical criticality is editable in the policy console through the existing inventory endpoint, audited, and refused for viewers in services/inventory-service/tests/test_criticality_console.py and services/api-bff/tests/test_policies_rbac.py
- [X] T077 [P] [US4] Test continuous re-evaluation: category recomputed on each demand update, history with reasons kept, clinical criticality never inferred in services/inventory-service/tests/test_segment_history.py
- [X] T078 [P] [US4] Test recommended versus effective safety stock and the override flow: pending until approved by a different approver, rejection keeps the recommendation, stale recommendation flagged, audit complete in services/procurement-service/tests/test_safety_stock_override.py
- [X] T079 [P] [US4] Test always-stocked mode: floor forces a proposal line with no recent demand or when not forecast-eligible, monthly check included, nothing ordered automatically, shortfall shown when no supplier can serve it in services/procurement-service/tests/test_always_stocked.py
- [X] T080 [P] [US4] Write Spanish browser test of override request, approval queue and always-stocked setting in apps/web/tests/e2e/safety-stock.spec.ts
- [X] T081 [P] [US4] Test forecast parameters accept only approved keys and ranges and are versioned in services/forecast-service/tests/test_parameters.py
- [X] T082 [P] [US4] Test unchanged inputs yield identical re-forecast and re-proposal in services/forecast-service/tests/test_reproducibility.py
- [X] T083 [P] [US4] Write Spanish browser test for policy edit, preview, conflict and refusal for viewers in apps/web/tests/e2e/policies.spec.ts

### Implementation

- [X] T084 [US4] Implement policy sets and budget caps (service, tables, routes, preview) in services/procurement-service/src/policies/ and services/procurement-service/src/api/policies.py
- [X] T085 [US4] Migrate service-level ownership to the decided owner and keep history in services/procurement-service/src/ or services/inventory-service/src/ per the Phase 2 decision
- [X] T086 [US4] Implement demand exclusions and censoring rules with routes in services/inventory-service/src/projections/rules.py and services/inventory-service/src/api/demand_rules.py
- [X] T087 [US4] Expose clinical criticality (read and edit) in the policy console through the BFF and the existing PUT /products/{id}/criticality in services/api-bff/src/routes/policies.py and apps/web/src/features/policies/
- [X] T088 [US4] Record category changes and expose the history in services/inventory-service/src/classification/history.py and services/inventory-service/src/api/segments.py
- [X] T089 [US4] Implement stocking settings, recommended-versus-effective safety stock and override requests with approval in services/procurement-service/src/policies/stocking.py, services/procurement-service/src/policies/overrides.py and services/procurement-service/src/api/policy_overrides.py
- [X] T090 [US4] Add the always-stocked floor rule and monthly check to proposal generation in services/procurement-service/src/proposals/ with the floor reason in the line explanation
- [X] T091 [US4] Add BFF routes and screens for category history, recommended versus effective safety stock, override requests, the approval queue and the always-stocked setting in services/api-bff/src/routes/policies.py and apps/web/src/features/policies/ with es-ES strings
- [X] T092 [US4] Implement forecast parameters with validation and routes in services/forecast-service/src/parameters.py and services/forecast-service/src/api.py
- [X] T093 [US4] Make runs read policy and parameter versions and record them in services/forecast-service/src/runs/runner.py and services/procurement-service/src/proposals/
- [X] T094 [US4] Add on-request re-forecast and re-proposal trigger via events in services/inventory-service/src/projections/rules.py and services/forecast-service/src/runs/consumer.py
- [X] T095 [US4] Add BFF aggregation routes for the three policy sections (each with its own revision) in services/api-bff/src/routes/policies.py
- [X] T096 [US4] Build the policy console (sections, preview, effective date, audit view) replacing the read-only config screen in apps/web/src/features/policies/ with es-ES strings

**Checkpoint**: US4 demonstrable; policy changes alter later runs.

---

## Phase 6: User Story 5 — Predictive seed import (P2)

**Goal**: CSV/XLSX upload → mapping → preview → validation → quarantine → dry-run → activation → forecast → rollback, with provenance and no fabricated ERP data.

**Independent Test**: quickstart scenario 4.

### Tests first

- [X] T097 [P] [US5] Test upload limits, file-signature mismatch, macro workbook, decompression bomb and CSRF/role enforcement in services/api-bff/tests/test_upload_security.py and services/forecast-service/tests/test_upload_hardening.py
- [X] T098 [P] [US5] Test CSV parsing (delimiter, encoding, decimal comma) and XLSX parsing (multi-sheet, merged cells, formulas not evaluated) in services/forecast-service/tests/test_seed_parsing.py
- [X] T099 [P] [US5] Test row validation: unknown variant, negative quantity, date range, duplicates, DST-ambiguous times, mixed origin, notes ignored, nothing silently dropped in services/forecast-service/tests/test_seed_validation.py
- [X] T100 [P] [US5] Test activation is atomic, audited, needs buyer/admin, enqueues a versioned run, and failure leaves the previous version active in services/forecast-service/tests/test_seed_activation.py
- [X] T101 [P] [US5] Test rollback restores the prior version without deleting data and actuals prevail over seeds in overlapping periods in services/forecast-service/tests/test_seed_rollback.py
- [X] T102 [P] [US5] Test imported data never appears in ERP-derived demand series or any ERP request in services/forecast-service/tests/test_seed_isolation.py and services/inventory-service/tests/test_demand_unaffected.py
- [X] T103 [P] [US5] Test formula-injection neutralisation on CSV and XLSX output in services/forecast-service/tests/test_formula_safe_export.py
- [X] T104 [P] [US5] Test duplicate file detection requires an explicit buyer decision in services/forecast-service/tests/test_seed_duplicates.py
- [X] T105 [US5] Write Spanish browser test of the full wizard with valid and hostile fixtures in apps/web/tests/e2e/import.spec.ts

### Implementation

- [X] T106 [US5] Implement BFF upload endpoint (session, CSRF, role, content-length cap, streaming to forecast-service) in services/api-bff/src/routes/imports.py and services/api-bff/src/clients/forecast.py
- [X] T107 [US5] Implement dataset storage, signature verification and private blob quarantine with retention in services/forecast-service/src/seeds/storage.py
- [X] T108 [US5] Implement streaming CSV/XLSX parsers with limits in services/forecast-service/src/seeds/parsers.py
- [X] T109 [US5] Implement mapping suggestion, saved mappings and preview in services/forecast-service/src/seeds/mapping.py
- [X] T110 [US5] Implement row validation, quarantine records and Spanish reason keys in services/forecast-service/src/seeds/validation.py
- [X] T111 [US5] Implement dry-run diff and backtest comparison against the active dataset in services/forecast-service/src/seeds/dryrun.py (reuse services/forecast-service/src/backtest/)
- [X] T112 [US5] Implement activation and rollback transactions and forecast.seed.activated.v1 outbox event in services/forecast-service/src/seeds/lifecycle.py
- [X] T113 [US5] Make forecast runs read the active dataset, fill only insufficient-history variants, flag seeded values and record dataset version in services/forecast-service/src/runs/sources.py and services/forecast-service/src/runs/runner.py
- [X] T114 [US5] Hybrid import processing (decided 2026-11-06): files up to 10,000 rows run in the request; larger ones are queued for the scale-to-zero worker with idempotent re-run (import_jobs), the upload response says the file was sent to the background, and an import status section in the wizard (BFF route + screen) lists imports with stage, timings and error, in services/forecast-service/src/worker.py, services/forecast-service/src/job.py, services/forecast-service/src/imports_api.py, services/api-bff/src/routes/imports.py and apps/web/src/features/imports/
- [X] T115 [US5] Implement Spanish template download (CSV and XLSX) from contracts/import-template.md in services/forecast-service/src/seeds/template.py
- [X] T116 [US5] Add remaining BFF import routes (list, preview, mapping, validate, dry-run, activate, rollback, template) in services/api-bff/src/routes/imports.py
- [X] T117 [US5] Build the import wizard (template, upload, mapping, preview, validation results, quarantine, dry-run, activation, rollback) in apps/web/src/features/imports/ with es-ES strings

**Checkpoint**: US5 demonstrable end to end; hostile files refused.

---

## Phase 7: User Story 2 — Analytical dashboard (P1)

**Goal**: real-data KPIs and interactive charts with live filters and drill-downs.

**Independent Test**: quickstart scenario 5. May run in parallel with Phase 6 after Phase 2.

### Tests first

- [X] T118 [P] [US2] Test aggregate read models equal reference totals on the synthetic dataset (value, coverage, risk, ABC/XYZ, trend) in services/inventory-service/tests/test_aggregates.py
- [X] T119 [P] [US2] Test filter options come from live warehouses, categories and suppliers and none are hard-coded in services/inventory-service/tests/test_filter_options.py and apps/web/tests/unit/no-hardcoded-options.test.ts
- [X] T120 [P] [US2] Test coverage days (forecast basis, 90-day actual fallback, labelled basis, zero-demand state) and inventory value equals quantity per lot times lot acquisition cost, ignores ERP movement price (PVP), uses the labelled fallback for lots without cost and counts them in the estimated-cost indicator in services/inventory-service/tests/test_inventory_value.py
- [X] T121 [P] [US2] Test forecast accuracy and spend summaries in services/forecast-service/tests/test_accuracy.py and services/procurement-service/tests/test_spend_summary.py
- [X] T122 [P] [US2] Test actual ERP series and imported estimates are separate in the trend response in services/inventory-service/tests/test_trend_series_separation.py
- [X] T123 [P] [US2] Test BFF merges card-level results only and degrades per card on a failing service in services/api-bff/tests/test_dashboard_orchestration.py
- [X] T124 [P] [US2] Write Spanish browser tests for KPIs, charts, filters, drill-down, empty/loading/error/stale states, keyboard use and axe accessibility in apps/web/tests/e2e/dashboard.spec.ts
- [X] T125 [P] [US2] Write dashboard performance budget test (first meaningful content under 3 s on ~1,000 variants) in apps/web/tests/e2e/dashboard-perf.spec.ts

### Implementation

- [X] T126 [US2] Implement daily aggregate refresh in the existing inventory worker pass in services/inventory-service/src/projections/aggregates.py and services/inventory-service/src/worker.py
- [X] T127 [US2] Project lot acquisition costs from procurement.lot_cost.changed.v1 into lot_cost_projection and compute inventory value from it in services/inventory-service/src/projections/lot_costs.py and services/inventory-service/src/projections/aggregates.py
- [X] T128 [US2] Implement dashboard routes (summary, demand-trend, abc-xyz, risks, filters/options) in services/inventory-service/src/api/dashboard.py
- [X] T129 [US2] Implement forecast accuracy, runs list and variant forecast routes in services/forecast-service/src/api.py and services/forecast-service/src/runs/accuracy.py
- [X] T130 [US2] Implement proposed-spend summary in services/procurement-service/src/api/summary.py
- [X] T131 [US2] Implement BFF dashboard orchestration and filter options in services/api-bff/src/routes/dashboard.py
- [X] T132 [US2] Build KPI cards, charts with table alternative, filter bar and freshness indicator in apps/web/src/features/dashboard/ (replace the hard-coded warehouse list)
- [X] T133 [US2] Build drill-down panels and the product detail view (demand, forecast with uncertainty, stock, risk reasons, data used) in apps/web/src/features/dashboard/ProductDetail.tsx
- [X] T134 [US2] Add es-ES labels and Spanish number/date/EUR formatting for all dashboard strings in apps/web/src/i18n/es-ES/dashboard.json

**Checkpoint**: US2 demonstrable; KPIs match reference totals.

---

## Phase 8: User Story 6 — Procurement scenarios (P2)

**Goal**: what-if scenarios with explanations, sensitivity, comparison, promotion and export.

**Independent Test**: quickstart scenario 6.

### Tests first

- [X] T135 [P] [US6] Test scenario computation never writes live tables or ERP data and is reproducible from recorded versions in services/procurement-service/tests/test_scenarios_isolation.py
- [X] T136 [P] [US6] Test MOQ, lead time, shipping, pack multiple and budget changes alter allocation with stated reasons in services/procurement-service/tests/test_scenarios_constraints.py
- [X] T137 [P] [US6] Test infeasible scenarios explain the shortfall and clinical-critical needs are shown under a low cap in services/procurement-service/tests/test_scenarios_infeasible.py
- [X] T138 [P] [US6] Test sensitivity is bounded to top binding constraints within the runtime budget in services/procurement-service/tests/test_scenarios_sensitivity.py
- [X] T139 [P] [US6] Test promotion creates a draft proposal that needs a different approver with fresh second factor in services/procurement-service/tests/test_scenarios_promote.py
- [X] T140 [P] [US6] Test Spanish CSV/XLSX export formats and formula safety in services/procurement-service/tests/test_scenarios_export.py
- [X] T141 [US6] Write Spanish browser test of scenario creation, comparison, promotion and export in apps/web/tests/e2e/scenarios.spec.ts

### Implementation

- [X] T142 [US6] Run the allocation engine in no-write mode against a scenario parameter set in services/procurement-service/src/scenarios/engine.py (reuse services/procurement-service/src/allocation/)
- [X] T143 [US6] Persist scenarios, results, constraint explanations and sensitivity in services/procurement-service/src/scenarios/store.py
- [X] T144 [US6] Implement scenario routes (create with Idempotency-Key, get, list, promote, export) in services/procurement-service/src/api/scenarios.py and emit procurement.scenario.ready.v1
- [X] T145 [US6] Add BFF scenario routes and client in services/api-bff/src/routes/scenarios.py and services/api-bff/src/clients/procurement.py
- [X] T146 [US6] Build scenario builder, side-by-side comparison, constraint explanations, sensitivity and budget utilisation in apps/web/src/features/scenarios/
- [X] T147 [US6] Add promote-to-proposal and export actions with es-ES strings in apps/web/src/features/scenarios/ and apps/web/src/i18n/es-ES/scenarios.json

**Checkpoint**: US6 demonstrable; scenarios explain allocation changes.

---

## Phase 9: User Story 7 — Administration, reliability and cost (P3)

**Goal**: operators see status, can safely re-run jobs, and cost guardrails hold.

**Independent Test**: quickstart scenario 7.

### Tests first

- [X] T148 [P] [US7] Test admin status aggregates sync freshness, import jobs, model runs and mirror lag in services/api-bff/tests/test_admin_status.py
- [X] T149 [P] [US7] Test permitted job re-runs are idempotent, admin-only and audited in services/api-bff/tests/test_admin_rerun.py
- [X] T150 [P] [US7] Test cost guardrails (minReplicas 0, replica and job caps, no new always-on resource, one lifecycle-limited container) against infra/bicep/guardrails.json in infra/tests/test_cost_guardrails.py

### Implementation

- [X] T151 [US7] Implement admin status and re-run routes in services/api-bff/src/routes/admin_status.py
- [X] T152 [US7] Build admin screens for sync, import jobs, supplier-policy history, model runs and cost indicators in apps/web/src/features/admin/
- [X] T153 [US7] Add metrics and alerts for import failures, upload rejections and role-mirror lag in infra/bicep/modules/ and the services' logging (no secrets, no personal data)
- [X] T154 [US7] Write the monthly cost estimate for storage and job minutes and evaluate malware scanning feasibility; record the decision or accepted risk in docs/architecture/implementation-plan.md and docs/adr/020-seed-provenance.md

---

## Phase 10: Polish and cross-cutting verification

- [X] T155 [P] Run the full Spanish Playwright suite and capture screenshots of every new screen as review evidence in apps/web/tests/e2e/ and docs/architecture/evidence/ (synthetic data only)
- [X] T156 [P] Write security abuse suite (upload abuse, CSRF, RBAC bypass, MFA freshness, IDOR on datasets and scenarios, formula injection) in infra/tests/test_security_abuse.py
- [X] T157 [P] Add runbooks: failed import, rollback of a dataset, role-mirror failure in docs/runbooks/
- [X] T158 [P] Update quickstart with final commands and add a synthetic demo path in specs/002-mmi-operational-console/quickstart.md
- [X] T159 Run secret scan, vulnerability scan and contract compatibility checks locally and in CI configuration under .github/workflows/ (local: pattern secret scan, pip-audit on the installed environment, npm audit and contract tests run; gitleaks and Trivy only run in CI because they are not installed here)
- [X] T160 Run RUN_PG_MIGRATIONS=1 and RUN_E2E=1 suites and fix failures before reporting (PostgreSQL 16 migrations and the real-process approval end-to-end passed against a local cluster; the Docker-based RUN_E2E pipeline suite was not run because Docker is unavailable here)
- [X] T161 Write the final technical report mapping SC-001..SC-011 and AC1..AC9 to evidence in specs/002-mmi-operational-console/report.md
- [X] T162 Mark completed tasks [X] in this file and update ADR statuses (018–020) after review (task list is current; ADR-018 to ADR-020 deliberately stay `proposed` until the owner reviews them, as the task says)

---

## Dependencies and execution order

- Phase 1 → Phase 2 (blocks everything) → Phase 3 (US1) → Phases 4–9.
- US3 (Phase 4) and US4 (Phase 5) are independent after US1; US4's service-level migration depends on the Phase 2 ownership decision.
- US5 (Phase 6) depends on the forecast migrations and US4's forecast parameters for run versioning.
- US2 (Phase 7) depends only on Phase 2 for code, and on US3–US5 for richer data; it can run in parallel with Phase 6.
- US6 (Phase 8) depends on US3 and US4 (terms and policies) and on proposals from US1.
- US7 (Phase 9) depends on US1, US5 and US6 status sources.
- Within a story: tests, then data/service, then routes, then BFF, then UI.

## Parallel opportunities

- Setup tasks, contract schemas, error keys and localisation checks (Phase 1–2) are largely [P].
- Test tasks inside each story are [P] (separate files).
- After Phase 3: Phase 4 and Phase 5 backend work can proceed in parallel; Phase 6 and Phase 7 can proceed in parallel.

## Implementation strategy

1. Review gate: humans approve spec, plan and tasks (required by Jira KAN-34).
2. MVP: Phases 1–3 (Setup, Foundational, US1) — durable roles and a working two-person approval. Then US3 (supplier terms) as the first buyer-visible value.
3. Deliver each phase as one small PR into the feature branch lineage; never merge PR #1 or deploy production from this work.
4. Stop at any checkpoint and demonstrate that story using its quickstart scenario.

## Phase 11: Follow-up from clarification 2026-11-07

- [X] T163 [P] Test that a variant price last confirmed by a sync more than 7 days ago is reported stale by `GET /pvp` (with its age), that a fresh price is not, and that procurement treats a stale price like a missing one (margin unavailable, release blocked, admin override allowed) in services/inventory-service/tests/test_pvp.py and services/procurement-service/tests/test_margin_rules.py
- [X] T164 Add `price_confirmed_at` to inventory `variants` (migration edited in place while unmerged), set it in the product/variant projection each time a sync confirms the price, and return `as_of` and `stale` from `GET /pvp` in services/inventory-service/src/
- [X] T165 Show the price age next to the PVP on the cost screen and the stale reason in Spanish (new string and error-key if needed) in apps/web/src/features/costs/ and services/procurement-service/src/costs/
- [ ] T166 [DEFERRED, separate task, not part of this delivery] Per-product VAT handling for the margin check: a buyer-maintained "selling price includes VAT" flag (default decided then), margin on price ÷ (1 + the product's VAT rate) when included, the flag and rate shown next to the PVP, and a one-time review of existing products (evidence: a VAT-included variant price, `price_cents` 250, and VAT-excluded ones with fractional cents, `price_cents` 4181.12)

## Phase 12: Convergence

- [X] T167 Run a backtest of the candidate seed dataset against the active one in the dry-run and return the accuracy comparison (instead of `not_run_until_activation`), with tests in services/forecast-service/tests/ and the comparison shown on the import screen with es-ES strings per FR-023 (partial)
- [X] T168 Wire `MMI_INVENTORY_URL`, the series source and blob writer into the forecast-service entry in infra/compose.yaml, and cover a forecast re-run in the pipeline suite infra/tests/test_pipeline_e2e.py per plan: Compose stack and SC-010 (partial)
- [X] T169 Add an Azure blob adapter for seed originals (put and get against the private `seed-quarantine` container, same interface as `LocalSeedStore`, managed identity), select it by configuration, grant the forecast identity writer access in infra/bicep/modules/storage.bicep, and test it on Azurite in services/forecast-service/ per FR-020 and ADR-020 (missing)
- [X] T170 Project the ERP `category` from variants into inventory (migration edited in place), return it in the filter options and apply it as the product-family filter on the dashboard, with tests and es-ES labels per FR-006 (partial)
- [X] T171 Fix the colour-contrast failures in apps/web/src/index.css and remove `disableRules(["color-contrast"])` from apps/web/tests/e2e/dashboard.spec.ts and a11y.spec.ts so the accessibility run enforces it per SC-010 (partial)
- [X] T172 Add a timing test on a synthetic 1,000-product import (upload to activation under 15 minutes) and a rollback (under 2 minutes) in services/forecast-service/tests/test_seed_timing.py per SC-002 (partial)
- [X] T173 Self-host the Inter and Bricolage Grotesque font files in apps/web/public/fonts, drop the Google Fonts links from apps/web/index.html and the third-party hosts from the Content-Security-Policy in apps/web/nginx.conf, and update infra/tests/test_web_headers.py, or record why the third-party hosts stay (unrequested) (resolved by decision 2026-11-07: the fonts stay on Google Fonts as a recorded exception, FR-049; the existing header test already enforces the two allowed hosts)

## Phase 13: Convergence

- [X] T174 Add drill-down from every dashboard KPI card and chart to the products behind the figure (for example the variants in a stock-out risk, an ABC/XYZ cell, or a trend day), and a supplier detail panel opened from the supplier filter and the spend-by-supplier figures, with es-ES strings and keyboard access, backed by the existing inventory and procurement endpoints (add a read-only endpoint only where one is missing, contract first), in apps/web/src/features/dashboard/ and a Spanish browser test in apps/web/tests/e2e/dashboard.spec.ts per FR-007 (partial)

## Phase 14: Convergence

- [X] T175 Carry the `seed_used` forecast reason through to the buyer: store it with the forecast in procurement's view of the run, add it to the proposal line explanation and to the product detail, and label such figures in Spanish as based on imported estimates (never as actual ERP demand); label only, no extra confirmation or approval step (decided 2026-11-07), with tests in services/procurement-service/tests/, services/inventory-service/tests/ and apps/web/tests/ per FR-008 (partial)
- [X] T176 Show the full per-supplier-group result in the scenario view: persist shipping and discount per group with the scenario result (contract first, migration edited in place), and render the lines, quantities, unit costs, shipping, discounts, order total, expected delivery and budget utilisation for each group in apps/web/src/features/scenarios/ with es-ES strings and tests per FR-029 (partial)

## Phase 15: Convergence

- [X] T177 Show demand versus forecast with uncertainty on the dashboard: fill the `estimated` series of `GET /dashboard/demand-trend` with the forecast's daily mean and an uncertainty band (low and high) for the coming days from forecast-service's latest run, only for forecast-eligible variants in the current filters, never mixed into the actual ERP series; draw it in the trend chart with a distinct style, a legend and a text and table alternative, say when no forecast exists, and write the missing separation test services/inventory-service/tests/test_trend_series_separation.py (actual series unchanged by the forecast; forecast absent when unavailable) plus a Spanish browser test, with es-ES strings per FR-005 and T122 (partial)

## Phase 16: Convergence

- [X] T178 Show a product's forecast with uncertainty and its risk reasons in the product detail: extend forecast-service's per-variant read (`GET /forecasts/variant/{id}`) to return the daily mean and the upper bound per horizon (never the imported rows), return the product's own risk entries from the inventory risk data, forward both through the BFF, and render them in apps/web/src/features/dashboard/ProductDetail.tsx as a labelled forecast block (clearly apart from the actual-demand table, with the imported-estimates note) and a list of Spanish risk reasons, with tests in services/forecast-service/tests/, services/inventory-service/tests/, services/api-bff/tests/ and apps/web/tests/ per US2/AC4 (partial)
- [X] T179 Label the warehouse view as informational: when a warehouse is selected, show in Spanish that the company-wide proposal is the canonical one and that the proposed spend and the forecast do not change with the warehouse filter, with a unit test and a browser test in apps/web/tests/ and es-ES strings in apps/web/src/i18n/es-ES.json per US2/AC6 (partial)

## Phase 17: Convergence

- [X] T180 Offer the Excel export of a proposal next to the CSV one: add a `proposals.export_xlsx` es-ES label and a download link for `/api/proposals/{id}/export?format=xlsx` in apps/web/src/features/proposals/ProposalsScreen.tsx, with a unit test in apps/web/tests/unit/ProposalsScreen.test.tsx and a browser test that the file downloads per FR-032 and US6/AC5 (partial)
