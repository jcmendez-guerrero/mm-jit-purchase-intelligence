# Audit inventory (main at `9d11abb`)

Facts gathered by inspecting the repository for the feature status audit ([feature-status.md](feature-status.md)). Counts are file counts, not coverage figures.

## Limits of this audit

- **No test suite was executed.** "complete" means: all tasks for the feature are marked done in its spec, code exists, and a test file exists. A broken suite would not be seen here; the end-to-end, security and cost gates (tasks T034 to T039) are what run the suites.
- Statuses come from `specs/00[1-4]-*/tasks.md` open tasks per user story; manual quickstart walks recorded as open tasks make a story `partial`.
- Evidence lines point at the first definition in each file, not at every relevant line.
- **Scope:** 31 features. 23 come from the user stories of specs 001 to 004. 8 are infrastructure and tooling that no user story covers (ids starting `infra-`): the Siweb mock, the dev issuer, the synthetic generator, the compose stack, web hardening, database migrations, the Bicep deployment and the CI and deploy workflows. Anything not in either group (for example individual scripts under `scripts/`) is not classified.

## Services and schema ownership

| Service | Database schema | Python source files | Test files |
|---|---|---|---|
| `services/siweb-connector` | `integration` | 26 | 15 |
| `services/inventory-service` | `inventory` | 38 | 31 |
| `services/forecast-service` | `forecasting` | 36 | 28 |
| `services/procurement-service` | `procurement` | 75 | 64 |
| `services/siweb-cost-writer` | `costwrite` | 11 | 5 |
| `services/api-bff` (gateway) | `bff` | 29 | 25 |

Source: `infra/postgres/init.sql` (one schema and one role per service). The isolation gate finds no cross-schema reference in these services.

## Shared contracts

`packages/contracts`: 27 DTO schemas, 14 event schemas, the error-code list and a `baseline/` snapshot; 42 entries in [contract-matrix.json](contract-matrix.json). Contract tests: 8 files in `packages/contracts/tests`.

## Endpoints

The gateway (`services/api-bff/src/routes`) declares 97 route handlers across the files `admin_roles`, `admin_status`, `api`, `costs`, `dashboard`, `imports`, `local_load`, `policies`, `rbac`, `scenarios`, `suppliers`. They are not yet listed one by one in the matrix (entries of kind `endpoint` are added by task T049).

## Frontend

`apps/web`: features `admin`, `costs`, `dashboard`, `imports`, `localload`, `policies`, `proposals`, `quality`, `scenarios`, `suppliers`; 31 unit test files and 28 end-to-end files (fake backends).

## CI

`.github/workflows/ci.yml` jobs: linting, changes, secrets, python, web, bicep, security-scans, compose-smoke, emulators. `.github/workflows/deploy.yml` jobs: gate, build, deploy. Cross-service tests live in `infra/tests` (16 files).

## Merged pull requests (`git log --merges`)

PR 1 (specs 001), PR 12 (feature 002 console), PR 13 (Azure deployment), PR 14 (feature 003 frontend), PR 15 (feature 004), and dependabot PRs 2, 3 and 5 (workflow action updates).

## Open work recorded in earlier specs

Spec 001: 7 open tasks; spec 002: 1; spec 003: 2; spec 004: 25 (local-only guards, runbook, supplier note block, conditions sync). These drive the two `partial` features in the audit (004 US2 and 004 US4).
