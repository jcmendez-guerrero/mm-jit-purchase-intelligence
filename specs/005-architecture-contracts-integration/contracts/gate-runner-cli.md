# Gate runner CLI contract

Command: `python -m gates` (run from the repository root; package at `scripts/gates`).

| Invocation | Behaviour |
|------------|-----------|
| `python -m gates run [--gate NAME ...] [--report PATH]` | Runs the named gates (default: all six: `contracts`, `isolation`, `integration`, `e2e`, `security`, `cost`) and writes a report matching [gate-report.schema.json](gate-report.schema.json). |
| `python -m gates integrate --plan docs/architecture/integration/integration-plan.json [--report PATH]` | Builds a temporary local branch from `main`, merges each PR head in plan order, runs all gates, drops a failing PR and its transitive dependents, continues, and writes the report with `dropped_prs`. An invalid plan (unknown `depends_on`, a cycle, overlapping owners) is refused before anything is built: the message goes to stderr and the exit code is 3. A PR whose head does not exist is dropped with `failed_gate: ref`; a merge that adds nothing does not undo the previous PR. |
| `python -m gates validate` | Validates the three JSON artifacts under `docs/architecture/integration/` against the schemas in this folder, and checks that the validated schema copies equal the design copies. |
| `python -m gates summary --report PATH [--pr N]` | Prints a Markdown summary of a report to stdout (gate results, dropped PRs, run duration; for `--pr N` only that PR's rows). CI posts the output as a comment on the domain PR. |
| `python -m gates run --openapi PATH` | As `run`, and the contracts gate also checks that the matrix's `endpoint` entries equal the gateway's exported OpenAPI. |
| `python -m gates integrate --install --web` | As `integrate`, after installing `packages/contracts` and `packages/testing` from the integration tree (`--install`) and running `npm ci` and Chromium install in its `apps/web` (`--web`). |
| `python -m gates matrix [--openapi PATH]` | Regenerates `contract-matrix.json` from `packages/contracts`; endpoint entries are kept, or refreshed from the OpenAPI file. |
| `python -m gates lookup NAME` | Prints owner, version, consumers and status of every matrix entry named `NAME` (a schema name such as `money`, a versioned name `money.v1`, or an endpoint name such as `GET /api/dashboard/overview`); exits 3 when nothing matches or the matrix is missing. SC-007 is checked by its test. |
| `python -m gates matrix-md` / `audit-md` | Render `contract-matrix.json` and `feature-status.json` to Markdown. |

Environment switches: `MMI_GATES_DATABASE=1` makes the isolation gate also run the PostgreSQL role-grant test (needs Docker); `MMI_GATES_LIVE_STACK=1` makes the e2e gate start the compose stack (project `mmi-gates-live`), run the live Spanish UI journey against it and remove it afterwards.

Exit codes: `0` all requested gates pass; `1` at least one requested gate failed; `2` at least one requested gate was not run and none failed; `3` invalid input or artifact. With no `--gate`, all six gates are requested. With `--gate NAME` (repeatable) only the named gates decide the result: the report still lists all six, and the others show `not requested`.

Gates:

- `contracts`, `isolation`: required checks on every PR.
- `integration`: passes only when every step of the integration plan is `integrated`, or `dropped` with a recorded reason.
- `e2e`: includes a browser journey in the Spanish UI against the local stack of real services, plus the fast fake-backend browser suite.
- `security`: includes the guarantee-to-test map (roles, second factor, audit, UTC, decimals).
- `cost`: failures name the contributing resources.
- All six are required on the integration branch.

Guarantees:

- Never pushes, never merges into `main`, never calls the ERP or any network host. Posting the summary comment is done by the CI workflow, not by this command.
- A gate that cannot run (missing fixture, missing tool) reports `not_run`; the aggregate then cannot be `pass`.
- A PR whose diff touches paths outside its `owned_paths` (and outside Agent 00's shared paths) is dropped with reason `touches_foreign_paths`.
- Reports contain only gate names, file paths, PR numbers, durations and messages; no data values.
