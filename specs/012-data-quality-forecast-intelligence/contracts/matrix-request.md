# Contract matrix request for Agent 00 (T004)

Requested additions to `docs/architecture/integration/contract-matrix.json`, all additive. Owner of each new entry is the service that produces it; status `draft` until the schemas land. Nothing here changes an existing frozen entry unless the decision below says so.

## Decision needed from Agent 00

The portfolio view (US5) needs eligibility and confidence per variant inside inventory-service. `forecast.completed` v1 is **frozen** (owner forecast-service, consumer procurement-service), so the earlier idea of adding optional fields to it needs your ruling. Options:

| Option | Description |
|---|---|
| A (recommended) | New event `forecast.eligibility.published` v1, owner forecast-service, consumer inventory-service. `forecast.completed` stays untouched. |
| B | Bump `forecast.completed` to v2 with optional per-variant eligibility and confidence; both consumers migrate. |
| C | Keep v1 and add optional fields without a bump (needs an explicit exception to the freeze). |

Until you answer, tasks T005, T044 and T060b assume option A in their event name.

## New entries

| Name | Kind | Version | Owner | Consumers | Status |
|---|---|---|---|---|---|
| `quality_summary` | dto | 1 | inventory-service | api-bff, web | draft |
| `anomaly_flag` | dto | 1 | inventory-service | api-bff, web | draft |
| `forecast_explanation` | dto | 1 | forecast-service | api-bff, web | draft |
| `product_backtest` | dto | 1 | forecast-service | api-bff, web | draft |
| `portfolio_summary` | dto | 1 | inventory-service | api-bff, web | draft |
| `forecast.eligibility.published` (option A) | event | 1 | forecast-service | inventory-service | draft |
| `GET /api/quality/products/{sku}` | endpoint | 1 | agent-02 | web | draft |
| `GET /api/quality/products/{sku}/anomalies` | endpoint | 1 | agent-02 | web | draft |
| `PUT /api/quality/products/{sku}/anomalies/{day}` | endpoint | 1 | agent-02 | web | draft |
| `POST /api/quality/recompute` | endpoint | 1 | agent-02 | web | draft |
| `GET /api/quality/portfolio` | endpoint | 1 | agent-02 | web | draft |
| `GET /api/quality/portfolio/products` | endpoint | 1 | agent-02 | web | draft |
| `GET /api/forecast/products/{sku}/explanation` | endpoint | 1 | agent-02 | web | draft |
| `GET /api/forecast/products/{sku}/backtest` | endpoint | 1 | agent-02 | web | draft |
| `POST /api/forecast/backtests` | endpoint | 1 | agent-02 | web | draft |

Endpoint paths use the gateway's `/api` prefix, as the existing matrix does; the service-level paths in `quality-intelligence.md` omit it.

## Error keys to register

`quality_product_not_found`, `quality_anomaly_not_found`, `quality_decision_invalid`, `forecast_explanation_not_available`, `forecast_backtest_conflict`, `quality_job_failed` (Spanish messages in the shared catalogue).

## Schema ownership

No new database schema: inventory-service and forecast-service keep their own. No cross-schema SQL.

## Baseline gate result (run 2026-11-15 before any schema change)

`contracts` pass, `isolation` pass, `cost` pass, `integration` not run (no PRs in the plan), `e2e` not run (Playwright not installed in the verification environment), `security` failed on a missing `ortools` module in that environment, unrelated to this feature.
