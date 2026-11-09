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
| 1 `validate` | exits 3: only `integration-plan.json` is missing (T030). The audit and matrix pass. |
| 2 contracts gate catches an undeclared change | covered by `test_contracts_gate.py` (removed property, missing entry, unmoved consumers); not repeated by hand |
| 3 isolation gate catches a cross-schema read | covered by `test_isolation_gate.py`; not repeated by hand |
| 4 full gate run | run once, see above |
| 5 integration with a failing PR | covered by `test_integrate.py` on throwaway git repos (drop, dependents, foreign path, conflict, main untouched); not run against real PRs |
| 6 audit spot check | `python -m gates validate` checks every evidence `path:line` automatically; no manual sampling done |

## SC-007: finding an interface's owner, version and consumers

Clarified on 2026-11-09: SC-007 is checked by a command and its test, not by a timed human trial. `python -m gates lookup NAME` prints the owner, version, consumers and status (exit 3 for an unknown name); `scripts/tests/gates/test_matrix.py` and `test_cli.py` cover it, and a run against the real matrix returned, for example, `procurement.order.confirmed v1 | event | owner: procurement-service | consumers: inventory-service | status: frozen`. This supersedes the manual timed check asked for in T061, which was therefore not carried out.

## Not verified

- The two new workflows (`gates` job in `ci.yml`, `integration-gates.yml`) parse as YAML but have never run on GitHub.
- The real-services Spanish UI journey (T035) and its screenshots (T045) do not exist.
- The audit statuses did not execute any test suite; the e2e failure above is the only suite result that contradicts an audited "complete" and may be environmental.
- `gitleaks` was not installed locally; only the repo's export-signature guard and a pattern scan of the new files were run.
