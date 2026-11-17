# Contract: Dashboard API completion (BFF)

Additive to `specs/006-executive-dashboard-analytics/contracts/dashboard-api.md`, which stays the contract of record for the common filter parameters, existing routes and behavioural guarantees. The JSON Schemas themselves live in `packages/contracts/dto` (`dashboard_sku.v1`, `dashboard_drilldown.v1`, `dashboard_freshness.v1`, `dashboard_charts.v1`); the frozen `dashboard_indicators.v2` and `dashboard_summary.v1` are not changed. Gateway endpoints are listed in `docs/architecture/integration/contract-matrix.json` (status `draft`, pending Agent 00).

All routes: GET only (export included), session cookie, es-ES error messages, stable error codes, no raw downstream text. The gateway validates request shape and forwards; it does no money arithmetic (no sums or percentages). A downstream refusal keeps its status and stable code; an unreachable service is 502 `downstream_unavailable`.

## Routes added or completed

| Route | Roles | Purpose | Errors |
|-------|-------|---------|--------|
| `GET /api/dashboard/charts` | viewer, buyer, approver, admin | The chart tables for `keys` (comma list; all when absent) and the filter set, as `dashboard_charts.v1` | `422 request_invalid`, `502 downstream_unavailable`; one failing chart is `state: error` on its own |
| `GET /api/dashboard/skus/{sku}` | same | SKU detail as `dashboard_sku.v1`; the `cost` object only for cost roles | `404 sku_not_found`, `422` for a malformed SKU, `502` |
| `GET /api/dashboard/freshness` | same | `dashboard_freshness.v1`: per-source freshness and origin, malformed records held for review, local-load products left out, review-list path | `502 downstream_unavailable` |
| `GET /api/dashboard/export` | buyer, approver, admin | CSV of `kind` = `cards`, `chart` (with `chart`) or `drilldown` (with `drill_kind` and its parameters); optional `loaded_at` | `403 auth_forbidden_role` (audited by the role check), `413 export_too_large` (audited), `400 format_unsupported` (audited), `422 request_invalid` |
| `GET /api/dashboard/drilldown` | same | New `kind` values `demand`, `forecast`, `capital`, `expiry_band` (`band`: `expired`, `d0_30`, `d31_60`; `demand` takes `date_from` and `date_to`); `dashboard_drilldown.v1` | `422 request_invalid`, `422 no_forecast`, `422 company_wide_only` (forecast with a warehouse) |
| `GET /api/dashboard/filters/options` | same | Options from current data | none new |

`budget` (drill-down), the `forecast_error` chart and XLSX are not served (see the closure report).

## Rules

- Invalid filter values are refused by the server (422 `request_invalid`). The web app drops them, and well-formed values that are not among the current options, from the address and shows a Spanish notice.
- Viewer responses never contain `cost`, `capital` or `budget` money fields, in any route; absence is asserted in tests, not only hiding in the UI. A viewer's export is refused.
- Export: header block first (report, filters, period, freshness, generation time in UTC and Madrid), then notes (`Fuera de este archivo`, and `Aviso` when `loaded_at` is older than the latest refresh), a blank line, the column header, the rows and a total row where the screen has one; semicolon separator, decimal comma, UTF-8 with BOM; text cells starting with `=`, `+`, `-`, `@`, tab or carriage return are prefixed so they stay text; no notes, tax ids or internal ids; rows and totals equal the screen for the same parameters; above 5,000 rows it is refused, never cut.
- The cards export holds the six indicators inventory computes, plus capital tied up when the gateway passes `open_orders`; budget, WAPE and bias are named in the header as outside the file.
- Export is idempotent and side-effect free apart from its audit entry (`dashboard.exported` or `dashboard.export.refused`: who, view, filters, row count or reason; never row content).
- Chart `state` is `ok`, `no_data` or `error` (the frozen v2 `ChartSeries`); `no_data` carries `summary_params.reason` (for example `range_outside_history`, `filter_not_stored`, `hidden_by_role`), never an empty zero-filled series.
- Freshness `state` is `ok`, `no_data`, `stale` or `error` (the vocabulary of the indicator freshness block); `no_data` and `error` never render as zero.
- Local-load figures (surrogate ids from 9,000,000) are never added to ERP figures: with both kinds present the figures are the ERP ones and `local_load_excluded` counts the rest; with only local data the origin is `local_load`.
- The dashboard's "today" is the Madrid business date.
- The drill-down rows still carry `variant_id` for the existing product overlay; removing it is a v2 change (open task).

## Downstream calls

| Service | Call | Owner |
|---------|------|-------|
| inventory-service | `/dashboard/charts`, `/dashboard/skus/{sku}`, `/dashboard/freshness`, `/dashboard/export`, extended `/dashboard/drilldown` | inventory-service |
| forecast-service | `/accuracy` with `history` (already approved in 006) | forecast-service |
| procurement-service | `/summary/spend` with date range (already approved in 006); the export also reads `open_orders` from it | procurement-service |

No call to the ERP connector or cost writer exists from these routes.

## Contract tests

Schema validation of each new payload and of the real responses of the inventory service (buyer and viewer); `v1` and `v2` schemas unchanged (hash-pinned); viewer absence of cost fields; GET-only test across all dashboard routes in both services; export audit entries for allowed and refused attempts; the matrix test for the gateway endpoints.
