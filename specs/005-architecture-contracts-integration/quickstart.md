# Quickstart: validating Architecture, Contracts & Integration

Prerequisites: repository checked out, Python 3.12 environment with the repo's dev dependencies, Node for the web tests. Everything runs on synthetic fixtures; no Azure or ERP access.

## 1. Validate the artifacts

```bash
python -m gates validate
```

Expected: exit 0; feature status, contract matrix and integration plan match the schemas in [contracts/](contracts/).

## 2. Contract gate catches an undeclared change (User Story 2)

1. Edit a field in any `packages/contracts/dto/*.v1.schema.json` without bumping the version or the matrix.
2. Run `python -m gates run --gate contracts`.

Expected: exit 1, evidence names the schema and the baseline mismatch. Revert, add `name.v2` plus a matrix entry (v1 `deprecated`), rerun: exit 0.

## 3. Isolation gate catches a cross-schema read (User Story 2, 4)

1. Add `SELECT 1 FROM procurement.some_table` to a file under `services/inventory-service/`.
2. Run `python -m gates run --gate isolation`.

Expected: exit 1 naming the file and the foreign schema. Remove it: exit 0.

## 4. Full gate run (User Story 4)

```bash
python -m gates run --report /tmp/gate-report.json
```

Expected: all six gates `pass`, exit 0. The e2e evidence includes the real-services Spanish UI journey (compose stack, synthetic data), the fast fake-backend browser suite and the pipeline e2e. The report records each gate's duration; note the total in the PR (SC-008). Disconnect a fixture (for example rename the e2e fixture) and rerun: that gate reports `not_run`, exit 2.

Then render the PR comment: `python -m gates summary --report /tmp/gate-report.json`. Expected: Markdown listing each gate result and dropped PRs, with no data values.

## 5. Integration with a failing PR (User Story 3)

1. Use two test branches named in a throwaway plan, B depending on A, with A failing a gate.
2. Run `python -m gates integrate --plan <throwaway plan> --report /tmp/integration-report.json`.

Expected: A and B appear in `dropped_prs` (`gate_failed`, `depends_on_dropped`); other PRs are integrated; `main` and all remotes are unchanged.

## 6. Audit spot check (User Story 1)

Pick 10 rows from `docs/architecture/integration/feature-status.json`; open each `path:line` evidence entry. Every one must exist and support the stated status.
