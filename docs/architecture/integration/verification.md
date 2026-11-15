# Verification record (feature 005)

Run on a developer machine at commit `9d11abb` plus the uncommitted changes of this feature. The environment was a Python 3.12 virtual environment with the contracts, testing, procurement, inventory and cost-writer packages installed, and a local Docker daemon that already had another `mmi` compose project running.

## First full gate run (SC-008)

`python -m gates run` from `scripts/`: **1 minute 20 seconds** in total.

| Gate | Result | Time | Note |
|---|---|---|---|
| contracts | pass | 0.5 s | 42 schema entries plus 98 gateway endpoints |
| isolation | pass | 0.4 s | no cross-schema reference in the six services |
| integration | not_run | 0.0 s | the integration plan is empty until the maintainer supplies the PR list (T030) |
| e2e | **fail** | 58.5 s | two `infra/tests/test_pipeline_e2e.py` tests failed: the `docker compose up --wait` they make exited non-zero because `procurement-service` and `inventory-service` containers were killed with exit 137 (SIGKILL, the usual sign of an out-of-memory kill). Docker's VM here has about 2 GB of memory and another 10-container `mmi` stack was already running. The test itself publishes no ports, so a port clash is ruled out. Re-run with the other stack stopped: the pipeline e2e tests **passed** (one run, about a minute), which supports the memory explanation. That re-run of the gate then stopped at `npm run e2e` (exit 127, `playwright: command not found`, because `apps/web/node_modules` was not installed); the gate now reports a missing tool as `not_run`, not `fail`. After `npm ci` and `npx playwright install chromium` in `apps/web`, a final gate run (1 min 40 s, other stack stopped) ran the pipeline e2e tests and the fast browser suite (189 passed, 6 skipped) without a failure; the gate result was **not_run** only because the live-stack journey needs a running stack and `PLAYWRIGHT_BASE_URL`. That journey (T035) was then run by hand against a separate compose project (`mmi-live`, only `web` and its dependencies, removed afterwards): **1 passed** (sign-in page, real `/api/dashboard/overview` returning 200, dashboard and Propuestas de compra headings in Spanish). Limits: the stack had no synthetic data loaded (the dashboard shows zeros and one card degraded to "No se pudo cargar este indicador"), so this proves the wiring, not the data. `infra/tests/test_error_keys_localised.py` passes (6 tests). Screenshots: `docs/architecture/evidence/005-live-*.png` (untracked). The first run, killed by a timeout before its teardown, also left an `mmi-e2e` project behind, which was removed. |
| security | pass | 19.0 s | 6 commands: mapped guarantee tests per service, `infra/tests` security tests, export-signature guard |
| cost | pass | 1.4 s | existing cost-guardrail and alert-rule tests |

The overall result of this first run was **fail** (e2e, see above).

## Full quickstart run on 2026-11-10 (T052)

`MMI_GATES_DATABASE=1 MMI_GATES_LIVE_STACK=1 python -m gates run` from `scripts/`, on this branch after merging `main` (features 006 to 008 included) and with `integration-plan.json` listing PRs 16, 18, 17 and 19 as integrated: contracts, isolation, integration (4 steps accounted for), e2e (3 commands), security (8 commands) and cost (1 command) all `pass`, exit 0, in 422 seconds (about 7 minutes, over the 3 minutes noted earlier because the live stack was rebuilt). The shell had the worktree's `packages/testing/src` and `packages/contracts/python` on `PYTHONPATH`. Endpoints were not checked (no `--openapi`).

## Clean full run and the per-gate time limits (SC-008, T067)

After the fixes above, on the same machine with the other `mmi` stack stopped, `MMI_GATES_DATABASE=1 MMI_GATES_LIVE_STACK=1 python -m gates run`: **2 minutes 57 seconds** in total. Five gates passed; `integration` is `not_run` only because the integration plan is still empty (T030), so the overall result is `not_run`, exit 2.

| Gate | Result | Time | Limit set in `suite_gate.TIMEOUTS` |
|---|---|---|---|
| contracts | pass | 0.2 s | 120 s |
| isolation (with the database check) | pass | 39.6 s | 600 s |
| integration | not_run | 0 s | 120 s |
| e2e (with the live stack) | pass | 83.7 s | 1200 s |
| security | pass | 27.6 s | 600 s |
| cost | pass | 1.0 s | 120 s |

The limits are about 7 to 15 times these warm-cache timings, to leave room for a cold CI runner (image pulls and builds). They are a first setting from one run on one machine; adjust them after the first run on GitHub.

## Quickstart steps

| Step | Status |
|---|---|
| 1 `validate` | exits 0 since T030: `integration-plan.json` lists PRs 16, 18, 17 and 19 (all integrated). |
| 2 contracts gate catches an undeclared change | covered by `test_contracts_gate.py` (removed property, missing entry, unmoved consumers); not repeated by hand |
| 3 isolation gate catches a cross-schema read | covered by `test_isolation_gate.py`; not repeated by hand |
| 4 full gate run | run once, see above |
| 5 integration with a failing PR | covered by `test_integrate.py` on throwaway git repos (drop, dependents, foreign path, conflict, main untouched); not run against real PRs |
| 6 audit spot check | `python -m gates validate` checks every evidence `path:line` automatically; no manual sampling done |

## SC-007: finding an interface's owner, version and consumers

Clarified on 2026-11-09: SC-007 is checked by a command and its test, not by a timed human trial. `python -m gates lookup NAME` prints the owner, version, consumers and status (exit 3 for an unknown name); `scripts/tests/gates/test_matrix.py` and `test_cli.py` cover it, and a run against the real matrix returned, for example, `procurement.order.confirmed v1 | event | owner: procurement-service | consumers: inventory-service | status: frozen`. This supersedes the manual timed check asked for in T061, which was therefore not carried out.

Re-checked on 2026-11-10 after PR 19 merged: `python -m gates lookup dashboard_indicators` answered in 0.34 s with `v2 | dto | owner: inventory-service | consumers: api-bff, web | status: frozen`. Regenerating the matrix no longer drops consumers added by hand (T090 follow-up in `test_matrix.py`).

## Endpoint check and audit test runs (2026-11-15)

- **Endpoint check:** `python -m gates run --gate contracts --openapi <gateway openapi.json>`, with the document taken from `app.openapi()` of `services/api-bff` (95 paths), passes: the matrix's endpoint entries equal the gateway's real endpoints.
- **Audit statuses backed by test runs:** the test file cited as evidence for each audit row was executed. 24 Python files pass (including `infra/tests/test_migrations_postgres.py`, 10 passed with `RUN_PG_MIGRATIONS=1` and Docker); `CommandPalette.test.tsx` passes (8); `a11y-all-routes.spec.ts` passes 11 of 12. The failing test is "reference task 3 by keyboard: edit one supplier term and save it", which also fails on `main` and does not cover the a11y routes. Each row's note records its result. Statuses were not changed. Rows `infra-bicep-deployment` and `infra-ci-deploy-workflows` stay `unverified`: the Bicep row's test checks guardrail settings, not a deployment, and no test covers the workflows.

## Manual workflow `integration-gates.yml` on GitHub (2026-11-15)

Started three times with `gh workflow run integration-gates.yml --ref claude/agent-00-integration-followups`; it had never run on GitHub before.

1. **Run 43768210506 failed:** `git worktree add ... main` crashed because the Actions checkout of another branch has `origin/main` but no local `main`; no report was written and the comment job found no artifact. Fixed in `c26b430` (base resolved from `origin/<base>`, a missing base is exit 3), with two tests.
2. **Run 43768440101 failed:** the security gate stopped on `ModuleNotFoundError: ortools` (procurement tests) because the install step did not list it. The report showed PR 16 as `gate_failed` and its dependents dropped, which is the designed behaviour. Fixed in `ce4d9ab`.
3. **Run 43769197601 passed:** `integrate` and `comment` succeeded; the report lists contracts, isolation, integration (4 steps), e2e (3 commands), security (8 commands) and cost (1 command) as `pass`, with PRs 16, 18, 17 and 19 integrated. The comment job posts nothing until `integration-plan.json` is on the default branch.

The endpoint check was not part of that workflow run (it needs `--openapi`); it was run separately, see above.

## Not verified

Updated 2026-11-15.

- The comment job of `integration-gates.yml` has not posted a comment on a PR: it posts nothing until `integration-plan.json` is on the default branch.
- `gitleaks` itself was not run locally; Super-linter's GITLEAKS check passes on the PRs.
- A test run backs an audit row only for the evidence file cited; other tests of the same feature were not run row by row.
- The `e2e` gate's live-stack journey ran in the full run of 2026-11-10, not today.
