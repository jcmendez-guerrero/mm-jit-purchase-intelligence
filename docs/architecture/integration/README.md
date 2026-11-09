# Integration artifacts (feature 005, Agent 00)

Machine-checked coordination files for the parallel MMI-1 effort. Design source: `specs/005-architecture-contracts-integration/`.

| File | Purpose |
|------|---------|
| `schemas/` | The validated copy of the four JSON schemas. The design copy lives in `specs/005-architecture-contracts-integration/contracts/`; `python -m gates validate` fails if they differ. |
| `contract-matrix.json` | Every shared interface: owner, version, consumers, status; also `schema_ownership` (service to database schema). Regenerate the skeleton with `python -m gates matrix`, then curate owners and consumers by hand. |
| `feature-status.json` | Audit of main: status and `path:line` evidence per feature. |
| `integration-plan.json` | Ordered domain PRs, owned paths, dependencies and verification gates (supplied by the maintainer). |

## Running the gates

```bash
python -m gates validate
python -m gates run --report gate-report.json
```

Run from `scripts/` (or with `scripts` on `PYTHONPATH`). `run --openapi <gateway openapi.json>` also checks that the matrix's `endpoint` entries equal the gateway's real endpoints; without it the gate says endpoints were not checked, and `services/api-bff/tests/test_gateway_matrix.py` covers them in the gateway's own CI job. `MMI_GATES_DATABASE=1` makes the isolation gate also run the PostgreSQL role-grant test (`infra/tests/test_migrations_postgres.py`, needs Docker, about a minute; the integration workflow sets it); without it the gate says role grants were not checked. A missing Docker or an all-skipped test run reports `not_run`, never `pass`. The `cost` gate runs the guardrail tests against `infra/bicep/guardrails.json` (budget EUR 120/month, scale to zero, replica and job caps, forbidden always-on resource types, storage rules): it checks the settings that bound spend and names the Bicep file and the setting on failure. It does not estimate euros; the repository holds no price data. Refresh the endpoint entries with `python -m gates matrix --openapi <openapi.json>`. Exit codes: 0 pass, 1 fail, 2 not run, 3 invalid input. All six gates are implemented. `integration` is `not_run` until `integration-plan.json` lists PRs; `e2e` is `not_run` without the browser tooling or, for the live journey, without `MMI_GATES_LIVE_STACK=1` (the gate then starts and removes its own compose project, `mmi-gates-live`, on ports 8080 and 8081, so stop any local stack that uses them first). `integrate --install --web` installs the shared packages and the browser tooling from the integration tree before the gates run.

## Finding who owns an interface

`python -m gates lookup NAME` (from `scripts/`) prints the owner, version, consumers and status of an interface, for example `python -m gates lookup procurement.order.confirmed`, `lookup supplier.v1` or `lookup 'GET /api/dashboard/overview'`. It exits 3 for an unknown name. The same data is in `contract-matrix.md`.

## Lint and type checking

`scripts/gates` and its tests are checked by `ruff` with the repository configuration (the `gates` CI job runs `ruff check scripts/gates scripts/tests/gates`). They are **outside the strict `mypy` scope**: CI installs `mypy` but does not run it on any target, and `mypy --strict scripts/gates` reports 54 errors (mostly missing type arguments and parameter annotations). Annotate the package if strict typing is ever enforced in CI.

## How contract owners were set

`python -m gates matrix` guesses an owner from which service mentions a schema, and keeps any owner, status or successor already in `contract-matrix.json`, so hand curation survives regeneration. Curated on 2026-11-09:

- **Procurement-service** owns `supplier`, `supplier_terms`, `supplier_cost`, `lot_acquisition_cost`, `cost_write`, `proposal`, `proposal_line` and `scenario`: ADR-018 says procurement owns terms, policies and scenarios, the supplier cost and lot tables live in its schema, and cost writes are requested by procurement.
- **Inventory-service** owns `dashboard_summary` (the dashboard aggregates), **forecast-service** owns `seed_validation_result` (predictive seed datasets), **siweb-cost-writer** owns `conditions_block` (the supplier-note block it writes). For these three no service source file references the schema by name (only the generated models do), so the owner follows the feature design, not code references.
- **Shared, owner `agent-00`:** `money`, `variant`, `envelope` and `error_codes` (used by every service) and `load_result` (used by the local loader tooling and the gateway).
- **Consumers are a lower bound.** They are references found in service source: the schema file or event type (`name.vN`) or the generated module (`name_vN_schema`). No service imports the generated models or names a DTO schema by version, so 34 of the 42 schema entries list no consumers even though services use the same shapes through their own models. An empty list therefore does **not** mean unused: before deprecating or retiring any version, search the code and ask the owning agents by hand. The gate's check that consumers have moved to a successor is only as good as these lists.

## Required checks (repository setting, maintainer)

Whether a check blocks merging is a GitHub repository setting, not code. Nothing in this repository configures it, so it has to be set once by a maintainer:

1. Settings, Branches (or Rulesets), protect `main`.
2. Require the status check from the `gates` job of the `ci` workflow (contracts and isolation gates plus the gate runner tests). It runs on every PR.
3. Do **not** require `integration-gates`: it is started by hand and does not run on PRs (spec FR-010, ADR-022).

Until that is set, a failing `gates` job is visible on the PR but does not stop a merge.

## Running the integration gates (maintainer)

When: after the domain PRs are open and listed in `integration-plan.json` **on `main`** (the comment job reads the plan from there), and before merging them. Re-run after an agent has fixed a dropped PR.

1. Actions, `integration-gates`, Run workflow, branch `main`. (Locally: `git fetch origin '+refs/pull/*/head:refs/pull/*/head'`, then `MMI_GATES_DATABASE=1 python -m gates integrate --report gate-report.json` from `scripts/`.)
2. The `integrate` job builds the integration tree from the PR heads, runs all six gates and uploads the `gate-report` artifact; it fails the run if any gate failed or did not run.
3. The `comment` job posts a summary on each PR listed in the plan (integrated, or dropped with the reason and failing gate).
4. Merge the PRs to `main` in the order of the plan only after the run passes. The workflow merges nothing.

## Watch-and-fix protocol for domain agents

1. After a PR is opened, watch its checks. `contracts` and `isolation` are required on every PR.
2. When the integration run (manually started workflow, ADR-022) finishes, the gate report is saved as a CI artifact and a summary is posted as a comment on your PR. A dropped PR names the reason (`gate_failed`, `depends_on_dropped`, `touches_foreign_paths`) and the failing gate.
3. Fix automatically, but only inside the paths listed as yours in `integration-plan.json`. Never merge to main, edit another agent's files or write to the ERP.
4. Push the fix to your own PR branch. The PR re-enters the next integration run and stays in only if it passes.
5. A PR that depends on a dropped PR is dropped too until its dependency passes.

## Changing a frozen interface (Agent 00 procedure)

1. Ask Agent 00 for the change; do not edit a frozen schema in a domain branch.
2. A compatible change (only added optional properties) edits the schema, refreshes `packages/contracts/baseline/` with `packages/contracts/tools/update_baseline.py`, and is recorded in the matrix.
3. A breaking change adds `name.v2.schema.json` next to `name.v1`; v1 becomes `deprecated` with `superseded_by` and stays until every consumer listed in the matrix has moved to v2.
4. `python -m gates run --gate contracts` must pass before the PR is reviewed.
