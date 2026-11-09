# Tasks: Architecture, Contracts & Integration (MMI 003 / Agent 00)

**Input**: `/specs/005-architecture-contracts-integration/` (plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md)

**Tests**: Included (AGENTS.md requires tests before implementation within a story). Synthetic fixtures only.

**Format**: `- [ ] ID [P?] [Story] Description with file path`. `[P]` = parallelizable. Stories: US1 audit, US2 contracts, US3 ADRs and sequencing, US4 gates, US5 gateway tests.

## Phase 1: Setup

- [X] T001 Create folders `docs/architecture/adr/`, `docs/architecture/integration/` and package `scripts/gates/` with `__init__.py` and a `__main__.py` stub
- [X] T002 [P] Copy the four schemas from `specs/005-architecture-contracts-integration/contracts/` to `docs/architecture/integration/schemas/` (the validated copy) and explain in `docs/architecture/integration/README.md` that the spec copy is the design source
- [X] T003 [P] Create `scripts/tests/gates/conftest.py` with synthetic helpers (temporary git repo, sample schemas)

## Phase 2: Foundational (blocks all stories)

- [X] T004 [P] Write tests for artifact validation (valid and invalid cases per schema) and for failing when the validated schema copies differ from the spec copies, in `scripts/tests/gates/test_validate.py`
- [X] T005 Implement `python -m gates validate` (exit 3 on invalid input; schema copies must be identical) in `scripts/gates/validate.py` and `scripts/gates/__main__.py`
- [X] T006 [P] Write tests for report building and exit codes (all pass 0, any fail 1, not-run without fail 2; six gates required; per-gate durations recorded) in `scripts/tests/gates/test_report.py`
- [X] T007 Implement the gate result model, UTC timestamps (keeping the original string), per-gate durations and aggregate exit code in `scripts/gates/report.py`

## Phase 3: US1 Evidence-based audit (P1) MVP

**Independent test**: validate `feature-status.json`; spot-check 10 rows (quickstart step 6).

- [X] T008 [P] [US1] Write a test failing on evidence pointing to a missing path or line beyond file length, and on a `complete` record without test evidence, in `scripts/tests/gates/test_audit_evidence.py`
- [X] T009 [US1] Implement the evidence checker in `scripts/gates/audit_check.py`
- [X] T010 [US1] Inventory services, endpoints, schemas, ownership, CI workflows, tests and merged PRs into `docs/architecture/integration/audit-inventory.md`
- [X] T011 [US1] Classify every feature of specs 001 to 004 with evidence and reuse flags in `docs/architecture/integration/feature-status.json`
- [X] T012 [US1] Render `docs/architecture/integration/feature-status.md` (status table, gaps by owner, reuse list)

## Phase 4: US2 Contract matrix and frozen interfaces (P1)

**Independent test**: quickstart steps 2 and 3.

- [X] T013 [P] [US2] Write tests for the contracts gate (missing entry, missing file, baseline mismatch, v2 plus deprecated v1, deprecated with unmoved consumers) in `scripts/tests/gates/test_contracts_gate.py`
- [X] T014 [P] [US2] Write tests for the isolation gate (foreign `schema.table` or `SET search_path` fails, own schema passes) in `scripts/tests/gates/test_isolation_gate.py`
- [X] T015 [US2] Implement the contracts gate in `scripts/gates/contracts_gate.py`, reusing `packages/contracts/tools/update_baseline.py` logic
- [X] T016 [US2] Implement the schema-isolation gate (static SQL scan of `services/*/`) in `scripts/gates/isolation_gate.py`
- [X] T017 [US2] Generate and curate the matrix (owners, consumers, status) in `docs/architecture/integration/contract-matrix.json`
- [X] T018 [US2] Record `schema_ownership` for the six services in `docs/architecture/integration/contract-matrix.json`
- [X] T019 [US2] Freeze stable entries and document the Agent 00 change-request procedure in `docs/architecture/integration/README.md`
- [X] T020 [US2] Render `docs/architecture/integration/contract-matrix.md`; name the gateway once as "gateway (`services/api-bff`)"
- [X] T021 [US2] Fix, or report to the owning domain, any real cross-schema reference found in `services/*/`

## Phase 5: US3 ADRs and integration sequencing (P2)

**Independent test**: quickstart step 5.

- [X] T022 [P] [US3] Write tests (ordering, transitive drop, foreign-path PR dropped as `touches_foreign_paths` including an auto-fix commit that touches another agent's files, main and remotes untouched) in `scripts/tests/gates/test_integrate.py`
- [X] T023 [US3] Implement `python -m gates integrate` (temporary local branch from main, ordered merges, drop failing PR plus dependents, never push) in `scripts/gates/integrate.py`; the gates are injected so it can be tested with stubs, and T042 wires the real gates
- [X] T024 [P] [US3] ADR-021 contract versioning (new version beside old) in `docs/architecture/adr/021-contract-versioning.md`
- [X] T025 [P] [US3] ADR-022 integration branch, drop-and-continue, report as CI artifact plus PR comment, agent auto-fix in `docs/architecture/adr/022-integration-branch.md`
- [X] T026 [P] [US3] ADR-023 gateway boundaries in `docs/architecture/adr/023-gateway-boundaries.md`
- [X] T027 [US3] Index the ADRs and link existing decisions (e.g. ADR-006) from `docs/architecture/implementation-plan.md`
- [X] T028 [US3] Document the watch-and-fix protocol (where agents read the report, auto-fix limited to own files, no merge to main, no ERP write, fixed PR re-enters only after passing) in `docs/architecture/integration/README.md`
- [X] T029 [P] [US3] Write tests that an integration plan entry with missing `owned_paths`, a dependency cycle, or an unknown gate name is rejected, in `scripts/tests/gates/test_integration_plan.py`
- [ ] T030 [US3] Create `docs/architecture/integration/integration-plan.json` from the list of sibling PRs, agents and owned paths supplied by the maintainer (PR numbers and paths only), and validate it with `python -m gates validate`

## Phase 6: US4 Release gates (P2)

**Independent test**: quickstart steps 1 to 4.

- [X] T031 [P] [US4] Write tests for the suite gate (unrunnable suite is `not_run`, failing suite is `fail` with evidence, no data values in evidence) in `scripts/tests/gates/test_suite_gate.py`
- [X] T032 [P] [US4] Write tests for the integration gate (passes when every step is `integrated` or `dropped` with a reason; fails on `pending` or a drop without a reason) in `scripts/tests/gates/test_integration_gate.py`
- [X] T033 [US4] Implement the integration gate in `scripts/gates/integration_gate.py`
- [X] T034 [US4] Implement the e2e gate part for the pipeline and approval tests and the fast fake-backend browser suite (`infra/tests/test_pipeline_e2e.py`, `test_approval_e2e.py`, Playwright in `apps/web`) in `scripts/gates/suite_gate.py`
- [X] T035 [US4] Add the real-services Spanish (es-ES) browser journey (compose stack, synthetic data) in `apps/web/tests/live/journey.spec.ts` and wire it into the e2e gate in `scripts/gates/suite_gate.py`
- [X] T036 [US4] Map each platform guarantee (role-based access, second factor, audit trail, UTC timestamps, decimal money) to an existing test in `docs/architecture/integration/guarantee-test-map.md`
- [X] T037 [P] [US4] Write a test that fails when a mapped test file is missing or not part of the security gate, in `scripts/tests/gates/test_guarantee_map.py`
- [X] T038 [US4] Add the security gate (guarantee-mapped tests, `infra/tests/test_security_abuse.py`, `test_erp_boundary.py`, `test_web_headers.py`, `scripts/check_export_signatures.py`) and new tests only for unmapped guarantees in `scripts/gates/suite_gate.py` and `infra/tests/`
- [X] T039 [US4] Add the cost gate (`infra/tests/test_cost_guardrails.py` plus a replica/job cap check against the EUR 120 constant; failure evidence names the contributing resources) in `scripts/gates/suite_gate.py` and `infra/tests/test_cost_guardrails.py`
- [X] T040 [P] [US4] Write tests for the report summary (Markdown with gate results, dropped PRs and durations; `--pr` filter; no data values) in `scripts/tests/gates/test_summary.py`
- [X] T041 [US4] Implement `python -m gates summary` in `scripts/gates/summary.py`
- [X] T042 [US4] Wire `python -m gates run --gate --report` for all six gates, the exit codes, and the real gates into `integrate` in `scripts/gates/__main__.py`
- [X] T043 [US4] Add a per-PR CI job running `validate` and the contracts and isolation gates, as required checks, in `.github/workflows/ci.yml`
- [X] T044 [US4] Create `.github/workflows/integration-gates.yml`, started manually (`workflow_dispatch`), checking out main with full history and running `python -m gates integrate` itself (fetching each PR head; nothing pushed), so all six gates run on the combined result, then uploading the report as an artifact and posting `python -m gates summary --pr N` as a comment on each domain PR (permissions limited to `pull-requests: write` and `contents: read`)
- [X] T045 [US4] Demonstrate the Spanish (es-ES) UI: run the live journey, capture screenshots for the PR, and confirm the existing localization test (`infra/tests/test_error_keys_localised.py`) passes

## Phase 7: US5 Gateway contracts and integration tests (P3)

- [X] T046 [P] [US5] Cross-domain composition test in `services/api-bff/tests/test_gateway_composition.py`
- [X] T047 [P] [US5] Idempotency test (same key, one effect) in `services/api-bff/tests/test_gateway_idempotency.py`
- [X] T048 [US5] Review `services/api-bff/` for business-rule logic; record findings in `docs/architecture/integration/gateway-review.md`
- [X] T049 [US5] Register gateway endpoints (kind `endpoint`, owner Agent 00) in `docs/architecture/integration/contract-matrix.json` and rerun the contracts gate

## Phase 8: Polish

- [X] T050 [P] Run the secret scan and export-signature check on the new files (synthetic data only, no real names or identifiers)
- [X] T051 [P] Add a one-line pointer to `docs/architecture/integration/` in `AGENTS.md` and `CLAUDE.md`
- [ ] T052 Run the quickstart end to end, time the first full gate run (SC-008) and record outcomes and duration in `docs/architecture/integration/verification.md`
- [X] T053 Prepare the single PR from `.github/pull_request_template.md` (summary, migration impact, screenshots, test evidence, limitations, first-run duration, links to the Confluence page and MMI-2). No merge, deploy or ERP write

## Dependencies and Order

- Phase 1, then Phase 2, then stories. US1 and US2 are independent and can run in parallel.
- T023 is testable with stub gates; T042 depends on T015, T016, T033, T034–T039 and wires the real gates into it.
- T030 needs the list from the maintainer; T033 needs T030 or a fixture plan.
- US4 needs the US2 gates (T015, T016). T044 needs T041 and T042. US5's T049 needs T017.
- Polish last; T052 follows T044.
- Parallel examples: T008, T013, T014 together; T024–T026 together; T031, T032, T037, T040 together; T046, T047 together.

## Implementation Strategy

MVP is Phase 1, Phase 2 and US1, then US2 to freeze contracts so other agents can proceed. Then US3 and US4, then US5, polish and the single PR. Mark tasks `[X]` as completed.

## Phase 9: Convergence

- [X] T054 Split `.github/workflows/integration-gates.yml` into an untrusted job (merges and runs PR code with `contents: read` only, uploads the report) and a separate comment job that downloads the report artifact and holds `pull-requests: write`, so no PR code runs where the write token is available per FR-010a and ADR-022 (partial)
- [X] T055 Add an endpoint-drift check to the contracts gate in `scripts/gates/contracts_gate.py`: compare the gateway's exported OpenAPI against the `endpoint` entries in `docs/architecture/integration/contract-matrix.json`, with a test in `scripts/tests/gates/test_contracts_gate.py` per FR-005 (partial)
- [X] T056 Wire the PostgreSQL role-grant check (`infra/tests/test_migrations_postgres.py`, run with `RUN_PG_MIGRATIONS=1`) into the isolation gate in `scripts/gates/isolation_gate.py`, reporting `not_run` when PostgreSQL is unavailable, per FR-006 and research R4 (partial)
- [X] T057 Make the cost gate match T039: add the replica and job cap check against the guardrail budget and have failure evidence name the contributing Bicep files or resources, in `scripts/gates/suite_gate.py` and `infra/tests/test_cost_guardrails.py`, or amend T039 to what was built, per FR-015 (partial)
- [X] T058 Document in `docs/architecture/integration/README.md` that the per-PR `gates` job must be a required check (branch protection) and how and when the maintainer starts `integration-gates.yml`, per FR-010 (missing)
- [X] T059 Review each test file in `docs/architecture/integration/guarantee-test-map.md` for real coverage of its guarantee; record gaps in that file and add tests only for guarantees that turn out uncovered, per FR-013 (partial)
- [X] T060 Update `docs/architecture/integration/README.md` so it no longer says only `contracts` and `isolation` are implemented, per plan documentation (partial)
- [ ] T061 Record a manual check in `docs/architecture/integration/verification.md` that a reader finds any interface's owner, version and consumers in `contract-matrix.md` in under 2 minutes, per SC-007 (missing)

## Phase 10: Convergence

- [X] T062 Make the integration run test the integrated tree: after `integrate` builds the worktree, install `packages/contracts` and `packages/testing` (and the service packages the suites use) from that tree before running the gates, via an option in `scripts/gates/integrate.py` and the install step of `.github/workflows/integration-gates.yml`, with a test that a change to `packages/contracts` in a PR is visible to the gates, per FR-008 and FR-009 (partial)
- [X] T063 Give the integration workflow what the e2e gate needs: pinned Node setup, `npm ci` and `npx playwright install chromium` in the integrated tree's `apps/web`, start the compose stack with `docker compose up --wait web`, export `PLAYWRIGHT_BASE_URL`, and tear the stack down afterwards, in `.github/workflows/integration-gates.yml`, so the e2e gate can pass instead of ending `not_run`, per FR-009, FR-010 and FR-011 (missing)
- [X] T064 Reject overlapping `owned_paths` between different agents in `plan_errors` in `scripts/gates/validate.py`, with a test in `scripts/tests/gates/test_validate.py`, per US3/AC3 and the shared-file edge case (partial)
- [X] T065 Curate the owners and consumers of the 16 schema entries that still carry the fallback owner `agent-00` in `docs/architecture/integration/contract-matrix.json`, keep the curation when `python -m gates matrix` regenerates the file, then re-render `contract-matrix.md`, per FR-004 and T017 (partial)
- [X] T066 Bring `specs/005-architecture-contracts-integration/contracts/gate-runner-cli.md` and the source tree in `plan.md` into line with the code: `matrix`, `matrix-md`, `audit-md`, `run --openapi`, `MMI_GATES_DATABASE`, and the modules `audit_check.py`, `guarantees.py`, `matrix.py`, `validate.py`, per plan: project structure (partial)
- [X] T067 Set per-gate time limits in `scripts/gates/suite_gate.py` from a clean full gate run (after T063) and record the numbers in `docs/architecture/integration/verification.md`, replacing the single 1,800 s constant, per SC-008 (partial)
- [X] T068 Classify the features no user story covers (deployment and Bicep, CI, mock services, dev issuer, local loader tooling) in `docs/architecture/integration/feature-status.json`, or state the audit's scope in `audit-inventory.md`, per FR-001 and SC-001 (partial)
