# Live stack for the dashboard (feature 014)

Runs the real BFF, services and PostgreSQL locally and loads the synthetic reference dataset, so the dashboard can be checked end to end without Azure credentials and without any real data. The dataset and its expected totals are in `packages/testing/fixtures/dashboard_reference/` (`dataset.json`, `TOTALS.md`).

## Start

```bash
docker compose -f infra/compose.yaml -f infra/compose.live-stack.yaml up --build -d postgres dev-issuer inventory-service forecast-service procurement-service api-bff web
```

`infra/compose.live-stack.yaml` only publishes the database on `127.0.0.1:55432`. The inventory service creates its tables on start (migrations).

## Seed

```bash
uv run python scripts/live-stack/seed.py --database-url postgresql+psycopg://inventory_svc:dev-only-local@127.0.0.1:55432/mmi
```

The loader refuses a host that is not this machine and a database that already holds products, so the fixture never mixes with data from the ERP or from the local loader. To start again, remove the stack's volumes (`docker compose -f infra/compose.yaml -f infra/compose.live-stack.yaml down -v`) and repeat.

## Check

- Open the web app on `http://localhost:8080` and sign in with the local development issuer as a buyer, then as a viewer.
- The ten indicators show the totals in `TOTALS.md` (for example stock value 100,00 EUR and expiring value 60,00 EUR).
- Playwright against this stack (task T060): `PLAYWRIGHT_BASE_URL=http://localhost:8080 npx playwright test --config playwright.live.config.ts tests/live/dashboard.spec.ts` from `apps/web`.

## Notes

- The reference data is dated 2026-11-09. Figures that depend on the current day (freshness, age) show it as old; this is expected and is what the stale banner is for.
- Use only synthetic data here. Real exports go through the local loader (`infra/compose.local-data.yaml`), never through this script.
