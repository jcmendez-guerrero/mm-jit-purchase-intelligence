# Research: Architecture, Contracts & Integration

No `NEEDS CLARIFICATION` remained after the clarification session; the items below resolve the planning-level unknowns.

## R1. How the audit classifies features with evidence

- **Decision**: One JSON record per feature (`id`, `title`, `status`, `evidence[]` as `path:line`, `owner`, `notes`), rendered to Markdown. Status is one of complete, partial, broken, missing, unverified. "Complete" requires an evidence reference to both code and a passing test or demonstration; otherwise "unverified".
- **Rationale**: Mirrors FR-001 and the edge case "appears complete but no test". JSON is validated by a schema and spot-checkable.
- **Alternatives**: Markdown only (not machine-checkable); a database (overkill, public repo).

## R2. Where the contract matrix comes from

- **Decision**: `contract-matrix.json` is partly generated from `packages/contracts/dto`, `events` and `errors` (name, version from the `vN` suffix, schema path) and partly curated (owner, consumers, status). The gate fails if a schema file has no matrix entry or a matrix entry points to no file.
- **Rationale**: The repo already versions schemas by file suffix and has a baseline compatibility check (`baseline/`, `update_baseline.py`, `test_compat.py`). Reusing them avoids a second source of truth.
- **Alternatives**: OpenAPI-only matrix (does not cover events); a separate registry service (new cost and infrastructure).

## R3. Freezing and breaking changes

- **Decision**: "Frozen" is a matrix status plus the existing baseline snapshot. A breaking change adds `name.v2` next to `name.v1`; v1 becomes `deprecated` and stays until every consumer in the matrix lists v2 (clarification Q3).
- **Rationale**: Matches the `vN` convention and the constitution's rule on coordinated rollouts.
- **Alternatives**: In-place change with synchronized consumers (breaks parallel work); additive-only (too rigid).

## R4. Detecting cross-schema reads

- **Decision**: Static scan of SQL in each service's migrations and source for `schema.table` references and `SET search_path`, comparing against the service's own schema (from the schema ownership list in the matrix). Plus the existing PostgreSQL migration test for role grants.
- **Rationale**: Cheap, runs offline with synthetic fixtures, catches regressions before runtime; grants verified separately.
- **Alternatives**: Runtime query logging (needs infrastructure); relying on role grants alone (misses code that would fail only at runtime).

## R5. Gate execution and "not run"

- **Decision**: Six gates (contracts, isolation, integration, e2e, security, cost). Each returns `pass`, `fail` or `not_run` with evidence. The aggregate exit code is non-zero unless all gates pass. Contracts, isolation and integration gates are native (integration passes only when every plan step is integrated, or dropped with a recorded reason); end-to-end, security and cost wrap existing suites (`infra/tests/test_pipeline_e2e.py`, `test_security_abuse.py`, `test_erp_boundary.py`, `test_cost_guardrails.py`, and the Playwright suite).
- **Rationale**: Satisfies FR-009/FR-010 with minimum new code.
- **Alternatives**: Re-implementing suites (duplication).

## R6. Cost gate

- **Decision**: Reuse `test_cost_guardrails.py` and add an assertion that the sum of the maximum replica/job caps in the Bicep parameters stays within the documented envelope; the budget figure (about EUR 120) is read from one documented constant.
- **Rationale**: No billing API is needed; the check is deterministic.
- **Alternatives**: Query Azure Cost Management (needs credentials, forbidden in CI here).

## R7. Integration branch and failure handling

- **Decision**: `integrate.py` reads `integration-plan.json` (ordered PRs with `depends_on`), creates a local temporary branch from main, merges each PR head in order, runs the gates, and on failure drops the failing PR plus all transitive dependents, then continues. It never pushes and never touches main. Dropped PRs are written to the report with the failing gate and cause for the owning agent. Failure handling: a failed merge is undone by resetting to the commit saved before it (a merge that adds nothing makes no commit, so `HEAD~1` would undo the previous PR); a PR whose head does not exist is dropped with `failed_gate: ref` and the run continues; an invalid plan (unknown `depends_on`, a cycle, overlapping owners) is refused before anything is built and the command exits 3.
- **Rationale**: Clarification Q1 and Q2. Dependent-closure is a simple graph walk.
- **Alternatives**: Verify each PR alone (misses interaction bugs); stop on first failure (blocks independent work).

## R8. Agent watching and auto-fix

- **Decision**: The repo provides the machine-readable gate report (and CI status) as the signal; each agent's own tooling watches it and fixes within its owned files. Ownership is an `owned_paths` list per agent in `integration-plan.json`, and the integration script rejects a PR whose diff touches another agent's paths.
- **Rationale**: FR-010a without adding a service; ownership check makes "no editing other agents' files" enforceable.
- **Alternatives**: A bot service (new cost, new attack surface).

## R9. ADR location

- **Decision**: `docs/architecture/adr/NNN-title.md` (context, decision, consequences), indexed from `implementation-plan.md`. Existing decisions already numbered there (for example ADR-006) are linked, not rewritten.
- **Alternatives**: Keep everything in `implementation-plan.md` (grows unwieldy, poor per-decision diffs).

## R10. Spanish UI demonstration

- **Decision**: Two layers. The existing Playwright suite with mocked backends stays as a separate fast check. A new browser journey under `apps/web/tests/live/` runs against the local compose stack (real services, synthetic data) and is part of the e2e gate; only it satisfies FR-011. Cross-domain integration tests go under `infra/tests`. Screenshots go in the PR, not committed binaries beyond the existing evidence folder. The existing localization test (`test_error_keys_localised.py`) covers es-ES text (FR-018).
- **Rationale**: FR-011 requires API-backed evidence; mocked backends cannot prove the screens work with the real services.
- **Alternatives**: Mocked suite only (rejected by clarification); replace the mocked suite (slower feedback).

## R11. Publishing gate results for agent watch and auto-fix

- **Decision**: A manually started workflow (`integration-gates.yml`) checks out main, builds the integration branch inside the run with `python -m gates integrate` (fetching each PR head, nothing pushed), runs the gates, uploads the JSON report as a CI artifact and posts `python -m gates summary --pr N` output as a comment on each domain PR with the repository token. Agents read PR checks, the comment and the artifact. No new service.
- **Alternatives**: Bot service (new cost and attack surface); local file only (agents cannot see it).

## R12. Which gates are required checks

- **Decision**: `contracts` and `isolation` run on every PR and are required; all six are required on the integration branch (FR-010). The slow gates stay off normal PRs.
- **Alternatives**: All six on every PR (slow, costly); integration branch only (a PR could break contracts unnoticed until late).

## R13. Platform guarantees

- **Decision**: `docs/architecture/integration/guarantee-test-map.md` maps role-based access, second factor, audit trail, UTC timestamps and decimal money to existing tests; a test fails if a mapped test file is missing or not part of the security gate. New tests are added only for unmapped guarantees (FR-013).

## R14. Run time

- **Decision**: No limit yet. The report records per-gate start and finish times; the first full run is recorded in the PR and the limit is set from it (SC-008).
