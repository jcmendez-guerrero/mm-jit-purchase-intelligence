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
- Task IDs are stable identifiers, not file order: T133–T141 were added after clarification and sit in the phase where they belong.

---

## Phase 1: Setup

**Purpose**: Tooling and fixtures shared by all stories.

- [ ] T001 [P] Add chart and accessibility dev dependencies (Recharts, @axe-core/playwright) and a bundle-size budget check in apps/web/package.json and apps/web/vite.config.ts
- [ ] T002 [P] Add upload-handling dependency (python-multipart) and size-limit settings to services/api-bff/pyproject.toml and services/forecast-service/pyproject.toml
- [ ] T003 [P] Create synthetic seed fixtures (valid CSV, valid XLSX, partly invalid, duplicate rows, unknown variants, negative quantities, mixed origin, macro workbook, wrong signature, oversized, formula cells) in packages/testing/fixtures/seeds/
- [ ] T004 [P] Create synthetic supplier-terms and policy fixtures (multiple suppliers, overrides, overlapping windows, expired and future terms) in packages/testing/fixtures/terms/
- [ ] T005 [P] Record the cost-guardrail baseline (replica caps, minReplicas 0, job caps) as machine-readable limits in infra/bicep/guardrails.json

---

## Phase 2: Foundational (blocks all stories)

**Purpose**: Contracts, migrations, ownership decisions and localisation keys. Contract-first (AGENTS rule 9).

- [ ] T006 Resolve duplicated service-level ownership: read services/inventory-service/src (service_level_config) and services/procurement-service/src (service-levels), decide single owner, and update docs/adr/018-configuration-ownership.md with the migration path
- [ ] T007 [P] Add JSON Schemas for supplier terms, product-supplier terms, policy sets, budget caps, demand rules in packages/contracts/dto/
- [ ] T008 [P] Add JSON Schemas for seed datasets, mappings, validation results, forecast parameters, accuracy in packages/contracts/dto/
- [ ] T009 [P] Add JSON Schemas for scenarios, results, sensitivity and dashboard aggregates in packages/contracts/dto/
- [ ] T010 [P] Add event schemas forecast.seed.activated.v1, procurement.terms.changed.v1, procurement.scenario.ready.v1, inventory.rules.changed.v1 and the additive forecast.completed.v1 fields in packages/contracts/events/
- [ ] T011 Regenerate Pydantic and TypeScript types and update the compatibility baseline in packages/contracts/ (codegen.toml, baseline/, python/, apps/web/src/api/generated)
- [ ] T012 [P] Write contract tests (schema validity, additive compatibility of forecast.completed, example payloads) in packages/contracts/tests/test_mmi002_contracts.py
- [ ] T013 Reconcile new BFF routes with existing ones (no duplicates) and finalise specs/002-mmi-operational-console/contracts/bff-api.delta.openapi.yaml and contracts/service-apis.md
- [ ] T014 [P] Add stable error-key catalogue and es-ES messages in services/procurement-service/src/locale/, services/forecast-service/src/locale/, services/inventory-service/src/locale/, services/api-bff/src/locale/ and apps/web/src/i18n/es-ES/
- [ ] T015 [P] Add localisation check that fails on hard-coded user-facing strings or error keys without an es-ES message in apps/web/tests/unit/i18n-coverage.test.ts and infra/tests/test_error_keys_localised.py
- [ ] T016 Write migration for schema bff (user_roles, role_audit, role_mirror_outbox) in services/api-bff/migrations/ with alembic.ini and a bff database role in infra/compose.yaml and infra/bicep/modules/
- [ ] T017 Write procurement migrations 0005 (extended supplier_terms, product_supplier_terms), 0006 (policy_sets, budget_caps), 0007 (scenarios, results, sensitivity, version columns on proposals) in services/procurement-service/migrations/versions/
- [ ] T133 [P] Add JSON Schema lot-acquisition-cost and event procurement.lot_cost.changed.v1 in packages/contracts/dto/ and packages/contracts/events/
- [ ] T018 Write forecast migrations 0003 (seed_datasets, seed_mappings, seed_rows, seed_quarantine, import_jobs) and 0004 (forecast_parameters, forecast_accuracy, version columns on forecast_runs) in services/forecast-service/migrations/versions/
- [ ] T019 Write inventory migration 0003 (demand_exclusions, censoring_rules, agg_daily_kpis, agg_demand_trend, agg_abc_xyz) in services/inventory-service/migrations/versions/
- [ ] T020 Extend the PostgreSQL migration test to cover upgrade and downgrade of every new migration and schema-versus-definition parity in infra/tests/test_migrations_postgres.py
- [ ] T021 [P] Add append-only and hash-chained audit usage for the bff, forecast and inventory new tables (reuse procurement audit chain pattern) in services/api-bff/src/audit.py, services/forecast-service/src/audit.py, services/inventory-service/src/audit.py
- [ ] T134 Write procurement migration 0008 (lot_acquisition_costs, suggested_median_cost on cost_write_requests) and inventory lot_cost_projection migration in services/procurement-service/migrations/versions/ and services/inventory-service/migrations/versions/
- [ ] T022 Add private encrypted seed-file container with lifecycle deletion to the existing storage account in infra/bicep/modules/ and the Azurite equivalent in infra/compose.yaml
- [ ] T023 Update docs/architecture/implementation-plan.md decisions log and docs/adr/README.md to reference ADRs 018–020 as proposed

**Checkpoint**: contract and migration tests green; stories may proceed.

---

## Phase 3: User Story 1 — Trustworthy approvals and durable access control (P1)

**Goal**: roles persist and are mirrored to procurement; two-person approval with fresh second factor works in the real stack.

**Independent Test**: assign roles, restart the BFF, run a proposal from draft to approved with two users (quickstart scenario 1).

### Tests first

- [ ] T024 [P] [US1] Test roles persist across a BFF restart and last admin cannot be removed in services/api-bff/tests/test_roles_persistence.py
- [ ] T025 [P] [US1] Test role change writes role, audit and outbox row atomically, retries failed mirror calls, and surfaces failures in services/api-bff/tests/test_role_mirror_outbox.py
- [ ] T026 [P] [US1] Test non-admin role changes and viewer mutations are refused and recorded durably in services/api-bff/tests/test_rbac_refusals.py
- [ ] T027 [P] [US1] Test dev-login is unavailable unless the local-development flag is set in services/api-bff/tests/test_dev_login_disabled.py
- [ ] T028 [P] [US1] Test submission refused with fewer than two eligible approvers, self-approval refused, stale second factor refused, fresh second factor accepted in services/procurement-service/tests/test_approval_eligibility.py
- [ ] T029 [US1] Write full-stack compose test: assign roles, restart api-bff, submit and approve with two users, confirm refusals in infra/tests/test_approval_e2e.py (RUN_E2E=1)

### Implementation

- [ ] T030 [US1] Implement bff table definitions and repository in services/api-bff/src/db/tables.py and services/api-bff/src/db/roles.py
- [ ] T031 [US1] Replace the in-memory user registry, refusal log and audit log with the persistent store in services/api-bff/src/routes/admin_roles.py and services/api-bff/src/routes/rbac.py
- [ ] T032 [US1] Implement the role-mirror relay (outbox to procurement PUT /internal/users/{id}/roles with audience-scoped identity, bounded retries) in services/api-bff/src/worker.py and services/api-bff/src/clients/procurement.py
- [ ] T033 [US1] Harden procurement's internal role endpoint (service identity audience check, schema validation, audit) in services/procurement-service/src/users/directory.py and services/procurement-service/src/api/
- [ ] T034 [US1] Return Spanish explanations for approval.fewer_than_two_approvers and approval.self_not_allowed through services/procurement-service/src/approvals/workflow.py and apps/web/src/features/proposals/
- [ ] T035 [US1] Add role and mirror-status management UI (durable, shows mirror lag and failures) in apps/web/src/features/admin/RolesScreen.tsx
- [ ] T036 [US1] Perform and document the security review of commit 3a664a0 (web and BFF); fix findings or record accepted risks in the internal wiki; add regression tests for each fix in services/api-bff/tests/ and apps/web/tests/unit/
- [ ] T037 [US1] Track open 001 gates (V6 budget split, V7 cutover, 429 behaviour, threat model T130, cost review T133, compose smoke test T152) with owner and status in docs/architecture/implementation-plan.md

**Checkpoint**: US1 independently demonstrable; real approvals possible.

---

## Phase 4: User Story 3 — Supplier and product-supplier terms (P1)

**Goal**: buyer edits full commercial terms and per-product overrides; the next proposal uses them; ERP untouched.

**Independent Test**: quickstart scenario 2.

### Tests first

- [ ] T038 [P] [US3] Test validation rules (negative amounts, threshold below minimum, overlapping windows, invalid weekdays, impossible lead time) in services/procurement-service/tests/test_terms_validation.py
- [ ] T039 [P] [US3] Test effective-dated append-only versions, as_of resolution and history in services/procurement-service/tests/test_terms_versions.py
- [ ] T040 [P] [US3] Test product override precedence over supplier terms and conflict indication with ERP values in services/procurement-service/tests/test_terms_precedence.py
- [ ] T041 [P] [US3] Test optimistic concurrency (If-Match, 412 with current version) in services/procurement-service/tests/test_terms_concurrency.py
- [ ] T042 [P] [US3] Test allocation uses lead time, pack multiples, discounts, validity windows, preferred flag and manual disable, and cites terms in the explanation in services/procurement-service/tests/test_allocation_terms.py
- [ ] T043 [P] [US3] Test no request is built for any ERP path or method when terms change (connector and writer allowlist tests unchanged) in services/siweb-connector/tests/ and services/siweb-cost-writer/tests/
- [ ] T044 [P] [US3] Test viewer cannot edit and refusal is audited in services/api-bff/tests/test_suppliers_rbac.py
- [ ] T137 [P] [US3] Test lot acquisition costs are append-only, non-negative, never taken from ERP movement price, and emit lot_cost.changed in services/procurement-service/tests/test_lot_costs.py
- [ ] T138 [P] [US3] Test the median cost (odd, even and single lot, zero lots, outliers) shows the lots used, is the only value that can be released, and the cost write still needs buyer release, fresh MFA and writer re-check in services/procurement-service/tests/test_median_cost_suggestion.py
- [ ] T045 [P] [US3] Write Spanish browser test: edit terms, reload, see persistence and history, conflict message on stale save in apps/web/tests/e2e/suppliers.spec.ts

### Implementation

- [ ] T046 [US3] Extend terms model, validation and versioned save (lead time, cut-off, delivery weekdays, discounts, payment terms, preference, validity, reliability, disabled, source, reason) in services/procurement-service/src/terms/service.py and services/procurement-service/src/db/tables.py
- [ ] T047 [US3] Implement product-supplier overrides with most-specific-wins resolution and conflict detection in services/procurement-service/src/terms/overrides.py
- [ ] T048 [US3] Add revision and If-Match handling to terms routes (GET/PUT /suppliers/{id}/terms, /product-suppliers/{variant}/{supplier}/terms) in services/procurement-service/src/api/terms.py
- [ ] T049 [US3] Make the allocation engine read effective terms for the run date and record terms version ids on proposals in services/procurement-service/src/allocation/ and services/procurement-service/src/proposals/
- [ ] T050 [US3] Emit procurement.terms.changed.v1 through the outbox in services/procurement-service/src/terms/service.py
- [ ] T139 [US3] Implement the lot acquisition cost ledger (record automatically from confirmed order costs at receipt matching, buyer correction on arrival with audit) and emit procurement.lot_cost.changed.v1 in services/procurement-service/src/costs/lot_costs.py and services/procurement-service/src/orders/
- [ ] T140 [US3] Compute the median cost and attach it, with its lot references, as the only value of the cost-write request in services/procurement-service/src/costs/median_suggestion.py and services/procurement-service/src/api/costs.py
- [ ] T141 [US3] Show the median, the lots behind it and a lot-cost correction action (no free cost entry) in the cost-write review screen in apps/web/src/features/costs/ with es-ES strings
- [ ] T051 [US3] Add BFF client methods and routes for supplier list/search, terms and overrides with role checks in services/api-bff/src/clients/procurement.py and services/api-bff/src/routes/suppliers.py
- [ ] T052 [US3] Build supplier list, terms editor, override editor, history and source badges in apps/web/src/features/suppliers/ with es-ES strings in apps/web/src/i18n/es-ES/suppliers.json
- [ ] T053 [US3] Show terms used and precedence in proposal line explanations in apps/web/src/features/proposals/

**Checkpoint**: US3 demonstrable; proposals reflect edited terms.

---

## Phase 5: User Story 4 — Editable policies (P2)

**Goal**: authorised users edit service levels, safety stock, min/max, criticality, cadence, budgets, exclusions, censoring and forecast parameters with preview, effective dates and audit.

**Independent Test**: quickstart scenario 3.

### Tests first

- [ ] T054 [P] [US4] Test policy range validation and revision conflicts in services/procurement-service/tests/test_policies.py
- [ ] T055 [P] [US4] Test effective dating: earlier runs unchanged, later runs use the new version and record it in services/procurement-service/tests/test_policy_effective_dates.py
- [ ] T056 [P] [US4] Test preview of affected products and spend change without saving in services/procurement-service/tests/test_policy_preview.py
- [ ] T057 [P] [US4] Test demand exclusions and censoring rules change forecast inputs and are reversible in services/inventory-service/tests/test_demand_rules.py
- [ ] T058 [P] [US4] Test forecast parameters accept only approved keys and ranges and are versioned in services/forecast-service/tests/test_parameters.py
- [ ] T059 [P] [US4] Test unchanged inputs yield identical re-forecast and re-proposal in services/forecast-service/tests/test_reproducibility.py
- [ ] T060 [P] [US4] Write Spanish browser test for policy edit, preview, conflict and refusal for viewers in apps/web/tests/e2e/policies.spec.ts

### Implementation

- [ ] T061 [US4] Implement policy sets and budget caps (service, tables, routes, preview) in services/procurement-service/src/policies/ and services/procurement-service/src/api/policies.py
- [ ] T062 [US4] Migrate service-level ownership to the decided owner and keep history in services/procurement-service/src/ or services/inventory-service/src/ per the Phase 2 decision
- [ ] T063 [US4] Implement demand exclusions and censoring rules with routes in services/inventory-service/src/projections/rules.py and services/inventory-service/src/api/demand_rules.py
- [ ] T064 [US4] Implement forecast parameters with validation and routes in services/forecast-service/src/parameters.py and services/forecast-service/src/api.py
- [ ] T065 [US4] Make runs read policy and parameter versions and record them in services/forecast-service/src/runs/runner.py and services/procurement-service/src/proposals/
- [ ] T066 [US4] Add on-request re-forecast and re-proposal trigger via events in services/inventory-service/src/projections/rules.py and services/forecast-service/src/runs/consumer.py
- [ ] T067 [US4] Add BFF aggregation routes for the three policy sections (each with its own revision) in services/api-bff/src/routes/policies.py
- [ ] T068 [US4] Build the policy console (sections, preview, effective date, audit view) replacing the read-only config screen in apps/web/src/features/policies/ with es-ES strings

**Checkpoint**: US4 demonstrable; policy changes alter later runs.

---

## Phase 6: User Story 5 — Predictive seed import (P2)

**Goal**: CSV/XLSX upload → mapping → preview → validation → quarantine → dry-run → activation → forecast → rollback, with provenance and no fabricated ERP data.

**Independent Test**: quickstart scenario 4.

### Tests first

- [ ] T069 [P] [US5] Test upload limits, file-signature mismatch, macro workbook, decompression bomb and CSRF/role enforcement in services/api-bff/tests/test_upload_security.py and services/forecast-service/tests/test_upload_hardening.py
- [ ] T070 [P] [US5] Test CSV parsing (delimiter, encoding, decimal comma) and XLSX parsing (multi-sheet, merged cells, formulas not evaluated) in services/forecast-service/tests/test_seed_parsing.py
- [ ] T071 [P] [US5] Test row validation: unknown variant, negative quantity, date range, duplicates, DST-ambiguous times, mixed origin, notes ignored, nothing silently dropped in services/forecast-service/tests/test_seed_validation.py
- [ ] T072 [P] [US5] Test activation is atomic, audited, needs buyer/admin, enqueues a versioned run, and failure leaves the previous version active in services/forecast-service/tests/test_seed_activation.py
- [ ] T073 [P] [US5] Test rollback restores the prior version without deleting data and actuals prevail over seeds in overlapping periods in services/forecast-service/tests/test_seed_rollback.py
- [ ] T074 [P] [US5] Test imported data never appears in ERP-derived demand series or any ERP request in services/forecast-service/tests/test_seed_isolation.py and services/inventory-service/tests/test_demand_unaffected.py
- [ ] T075 [P] [US5] Test formula-injection neutralisation on CSV and XLSX output in services/forecast-service/tests/test_formula_safe_export.py
- [ ] T076 [P] [US5] Test duplicate file detection requires an explicit buyer decision in services/forecast-service/tests/test_seed_duplicates.py
- [ ] T077 [US5] Write Spanish browser test of the full wizard with valid and hostile fixtures in apps/web/tests/e2e/import.spec.ts

### Implementation

- [ ] T078 [US5] Implement BFF upload endpoint (session, CSRF, role, content-length cap, streaming to forecast-service) in services/api-bff/src/routes/imports.py and services/api-bff/src/clients/forecast.py
- [ ] T079 [US5] Implement dataset storage, signature verification and private blob quarantine with retention in services/forecast-service/src/seeds/storage.py
- [ ] T080 [US5] Implement streaming CSV/XLSX parsers with limits in services/forecast-service/src/seeds/parsers.py
- [ ] T081 [US5] Implement mapping suggestion, saved mappings and preview in services/forecast-service/src/seeds/mapping.py
- [ ] T082 [US5] Implement row validation, quarantine records and Spanish reason keys in services/forecast-service/src/seeds/validation.py
- [ ] T083 [US5] Implement dry-run diff and backtest comparison against the active dataset in services/forecast-service/src/seeds/dryrun.py (reuse services/forecast-service/src/backtest/)
- [ ] T084 [US5] Implement activation and rollback transactions and forecast.seed.activated.v1 outbox event in services/forecast-service/src/seeds/lifecycle.py
- [ ] T085 [US5] Make forecast runs read the active dataset, fill only insufficient-history variants, flag seeded values and record dataset version in services/forecast-service/src/runs/sources.py and services/forecast-service/src/runs/runner.py
- [ ] T086 [US5] Implement import job processing in the scale-to-zero worker with idempotent re-run in services/forecast-service/src/worker.py and services/forecast-service/src/job.py
- [ ] T087 [US5] Implement Spanish template download (CSV and XLSX) from contracts/import-template.md in services/forecast-service/src/seeds/template.py
- [ ] T088 [US5] Add remaining BFF import routes (list, preview, mapping, validate, dry-run, activate, rollback, template) in services/api-bff/src/routes/imports.py
- [ ] T089 [US5] Build the import wizard (template, upload, mapping, preview, validation results, quarantine, dry-run, activation, rollback) in apps/web/src/features/imports/ with es-ES strings

**Checkpoint**: US5 demonstrable end to end; hostile files refused.

---

## Phase 7: User Story 2 — Analytical dashboard (P1)

**Goal**: real-data KPIs and interactive charts with live filters and drill-downs.

**Independent Test**: quickstart scenario 5. May run in parallel with Phase 6 after Phase 2.

### Tests first

- [ ] T090 [P] [US2] Test aggregate read models equal reference totals on the synthetic dataset (value, coverage, risk, ABC/XYZ, trend) in services/inventory-service/tests/test_aggregates.py
- [ ] T091 [P] [US2] Test filter options come from live warehouses, categories and suppliers and none are hard-coded in services/inventory-service/tests/test_filter_options.py and apps/web/tests/unit/no-hardcoded-options.test.ts
- [ ] T135 [P] [US2] Test inventory value equals quantity per lot times lot acquisition cost, ignores ERP movement price (PVP), uses the labelled fallback for lots without cost and counts them in the estimated-cost indicator in services/inventory-service/tests/test_inventory_value.py
- [ ] T092 [P] [US2] Test forecast accuracy and spend summaries in services/forecast-service/tests/test_accuracy.py and services/procurement-service/tests/test_spend_summary.py
- [ ] T093 [P] [US2] Test actual ERP series and imported estimates are separate in the trend response in services/inventory-service/tests/test_trend_series_separation.py
- [ ] T094 [P] [US2] Test BFF merges card-level results only and degrades per card on a failing service in services/api-bff/tests/test_dashboard_orchestration.py
- [ ] T095 [P] [US2] Write Spanish browser tests for KPIs, charts, filters, drill-down, empty/loading/error/stale states, keyboard use and axe accessibility in apps/web/tests/e2e/dashboard.spec.ts
- [ ] T096 [P] [US2] Write dashboard performance budget test (first meaningful content under 3 s on ~1,000 variants) in apps/web/tests/e2e/dashboard-perf.spec.ts

### Implementation

- [ ] T097 [US2] Implement daily aggregate refresh in the existing inventory worker pass in services/inventory-service/src/projections/aggregates.py and services/inventory-service/src/worker.py
- [ ] T136 [US2] Project lot acquisition costs from procurement.lot_cost.changed.v1 into lot_cost_projection and compute inventory value from it in services/inventory-service/src/projections/lot_costs.py and services/inventory-service/src/projections/aggregates.py
- [ ] T098 [US2] Implement dashboard routes (summary, demand-trend, abc-xyz, risks, filters/options) in services/inventory-service/src/api/dashboard.py
- [ ] T099 [US2] Implement forecast accuracy, runs list and variant forecast routes in services/forecast-service/src/api.py and services/forecast-service/src/runs/accuracy.py
- [ ] T100 [US2] Implement proposed-spend summary in services/procurement-service/src/api/summary.py
- [ ] T101 [US2] Implement BFF dashboard orchestration and filter options in services/api-bff/src/routes/dashboard.py
- [ ] T102 [US2] Build KPI cards, charts with table alternative, filter bar and freshness indicator in apps/web/src/features/dashboard/ (replace the hard-coded warehouse list)
- [ ] T103 [US2] Build drill-down panels and the product detail view (demand, forecast with uncertainty, stock, risk reasons, data used) in apps/web/src/features/dashboard/ProductDetail.tsx
- [ ] T104 [US2] Add es-ES labels and Spanish number/date/EUR formatting for all dashboard strings in apps/web/src/i18n/es-ES/dashboard.json

**Checkpoint**: US2 demonstrable; KPIs match reference totals.

---

## Phase 8: User Story 6 — Procurement scenarios (P2)

**Goal**: what-if scenarios with explanations, sensitivity, comparison, promotion and export.

**Independent Test**: quickstart scenario 6.

### Tests first

- [ ] T105 [P] [US6] Test scenario computation never writes live tables or ERP data and is reproducible from recorded versions in services/procurement-service/tests/test_scenarios_isolation.py
- [ ] T106 [P] [US6] Test MOQ, lead time, shipping, pack multiple and budget changes alter allocation with stated reasons in services/procurement-service/tests/test_scenarios_constraints.py
- [ ] T107 [P] [US6] Test infeasible scenarios explain the shortfall and clinical-critical needs are shown under a low cap in services/procurement-service/tests/test_scenarios_infeasible.py
- [ ] T108 [P] [US6] Test sensitivity is bounded to top binding constraints within the runtime budget in services/procurement-service/tests/test_scenarios_sensitivity.py
- [ ] T109 [P] [US6] Test promotion creates a draft proposal that needs a different approver with fresh second factor in services/procurement-service/tests/test_scenarios_promote.py
- [ ] T110 [P] [US6] Test Spanish CSV/XLSX export formats and formula safety in services/procurement-service/tests/test_scenarios_export.py
- [ ] T111 [US6] Write Spanish browser test of scenario creation, comparison, promotion and export in apps/web/tests/e2e/scenarios.spec.ts

### Implementation

- [ ] T112 [US6] Run the allocation engine in no-write mode against a scenario parameter set in services/procurement-service/src/scenarios/engine.py (reuse services/procurement-service/src/allocation/)
- [ ] T113 [US6] Persist scenarios, results, constraint explanations and sensitivity in services/procurement-service/src/scenarios/store.py
- [ ] T114 [US6] Implement scenario routes (create with Idempotency-Key, get, list, promote, export) in services/procurement-service/src/api/scenarios.py and emit procurement.scenario.ready.v1
- [ ] T115 [US6] Add BFF scenario routes and client in services/api-bff/src/routes/scenarios.py and services/api-bff/src/clients/procurement.py
- [ ] T116 [US6] Build scenario builder, side-by-side comparison, constraint explanations, sensitivity and budget utilisation in apps/web/src/features/scenarios/
- [ ] T117 [US6] Add promote-to-proposal and export actions with es-ES strings in apps/web/src/features/scenarios/ and apps/web/src/i18n/es-ES/scenarios.json

**Checkpoint**: US6 demonstrable; scenarios explain allocation changes.

---

## Phase 9: User Story 7 — Administration, reliability and cost (P3)

**Goal**: operators see status, can safely re-run jobs, and cost guardrails hold.

**Independent Test**: quickstart scenario 7.

### Tests first

- [ ] T118 [P] [US7] Test admin status aggregates sync freshness, import jobs, model runs and mirror lag in services/api-bff/tests/test_admin_status.py
- [ ] T119 [P] [US7] Test permitted job re-runs are idempotent, admin-only and audited in services/api-bff/tests/test_admin_rerun.py
- [ ] T120 [P] [US7] Test cost guardrails (minReplicas 0, replica and job caps, no new always-on resource, one lifecycle-limited container) against infra/bicep/guardrails.json in infra/tests/test_cost_guardrails.py

### Implementation

- [ ] T121 [US7] Implement admin status and re-run routes in services/api-bff/src/routes/admin_status.py
- [ ] T122 [US7] Build admin screens for sync, import jobs, supplier-policy history, model runs and cost indicators in apps/web/src/features/admin/
- [ ] T123 [US7] Add metrics and alerts for import failures, upload rejections and role-mirror lag in infra/bicep/modules/ and the services' logging (no secrets, no personal data)
- [ ] T124 [US7] Write the monthly cost estimate for storage and job minutes and evaluate malware scanning feasibility; record the decision or accepted risk in docs/architecture/implementation-plan.md and docs/adr/020-seed-provenance.md

---

## Phase 10: Polish and cross-cutting verification

- [ ] T125 [P] Run the full Spanish Playwright suite and capture screenshots of every new screen as review evidence in apps/web/tests/e2e/ and docs/architecture/evidence/ (synthetic data only)
- [ ] T126 [P] Write security abuse suite (upload abuse, CSRF, RBAC bypass, MFA freshness, IDOR on datasets and scenarios, formula injection) in infra/tests/test_security_abuse.py
- [ ] T127 [P] Add runbooks: failed import, rollback of a dataset, role-mirror failure in docs/runbooks/
- [ ] T128 [P] Update quickstart with final commands and add a synthetic demo path in specs/002-mmi-operational-console/quickstart.md
- [ ] T129 Run secret scan, vulnerability scan and contract compatibility checks locally and in CI configuration under .github/workflows/
- [ ] T130 Run RUN_PG_MIGRATIONS=1 and RUN_E2E=1 suites and fix failures before reporting
- [ ] T131 Write the final technical report mapping SC-001..SC-011 and AC1..AC9 to evidence in specs/002-mmi-operational-console/report.md
- [ ] T132 Mark completed tasks [X] in this file and update ADR statuses (018–020) after review

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
