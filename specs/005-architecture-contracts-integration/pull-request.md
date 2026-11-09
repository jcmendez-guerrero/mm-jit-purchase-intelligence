# PR description (draft, not opened)

**Title:** feat: architecture, contracts and integration gates (MMI-2, Agent 00)

Links: Jira [MMI-2](https://mundomascotix.atlassian.net/browse/MMI-2), epic MMI-1, Confluence page "MMI 003 / Agent 00" (pages/3112981). Spec: `specs/005-architecture-contracts-integration/`.

## What and why

Coordination layer for the parallel MMI-1 effort: an evidence-based audit of main, a machine-checked contract matrix, three ADRs (021 to 023), and a standard-library gate runner (`python -m gates`) with six gates: contracts, isolation, integration, e2e, security, cost. An `integrate` command builds a throwaway integration tree from the domain PRs, drops failing PRs with their dependents and never pushes. Tasks T001 to T049 and T050/T051 of `tasks.md`.

## Changes

- `scripts/gates/` (new), tests in `scripts/tests/gates/` (63 tests)
- `docs/architecture/integration/`: audit (31 features: 27 complete, 2 partial, 2 unverified), contract matrix (27 DTOs, 14 events, error codes, 98 gateway endpoints), gateway review, guarantee-to-test map, verification record
- `docs/architecture/adr/021` to `023`, one row added to `docs/architecture/implementation-plan.md`
- `.github/workflows/ci.yml` (new `gates` job), `.github/workflows/integration-gates.yml` (new, manual)
- `services/api-bff/tests/test_gateway_composition.py`, `test_gateway_idempotency.py` (tests only; no service code changed)
- one pointer line each in `AGENTS.md` and `CLAUDE.md`

## Migration impact

None. No database, schema-file or service code changes. Contract schemas are untouched.

## Evidence

- `pytest scripts/tests/gates`: 63 passed. Gateway tests: 4 passed.
- First full gate run: 1 min 20 s; contracts, isolation, security, cost pass; integration not_run; e2e **fail** (see `docs/architecture/integration/verification.md`).
- Real-services Spanish UI journey (`apps/web/tests/live/journey.spec.ts`): 1 passed against a local compose stack with no synthetic data loaded; screenshots in `docs/architecture/evidence/005-live-*.png`. `test_error_keys_localised.py`: 6 passed.

## Known limitations

- `integration-plan.json` is missing: needs the maintainer's list of sibling PRs (T030). `python -m gates validate` exits 3 until then, and the integration gate reports `not_run`.
- The e2e gate failed in the author's environment: two service containers were killed with exit 137 (likely out of memory: a 2 GB Docker VM with another `mmi` stack running). With that stack stopped, the pipeline e2e tests passed (one run), supporting the memory explanation. After installing the web dependencies, the fast browser suite also passed (189 passed, 6 skipped). The e2e gate reports `not_run` unless the compose stack is up and `PLAYWRIGHT_BASE_URL` is set; the journey itself passed when run by hand, but the integration workflow does not start the stack yet.
- Audit statuses are not backed by a test run. Gateway endpoints are `draft` in the matrix. Of 54 mutating gateway endpoints only one declares an idempotency key; repeat safety of the rest is for the domain owners to confirm.
- The two new workflows have never run on GitHub.

## Checklist (from the template)

- Data: synthetic only; no real exports, SKUs, suppliers or e-mails (only `@example.test` placeholders). Passes `scripts/check_export_signatures.py`.
- Security: no secrets or IDs; no Siweb access added or changed; in the new manual workflow the job that runs merged PR code has `contents: read` only; a separate job with `pull-requests: write` and `actions: read` runs trusted code from the default branch and treats the report as untrusted data.
- Cost: no new resource; adds CI minutes only.
- Contracts: no schema changes; the contracts gate and existing baseline tests pass.
- Quality: tests added; no user-facing text added; constitution v1.3.0 and ADR-018/020 checked.

No merge, deployment or ERP write is part of this PR.
