# PR description

**Title:** feat: architecture, contracts and integration gates (MMI-2, Agent 00)

Links: Jira [MMI-2](https://mundomascotix.atlassian.net/browse/MMI-2), epic MMI-1, Confluence page "MMI 003 / Agent 00" (pages/3112981). Spec: `specs/005-architecture-contracts-integration/`.

## What and why

The coordination layer for the parallel MMI-1 effort: an evidence-based audit of main, a machine-checked contract matrix, three ADRs (021 to 023), and a standard-library gate runner (`python -m gates`) with six gates: contracts, isolation, integration, e2e, security, cost. An `integrate` command builds a throwaway integration tree from the domain PRs, drops failing PRs with their dependents, and never pushes or merges. 73 of 76 tasks in `tasks.md` are done; the rest are listed under Known limitations.

## Changes

- `scripts/gates/` (new) and 94 tests in `scripts/tests/gates/`. Commands: `validate`, `run`, `integrate`, `summary`, `lookup`, `matrix`, `matrix-md`, `audit-md`.
- `docs/architecture/integration/`: audit (31 features: 27 complete, 2 partial, 2 unverified), contract matrix (27 DTOs, 14 events, error codes and 98 gateway endpoints, owners curated), gateway review, guarantee-to-test map, README, verification record.
- `docs/architecture/adr/021` to `023`, plus one row in `docs/architecture/implementation-plan.md`.
- `.github/workflows/ci.yml`: new `gates` job (lint, gate tests, contracts and isolation gates). `.github/workflows/integration-gates.yml` (new, manual): builds the integration tree, runs all six gates, uploads the report and comments on each domain PR. The job that runs merged PR code is read-only; a separate job holds the comment permission and runs only trusted code.
- `services/api-bff/tests/`: three gateway tests (composition without business rules, idempotency keys pinned, endpoints equal the matrix). Tests only; no service code changed.
- `apps/web`: a real-services Spanish UI journey (`tests/live/journey.spec.ts`) and its Playwright config.
- `infra/tests/test_cost_guardrails.py`: failure messages now name the Bicep file and setting.
- One pointer line each in `AGENTS.md` and `CLAUDE.md`.

## Migration impact

None. No database, shared schema or service code changes.

## Evidence

- `pytest scripts/tests/gates`: 94 passed. `ruff check` on the new code: clean. Gateway tests: 5 passed.
- A clean timed run of all gates (database check and live stack on) took 2 min 57 s: contracts, isolation, e2e, security and cost **pass**; integration is `not_run` because the plan is empty (see below). Per-gate times are in `docs/architecture/integration/verification.md`.
- Pipeline e2e tests, the fast browser suite (189 passed, 6 skipped) and the real-services journey (1 passed) all pass; an earlier e2e failure was containers killed with exit 137 in a 2 GB Docker VM that was also running another stack (explained in the verification record).
- Screenshots: `docs/architecture/evidence/005-live-*.png` (empty synthetic data, so they show the wiring, not data).

## Known limitations

- `integration-plan.json` is not created yet (T030): the plan starts with this PR, whose number is only known now. Follow-up: add this PR as agent-00 step one, then `python -m gates validate` exits 0. Until then the integration gate reports `not_run` and `validate` exits 3.
- T052 (full quickstart run) follows T030. T061 is superseded by `python -m gates lookup` (SC-007), but its box is unchecked.
- The two new workflows have never run on GitHub; this PR is their first real run. The per-gate time limits are a first setting from one machine.
- Audit statuses are not backed by a test run. Gateway endpoints are `draft` in the matrix. Of 54 mutating gateway endpoints only one declares an idempotency key; repeat safety of the rest is for the domain owners to confirm (see the gateway review).
- The guarantee-to-test map lists known evidence gaps (for example no cross-service audit chain test).
- `scripts/` is outside strict `mypy` scope (CI does not run mypy); it is covered by `ruff`.

## Checklist (from the template)

- Data: synthetic only; no real exports, SKUs, suppliers or e-mails (only `@example.test` placeholders). Passes `scripts/check_export_signatures.py`.
- Security: no secrets or IDs; no Siweb access added or changed; the new workflow follows the trust split described above.
- Cost: no new resource; adds CI minutes only.
- Contracts: no change to shared schemas; the contracts gate and existing baseline tests pass.
- Quality: tests added; no user-facing text added; constitution v1.3.0 and ADR-018/020 checked.

No merge, deployment or ERP write is part of this PR.
