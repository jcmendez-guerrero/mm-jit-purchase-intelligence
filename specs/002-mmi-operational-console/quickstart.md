# Quickstart: validating MMI 002

Synthetic data only; no Azure credentials or real Siweb host. Commands follow the repository conventions from 001 (see `specs/001-mmi-purchase-intelligence/quickstart.md`). Scenarios become runnable as their phase lands; until then they are the acceptance walkthrough.

## Prerequisites

- Docker with about 1.5 GiB free (local VM of 1.9 GiB is tight; see 001 findings).
- Repository virtual environment; Node for `apps/web`.

## Setup

```bash
docker compose -f infra/compose.yaml up --build
```

```bash
docker compose run --rm siweb-connector python -m job all
```

This loads the synthetic ERP mock and runs the existing pipeline.

## Validation scenarios

1. **Durable roles and approval (US1, SC-007)**: sign in as an admin (dev login, local only), assign buyer and approver roles to two synthetic users, restart `api-bff`, confirm the roles remain and procurement lists both approvers; create, submit and approve a proposal with a different user and fresh second factor; confirm self-approval and a stale second factor are refused.
2. **Supplier terms (US3, SC-001)**: open Proveedores, edit a synthetic supplier's lead time, MOQ, shipping, discounts and one product override; reload and see persistence and history; generate a proposal and see the terms cited; confirm no request reached the ERP mock other than the existing cost PUT path.
3. **Policies (US4)**: change a segment service level and a budget cap, check the preview, set a future effective date, produce a proposal before and after; check the audit entry and that a stale concurrent edit gets a conflict.
4. **Seed import (US5, SC-002/005)**: download the Spanish template; upload the synthetic valid CSV and XLSX from `packages/testing`; map, preview, validate; check that invalid rows are quarantined with Spanish reasons; view the dry-run; activate; see a forecast run referencing the dataset; roll back; confirm ERP movements are unchanged. Upload the hostile fixtures (macro workbook, wrong signature, oversized, formula cells) and confirm refusal or neutralisation.
5. **Dashboard (US2, SC-003/004)**: open the dashboard; check KPI values against the reference totals, filters from live options, drill-down to a variant, loading/empty/error/stale states, and the table alternative of each chart.
6. **Scenarios (US6, SC-008)**: create scenarios changing MOQ, lead time, shipping, pack multiple and budget; confirm allocations change with stated reasons; promote one and approve it; export CSV/XLSX and open it safely.
7. **Cost update and margin (US3, SC-012)**: receive a synthetic order with lots at different costs, check the median and the lots behind it, a margin below 15% blocked, an admin override with tips and reason, and that the ERP mock receives only the allowed PUT.
8. **Admin and cost (US7, SC-011)**: view sync/import/model status, rerun a failed import idempotently, run the cost-guardrail test.

## Automated suites

```bash
pytest services/<service>
```

```bash
RUN_PG_MIGRATIONS=1 pytest infra/tests/test_migrations_postgres.py
```

```bash
RUN_E2E=1 pytest infra/tests/test_pipeline_e2e.py
```

```bash
npm --prefix apps/web run test
```

```bash
npm --prefix apps/web run e2e
```

Expected: contract, integration, migration (up and down), Spanish end-to-end with axe, security abuse, localisation and cost-guardrail suites all green. Playwright captures screenshots of the Spanish screens as review evidence.

## References

Contracts: [contracts/](contracts/). Data model: [data-model.md](data-model.md). Decisions: [research.md](research.md) and `docs/adr/018`–`020`.
