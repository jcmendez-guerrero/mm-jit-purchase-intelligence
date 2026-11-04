# Tasks: Mundo Mascotix Intelligence — Inventory Intelligence & Weekly Purchasing Platform

**Input**: Design documents from `/specs/001-mmi-purchase-intelligence/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included. The constitution (Principle V) requires automated tests for behaviour, security boundaries, data-quality failures and duplicate handling.

**Organization**: Grouped by user story. Note: US5 (P1) depends on US3 and US4 (P2) for policies and costs, so phases run US1 → US2 → US3 → US4 → US5 → US6 → US7.

## Format: `- [ ] [ID] [P?] [Story] Description with file path`
- **[P]**: parallelisable (different files, no dependency on incomplete tasks)
- Real Siweb data is never used; all tests use synthetic fixtures.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Monorepo skeleton, tooling and repository hygiene (public repo rules).

- [X] T001 Create monorepo skeleton per plan.md: apps/web, services/{siweb-connector,siweb-cost-writer,inventory-service,forecast-service,procurement-service,api-bff}, packages/{contracts,testing}, infra/bicep, security/, docs/adr/, .github/workflows/
- [X] T002 Write AGENTS.md and CLAUDE.md at repo root (rules: synthetic data only, read-only Siweb except cost write, no real IDs, es-ES UI, contract-first)
- [X] T003 [P] Configure Python workspace tooling (uv/pip-tools with hashed lockfiles, ruff, mypy, pytest) in pyproject.toml at repo root and per service services/*/pyproject.toml
- [X] T004 [P] Configure web tooling (Vite, TypeScript strict, ESLint, Vitest, Playwright) in apps/web/package.json and apps/web/tsconfig.json
- [X] T005 [P] Extend .gitignore to block real data and params: *.csv, *.xlsx, *.har, /data/, *.bicepparam, *.tfvars (allow packages/testing/**/fixtures/ and *.example) in .gitignore
- [X] T006 [P] Add Gitleaks config with custom rules (Siweb host + Bearer, Azure ID patterns) in .gitleaks.toml and a pre-commit config in .pre-commit-config.yaml
- [X] T007 [P] Add PR template with data/security/cost/contract checklist in .github/pull_request_template.md and Dependabot config in .github/dependabot.yml
- [X] T008 [P] Add security method docs (templates only, no findings): security/threat-model-template.md, security/data-classification.md
- [X] T009 [P] Create ADR index and MADR template plus ADRs 001, 002, 005, 006 (amended), 012, 017 in docs/adr/
- [ ] T129 Gate 0 live read-only checks, results recorded in the internal wiki (not in repo): movement timezone (V1), ticket reference_type (V2), history depth, page sizes and 429 behaviour (V3), VAT-rate source and rounding (V5), rate split (V6), loss-reason cutover date (V7). Blocks live collection (T045 against the real ERP) and the defaults baked into US1/US2; mock-based work may proceed meanwhile
- [X] T135 Gate 0 supplier-cost PUT verification on a non-production record (V4): body, merge semantics, whether a link can be created; record outcome in the internal wiki and update research.md R4/V4. Blocks T100 and T101 against the real ERP and any cost write to production

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Contracts, synthetic data, Siweb mock, local stack, shared libraries, CI. No user story starts before this completes.

- [X] T010 Define JSON Schemas for event envelope and the eight events in packages/contracts/events/*.schema.json (see specs/001-mmi-purchase-intelligence/contracts/events.md)
- [X] T011 [P] Define JSON Schemas for shared DTOs (Money, Variant, Proposal, ProposalLine, SupplierCost, CostWrite) in packages/contracts/dto/*.schema.json
- [X] T012 Configure codegen to Pydantic and TypeScript plus a schema-compatibility check in packages/contracts/codegen.toml and packages/contracts/tests/test_compat.py
- [X] T013 [P] Create shared Python library for Decimal money, UTC time and correlation IDs in packages/contracts/python/mmi_common/money.py and mmi_common/time.py
- [X] T014 [P] Implement MessageBus interface with Storage Queue and in-memory implementations in packages/contracts/python/mmi_common/bus.py
- [X] T015 [P] Implement outbox relay (one message per subscribed queue) and inbox dedup helpers in packages/contracts/python/mmi_common/outbox.py
- [X] T016 [P] Implement structured logging with correlation ID and redaction (tokens, personal data) in packages/contracts/python/mmi_common/logging.py
- [X] T017 [P] Implement service-to-service auth (managed-identity validation, dev issuer) in packages/contracts/python/mmi_common/auth.py
- [X] T018 Create the seeded synthetic data generator (catalogue ~1,000 variants, 3 warehouses + unassigned, lots, ~9 months of movements across all 15 reasons, demand profiles, stockouts, malformed expiry, missing lots) in packages/testing/src/generator/
- [X] T019 Build the Siweb mock server (three pagination shapes, newest-first paging with mid-run inserts, 429/401, missing pages, timezone-less timestamps) serving the generator in packages/testing/src/siweb_mock/
- [X] T020 Add supplier-cost PUT to the Siweb mock (read-modify-write pitfalls, failure injection, request log for assertions) in packages/testing/src/siweb_mock/suppliers.py
- [X] T021 [P] Add generator tests that fixtures match only the aggregate ratios and contain no real values in packages/testing/tests/test_generator.py
- [X] T022 Create Docker Compose stack (Postgres with per-service schemas/roles, Azurite, Siweb mock, dev JWT issuer, all services, web) in infra/compose.yaml
- [X] T023 [P] Create per-service Dockerfiles (non-root, pinned digests) in services/*/Dockerfile and apps/web/Dockerfile
- [X] T024 [P] Set up Alembic per service with schema-scoped roles in services/*/migrations/ and infra/postgres/init.sql
- [X] T025 [P] Create FastAPI service skeletons with health endpoints and auth dependency in services/*/src/main.py
- [X] T026 Create CI workflows with path filters, contract-change downstream validation, Gitleaks, Trivy, pip-audit, SBOM in .github/workflows/ci.yml
- [X] T027 [P] Create Bicep skeleton: naming module, one module per resource type, main.bicep, *.bicepparam.example in infra/bicep/
- [X] T028 Add a compose smoke test that boots with zero cloud credentials in infra/tests/test_compose_smoke.py
- [X] T139 [P] Create the minimal OIDC deploy workflow (connector job only, manual production approval, pinned digests) so early capture in Azure can start after US1; US7 extends it to all services in .github/workflows/deploy.yml

---

## Phase 3: User Story 1 - Trustworthy inventory and movement data (Priority: P1)

**Purpose**: Read-only collection from Siweb with allowlist, rate budget, reconciliation and quarantine.

- [X] T029 [P] [US1] Contract test: every method/path/host/redirect outside the reader allowlist is refused before sending in services/siweb-connector/tests/contract/test_allowlist.py
- [X] T030 [P] [US1] Contract test: dropped fields (supplier_cif, notes) never reach storage; only has_note kept in services/siweb-connector/tests/contract/test_minimisation.py
- [X] T031 [P] [US1] Integration test: backfill resumes across nights without gaps or duplicates and respects the request budget in services/siweb-connector/tests/integration/test_backfill.py
- [X] T032 [P] [US1] Integration test: quarantine cases (malformed expiry, missing warehouse, unreferenced sale) in services/siweb-connector/tests/integration/test_quarantine.py
- [X] T033 [P] [US1] Create integration schema migrations (sync_runs, sync_checkpoints, external_mappings, import_errors, raw_payload_index, rate_budget_log, outbox) in services/siweb-connector/migrations/versions/0001_integration.py
- [X] T034 [US1] Implement closed allowlist + host check in services/siweb-connector/src/allowlist/allowlist.py (per specs/001-mmi-purchase-intelligence/contracts/siweb-allowlist.md)
- [X] T035 [US1] Implement typed Siweb reader client with three pagination shapes, retry and 429/401 handling in services/siweb-connector/src/client/reader.py
- [X] T036 [P] [US1] Implement token-bucket rate limiter (≤ 500 req/h, night window) in services/siweb-connector/src/ratelimit/bucket.py
- [X] T037 [P] [US1] Implement Key Vault token provider (reader identity) with local env stub in services/siweb-connector/src/client/token.py
- [X] T038 [US1] Implement sync orchestration with frozen date_to, dedupe by movement id, checkpoints and count reconciliation in services/siweb-connector/src/sync/runner.py
- [X] T039 [P] [US1] Implement mapping/normalisation (UTC + raw timestamp, Decimal costs, unassigned warehouse, variant_id key) in services/siweb-connector/src/mapping/normalise.py
- [X] T040 [P] [US1] Implement data-quality gates writing import_errors in services/siweb-connector/src/mapping/quality.py
- [X] T041 [P] [US1] Implement raw payload writer to Blob after field stripping with retention metadata in services/siweb-connector/src/sync/raw_store.py
- [X] T042 [US1] Implement outbox publishing of siweb.sync.completed.v1 in services/siweb-connector/src/outbox/publisher.py
- [X] T043 [US1] Implement inventory projections: warehouses, products (tombstone after N missed syncs), variants, snapshots, lots, movements in services/inventory-service/src/projections/ and migration services/inventory-service/migrations/versions/0001_inventory.py
- [X] T044 [P] [US1] Implement inbox consumer for siweb.sync.completed.v1 in services/inventory-service/src/projections/consumer.py
- [X] T045 [P] [US1] Implement connector job entrypoint and ACA Job definition in services/siweb-connector/src/main.py and infra/bicep/modules/containerAppJob.bicep
- [X] T141 [P] [US1] Unit test: a product is marked discontinued only after N consecutive missed syncs (default 3), reappearance reactivates it, and a single failed run never tombstones in services/inventory-service/tests/test_tombstone.py
- [X] T142 [P] [US1] Unit test: free-text notes are never stored or used in any decision (has_note flag only) in services/inventory-service/tests/test_notes_minimisation.py
- [X] T046 [US1] Add alerts for failed syncs, quota denials and allowlist refusals in infra/bicep/modules/alerts.bicep (T122 extends the same file; do not run in parallel)
- [X] T136 [P] [US1] Implement raw-payload retention: Blob lifecycle rule and a purge job deleting payloads past expires_at (default 90 days, configurable) with a test that expired payloads are removed and unexpired ones kept, in infra/bicep/modules/storage.bicep and services/siweb-connector/src/storage/purge.py

---

## Phase 4: User Story 2 - Reliable demand picture per product (Priority: P1)

**Purpose**: Demand from movements, separate loss series, cutover classification, censoring.

- [X] T047 [P] [US2] Unit test: demand = sale_shipment − return_customer; other reasons excluded in services/inventory-service/tests/test_demand.py
- [X] T048 [P] [US2] Unit test: loss classification before/after cutover date; reclassification on cutover change in services/inventory-service/tests/test_losses.py
- [X] T049 [P] [US2] Unit test: backward stock reconstruction, censoring and mismatch flag in services/inventory-service/tests/test_stock_history.py
- [X] T050 [P] [US2] Create migrations for demand_observations, flow_series, stock_history, data_quality_metrics, config_loss_cutover in services/inventory-service/migrations/versions/0002_demand.py
- [X] T051 [US2] Implement DemandProvider interface with movements implementation in services/inventory-service/src/demand/provider.py
- [X] T052 [P] [US2] Implement loss classifier with configurable cutover (default 2026-09-19) in services/inventory-service/src/demand/losses.py
- [X] T053 [P] [US2] Implement backward on-hand reconstruction and censored days in services/inventory-service/src/demand/stock_history.py
- [X] T054 [US2] Implement quarantine exclusion and review release flow in services/inventory-service/src/quality/review.py
- [X] T055 [P] [US2] Implement data-quality metric: share of post-cutover negative adjustments without reason in services/inventory-service/src/quality/metrics.py
- [X] T056 [US2] Publish inventory.snapshot.created.v1 and inventory.demand.updated.v1 in services/inventory-service/src/demand/publisher.py
- [X] T057 [P] [US2] Expose inventory API endpoints (variant detail, review list) in services/inventory-service/src/api/routes.py

---

## Phase 5: User Story 3 - Product classification and forecast eligibility (Priority: P2)

**Purpose**: ABC/XYZ, demand patterns, policies, rolling backtests, eligibility, service levels.

- [ ] T058 [P] [US3] Unit test: ABC/XYZ and pattern classification on known synthetic profiles in services/inventory-service/tests/test_classification.py
- [ ] T059 [P] [US3] Unit test: eligibility flags and conservative min/max fallback in services/forecast-service/tests/test_eligibility.py
- [ ] T060 [P] [US3] Unit test: rolling-origin backtest scoring by stockout/holding/expiry cost in services/forecast-service/tests/test_backtest.py
- [ ] T061 [P] [US3] Create migrations for product_segments, service_level_config in services/inventory-service/migrations/versions/0003_segments.py
- [ ] T062 [P] [US3] Create forecasting migrations (forecast_runs, forecast_values, backtest_metrics, model_registry) in services/forecast-service/migrations/versions/0001_forecasting.py
- [ ] T063 [US3] Implement ABC/XYZ/pattern classification in services/inventory-service/src/classification/segments.py
- [ ] T064 [P] [US3] Implement clinical-criticality manual flag and API in services/inventory-service/src/classification/criticality.py
- [ ] T065 [US3] Implement policy ladder (min/max Poisson/NB, moving average, seasonal naive, Croston/TSB/ADIDA candidates) in services/forecast-service/src/policies/
- [ ] T066 [US3] Implement rolling-origin backtests with economic scoring in services/forecast-service/src/backtest/runner.py
- [ ] T067 [P] [US3] Implement forecast run versioning and uncertainty output in services/forecast-service/src/runs/
- [ ] T068 [P] [US3] Implement service-level config with defaults, per-product override and change history in services/inventory-service/src/classification/service_levels.py
- [ ] T069 [US3] Publish forecast.completed.v1 and add the forecast job definition in services/forecast-service/src/main.py and infra/bicep/modules/containerAppJob.bicep

---

## Phase 6: User Story 4 - Supplier costs and terms with provenance (Priority: P2)

**Purpose**: Versioned costs, recargo handling, price lists, staleness, jump blocking, supplier terms.

- [ ] T070 [P] [US4] Unit/property test: recargo math (10%→1.4%, 21%→5.2%), net↔gross round trip, unknown VAT rejection in services/procurement-service/tests/test_recargo.py
- [ ] T071 [P] [US4] Unit test: version immutability, staleness and jump blocking in services/procurement-service/tests/test_costs.py
- [ ] T072 [P] [US4] Unit test: price-list CSV/Excel import validation and error list in services/procurement-service/tests/test_price_import.py
- [ ] T073 [P] [US4] Create procurement migrations (suppliers, supplier_terms, supplier_costs, recargo_rates config, audit_events with hash chain) in services/procurement-service/migrations/versions/0001_costs.py
- [ ] T074 [US4] Implement recargo calculator with versioned rate table and rounding rule in services/procurement-service/src/costs/recargo.py
- [ ] T075 [US4] Implement immutable cost versions with source, verified_at, supersession in services/procurement-service/src/costs/store.py
- [ ] T076 [P] [US4] Implement ERP cost ingestion from supplier rows (cost treated as with-recargo; supplier_cif ignored) in services/procurement-service/src/costs/siweb_import.py
- [ ] T077 [P] [US4] Implement staleness rule and abnormal-jump detection (defaults 30 days, ±25%, configurable) in services/procurement-service/src/costs/rules.py
- [ ] T078 [P] [US4] Implement per-variant override and cost-not-found requirement for proposal use in services/procurement-service/src/costs/resolve.py
- [ ] T079 [P] [US4] Implement price-list import (fixed template, CSV/Excel via openpyxl) in services/procurement-service/src/costs/price_import.py
- [ ] T080 [P] [US4] Implement supplier terms CRUD with versioning in services/procurement-service/src/terms/
- [ ] T081 [P] [US4] Implement hash-chained audit events in services/procurement-service/src/audit/chain.py
- [ ] T082 [P] [US4] Expose cost and terms endpoints per contracts/bff-api.openapi.yaml in services/procurement-service/src/api/costs.py

---

## Phase 7: User Story 5 - Explainable weekly proposal, approval and ordering (Priority: P1)

**Purpose**: Replenishment targets, supplier allocation, proposals, separation of duties, order confirmation, cost write-back, exports.

- [ ] T083 [P] [US5] Unit test: replenishment targets (H = 7d + lead time, inventory position, expiring lots) in services/procurement-service/tests/test_targets.py
- [ ] T084 [P] [US5] Property test: allocation respects minimums, thresholds, pack multiples, budget, overrides in services/procurement-service/tests/test_allocation.py
- [ ] T085 [P] [US5] Unit test: proposal reproducibility from inputs_hash and rule versions in services/procurement-service/tests/test_reproducibility.py
- [ ] T086 [P] [US5] Unit test: separation of duties (creator and last editor cannot approve; edit resets eligibility; stale MFA refused) in services/procurement-service/tests/test_approval.py
- [ ] T087 [P] [US5] Contract test: cost-writer allowlist allows only the supplier-cost PUT and refuses everything else in services/siweb-cost-writer/tests/test_allowlist.py
- [ ] T088 [P] [US5] Integration test: cost write flow (missing cost, order confirmed, failure + visible retry, read-after-write verification, forged message rejected) in services/siweb-cost-writer/tests/test_write_flow.py
- [ ] T089 [P] [US5] Create migrations for replenishment_targets, proposals, proposal_lines, supplier_order_groups, approvals, inbound_orders, inbound_order_lines, cost_write_requests in services/procurement-service/migrations/versions/0002_proposals.py
- [ ] T090 [P] [US5] Create costwrite migrations (write_attempts, writer_audit) in services/siweb-cost-writer/migrations/versions/0001_costwrite.py
- [ ] T091 [US5] Implement replenishment target engine in services/procurement-service/src/proposals/targets.py
- [ ] T092 [US5] Implement greedy baseline allocation in services/procurement-service/src/allocation/greedy.py
- [ ] T093 [US5] Implement OR-Tools CP-SAT allocation with fixed-charge minimums, free-delivery thresholds, time box and fallback in services/procurement-service/src/allocation/cpsat.py
- [ ] T094 [US5] Implement top-up / reallocation / shortfall options with cost impact in services/procurement-service/src/allocation/shortfall.py
- [ ] T095 [US5] Implement proposal generation, line explanations (structured) and input/rule-version recording in services/procurement-service/src/proposals/generate.py
- [ ] T096 [P] [US5] Implement proposal edit with optimistic concurrency and constraint re-validation in services/procurement-service/src/proposals/edit.py
- [ ] T097 [US5] Implement submit/approve state machine with separation of duties and MFA freshness in services/procurement-service/src/approvals/workflow.py
- [ ] T098 [US5] Implement per-supplier order confirmation (actual qty/cost) and inbound projection event in services/procurement-service/src/orders/confirm.py
- [ ] T099 [P] [US5] Implement receipt matching to purchase_receipt movements (plain id and 'Compra #n') in services/procurement-service/src/orders/reconcile.py
- [ ] T100 [US5] Implement cost_write_requests creation for missing-cost entry and order-confirmed differences, including variant-conflict warning and fresh-MFA release, in services/procurement-service/src/costs/writes.py (real-ERP use blocked until T135)
- [ ] T140 [US5] Implement and test the `pending_link` path: no product–supplier record in the ERP means no call, the pair is flagged in the UI and the cost stays local, in services/procurement-service/src/costs/writes.py and services/siweb-cost-writer/tests/test_no_link.py
- [ ] T101 [US5] Implement the cost writer: allowlist, read-modify-write of purchase cost only, read-after-write verification, bounded retries, hash-chained audit in services/siweb-cost-writer/src/writer/
- [ ] T102 [P] [US5] Implement writer identity separation (own Key Vault access policy, egress limited to Siweb host) in infra/bicep/modules/costWriter.bicep
- [ ] T103 [P] [US5] Implement CSV and Excel exports in Spanish locale profile (Spanish headers, semicolon CSV, comma decimals; test asserts all three) in services/procurement-service/src/proposals/export.py and services/procurement-service/tests/test_export_locale.py
- [ ] T104 [P] [US5] Publish procurement.proposal.generated.v1 and procurement.order.confirmed.v1 in services/procurement-service/src/proposals/publisher.py
- [ ] T105 [P] [US5] Expose proposal/order/cost-write endpoints per contracts/bff-api.openapi.yaml in services/procurement-service/src/api/proposals.py

---

## Phase 8: User Story 6 - Spanish insight and risk dashboard (Priority: P2)

**Purpose**: BFF, RBAC, SPA screens, daily risk evaluation, es-ES.

- [ ] T106 [P] [US6] UI test: role matrix (viewer/buyer/approver/admin) in apps/web/tests/e2e/roles.spec.ts
- [ ] T107 [P] [US6] UI test: fails on hard-coded or missing translation keys and checks es-ES formats in apps/web/tests/unit/i18n.test.ts
- [ ] T108 [P] [US6] E2E test: warehouse breakdown and company-wide views in apps/web/tests/e2e/warehouses.spec.ts
- [ ] T109 [US6] Implement BFF OIDC login, cookie session (Secure/HttpOnly/SameSite), CSRF and step-up MFA check in services/api-bff/src/auth/
- [ ] T110 [P] [US6] Implement BFF RBAC per route and request validation/limits in services/api-bff/src/routes/rbac.py
- [ ] T137 [P] [US6] Implement admin role assignment/revocation (audited) and the "at least two eligible users" check before submit-for-approval, with tests for both and for recording refused attempts, in services/api-bff/src/routes/admin_roles.py and services/api-bff/tests/test_roles_admin.py
- [ ] T111 [P] [US6] Implement BFF clients and aggregation routes per contracts/bff-api.openapi.yaml in services/api-bff/src/routes/ and services/api-bff/src/clients/
- [ ] T112 [P] [US6] Implement daily risk evaluation (stockout, expiry, data quality) in services/inventory-service/src/risk/daily.py
- [ ] T113 [US6] Set up SPA shell, routing, API client from generated types and i18next es-ES in apps/web/src/app/ and apps/web/src/i18n/es-ES.json
- [ ] T114 [P] [US6] Build dashboard and risk screens in apps/web/src/features/dashboard/
- [ ] T115 [P] [US6] Build demand, losses and data-quality review screens in apps/web/src/features/quality/
- [ ] T116 [P] [US6] Build supplier cost, terms, price-list import and pending cost-write screens (recargo checkbox, review before send) in apps/web/src/features/costs/
- [ ] T117 [P] [US6] Build proposal screens: supplier-grouped view, explanations, editing, submit/approve, order confirmation, export in apps/web/src/features/proposals/
- [ ] T118 [P] [US6] Build service-level and cutover configuration screens in apps/web/src/features/config/
- [ ] T119 [P] [US6] Add accessibility labels and keyboard navigation checks in apps/web/tests/e2e/a11y.spec.ts

---

## Phase 9: User Story 7 - Safe, observable, budget-bounded operation (Priority: P2)

**Purpose**: Local run, replay/poison handling, alerts, budget, backup/restore, shadow period.

- [ ] T120 [P] [US7] Integration test: replayed, duplicated and forged messages and poison queue alert in services/procurement-service/tests/test_messaging_resilience.py
- [ ] T121 [P] [US7] Integration test: quota denials back off and alert; no partial data promoted on failed run in services/siweb-connector/tests/integration/test_failure_modes.py
- [ ] T122 [US7] Add metrics and alerts: sync freshness, queue age, quota use, cost-write outcomes, auth denials, unmatched writes, suspicious approvals in infra/bicep/modules/alerts.bicep (same file as T046; run after it)
- [ ] T143 [P] [US7] Test that every failure class has an alert rule and that rule evaluation windows total ≤ 1 hour end to end (SC-013): static check of the Bicep alert definitions; the compose stack cannot run Azure Monitor, so firing is proven by T145, in infra/tests/test_alert_rules.py
- [ ] T145 [US7] Post-deploy alert drill: inject a staged failure (failed sync, poison message) in the non-production cloud environment and record time-to-alert against the 1-hour target; add to the release checklist in docs/runbooks/alert-drill.md
- [ ] T144 [P] [US7] Performance test: proposal generation for the full synthetic catalogue completes within the plan target (under 2 minutes) and key API pages respond within target, in services/procurement-service/tests/perf/test_generation_time.py and services/api-bff/tests/perf/test_latency.py
- [ ] T123 [P] [US7] Add budget alerts at 50/80/100 % of the shared total and log ingestion cap in infra/bicep/modules/budget.bicep
- [ ] T124 [P] [US7] Set replica caps, job parallelism 1 and scale-to-zero for all workloads in infra/bicep/modules/containerApp.bicep
- [ ] T125 [P] [US7] Write backup configuration and restore drill procedure in docs/runbooks/restore-drill.md
- [ ] T126 [P] [US7] Write runbooks: failed sync, poison queue, token rotation (coordinated with the other app), failed cost write in docs/runbooks/
- [ ] T127 [P] [US7] Extend the deploy workflow from T139 to all services and the SPA, keeping manual production approval and pinned digests, in .github/workflows/deploy.yml
- [ ] T128 [US7] Create shadow-mode report comparing proposals with actual buyer decisions and outcomes in services/procurement-service/src/proposals/shadow_report.py

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Final verification, docs, hygiene.

- [ ] T130 [P] Complete threat model in the internal wiki using security/threat-model-template.md (incl. writer residual risk)
- [ ] T131 [P] Update docs/architecture/implementation-plan.md revision and any ADR status changes after Gate 0
- [ ] T132 [P] Run quickstart.md scenarios end to end and fix gaps (specs/001-mmi-purchase-intelligence/quickstart.md)
- [ ] T133 [P] Cost review against shared EUR 120 budget with real regional prices (internal)
- [ ] T134 Final secret-scan and dependency/container scan pass across the repo

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 (blocks everything) → user story phases → Phase 10.
- Gate 0 (T129, T135) sits in Phase 1: T129 must finish before live collection and before the defaults it covers are relied on; T135 must finish before T100/T101 touch the real ERP. Work against the mock is not blocked.
- Task IDs T135, T136, T137, T139, T140, T141, T142, T143, T144 and T145 were added by analysis remediation (T138 is unused) and are placed by phase, not in numeric order; T129 moved here from Phase 10.
- US1 (collection) → US2 (demand) → US3 (classification/policies) .
- US4 (costs) needs Phase 2 and the procurement audit chain; it can run in parallel with US2/US3.
- US5 (proposals) needs US3 (policies, service levels), US4 (costs, terms) and US1/US2 (stock, demand).
- US6 (UI) consumes endpoints as they land; screens per story can start once that story's API contract is stubbed.
- US7 spans the system; resilience tests and Bicep modules can start after Phase 2 and finish last.
- Within a story: tests first (must fail) → migrations → core logic → publishers/endpoints.

## Parallel Opportunities

- Phase 2: contracts, shared libraries, generator, Siweb mock, Dockerfiles and Bicep skeleton are independent files.
- US1: all test tasks together; rate limiter, token provider, mapping, quality gates and raw store in parallel.
- US3 and US4 run in parallel by different developers; US4 recargo/cost rules are independent of forecasting.
- US5: allocation (greedy/CP-SAT) and the cost writer are separate services and can proceed in parallel.

## Implementation Strategy

1. **MVP data slice**: Phases 1–2 → US1 (collect and reconcile, early capture can start in Azure as soon as US1 passes) → US2 (demand picture). Validate with the quickstart sections 1–3.
2. **Buying slice**: US3 + US4 in parallel → US5 (proposals, approval, order confirmation, cost write-back) → US6 UI. Run in shadow mode.
3. **Operate**: US7 hardening, Gate 0 results, restore drill, shadow review before production.
4. Do not enable the cost write against the real Siweb until T135 (research item V4, PUT semantics) is verified on a non-production record.

## Task Summary

| Phase | Tasks |
|---|---|
| Phase 1: Setup (incl. Gate 0) | 11 |
| Phase 2: Foundational | 20 |
| Phase 3: User Story 1 - Trustworthy inventory and movement data | 21 |
| Phase 4: User Story 2 - Reliable demand picture per product | 11 |
| Phase 5: User Story 3 - Product classification and forecast eligibility | 12 |
| Phase 6: User Story 4 - Supplier costs and terms with provenance | 13 |
| Phase 7: User Story 5 - Explainable weekly proposal, approval and ordering | 24 |
| Phase 8: User Story 6 - Spanish insight and risk dashboard | 15 |
| Phase 9: User Story 7 - Safe, observable, budget-bounded operation | 12 |
| Phase 10: Polish & Cross-Cutting Concerns | 5 |
| **Total** | **144** |
