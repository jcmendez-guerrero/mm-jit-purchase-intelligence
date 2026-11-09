# Quickstart: validating seed import and governance (MMI-7)

Synthetic data only. No Azure credentials, no Siweb host.

## Prerequisites

- Local compose stack running (database, gateway, forecast service, web app) as in the repository README.
- Synthetic fixtures from `packages/testing` (T004).

## Scenarios

1. **Import and preview (US1)**: download the template, upload the synthetic SKU file, map columns if needed, validate. Expect counts, a preview, quarantined rows with reasons, and "nothing has changed yet". Automated: `services/forecast-service/tests/test_seed_sku.py`, `apps/web/tests/e2e/import.spec.ts`.
2. **Dry run and activation (US2)**: as buyer A upload and validate; as buyer B run the dry run, then activate with fresh MFA. Expect the next forecast for the covered "new" product to differ and show the dataset version; uncovered products unchanged. Check that buyer A is refused, and that an owner self-activation needs a reason.
3. **Rollback (US3)**: roll back with a reason; rerun the forecast. Expect the pre-activation result (previous dataset, or none).
4. **Governance view (US4)**: open the dataset list; check state, origin, approver, provenance mix. A mixed-origin file and an ERP-export-shaped file are refused.
5. **Large file (US5)**: submit a file above 10,000 rows; expect a background message, visible stages, a result, and no duplicate on resubmission.

## Commands

The repository has no `uv.lock` and the workspace root has no dependencies, so `uv run pytest` from the root does not work. Build a virtual environment as CI does (once):

```bash
uv venv --python 3.12
uv pip install -e packages/contracts -e packages/testing pytest pytest-asyncio hypothesis pyyaml openpyxl ruff fastapi sqlalchemy alembic "psycopg[binary]" httpx python-multipart azure-storage-blob azure-storage-queue azure-identity pydantic
(cd apps/web && npm ci)
```

Then run the checks for this feature:

```bash
(cd services/forecast-service && ../../.venv/bin/python -m pytest -q)
(cd services/api-bff && ../../.venv/bin/python -m pytest -q)
(cd services/inventory-service && ../../.venv/bin/python -m pytest -q)
.venv/bin/python -m pytest -q packages/contracts/tests infra/tests
(cd apps/web && npx vitest run tests/unit/ImportScreen.test.tsx tests/unit/imports-model.test.ts)
(cd apps/web && npx playwright test tests/e2e/import.spec.ts)
```

Last verified on 2026-11-09. Known unrelated failures: with Node 26 the web tests in `tests/unit/ui/{DataTable,ThemeToggle,forms,preferences}` fail on `localStorage.clear`.

Expected outcome: all pass; no seed value appears as an ERP movement, stock or cost. Contracts: `contracts/seed-governance.delta.md`; model: `data-model.md`.
