# Data Model: Dashboard & Analytics Completion

Additions and clarifications on top of `specs/006-executive-dashboard-analytics/data-model.md`. No new tables are planned; entities below are response shapes and one report document, unless the verification task finds a missing column of `agg_daily_kpis` (then an additive Alembic migration in inventory-service, no cross-schema SQL).

## DashboardFilterSet (existing, confirmed)

| Field | Rules |
|-------|-------|
| date_from, date_to | ISO dates; `date_from <= date_to`; span 7-730 days; default last 60 days |
| warehouse_id | integer >= 0 |
| supplier_id | public supplier id, `[A-Za-z0-9_-]{1,36}` |
| category | `A`, `B`, `C`, `critical` |
| family | exact family name, 1-120 characters |

An invalid value (wrong format) is refused by the server with 422 `request_invalid`. The web app never sends one: it drops a badly formed value, and also a well-formed one that is not among the current options (a supplier, category, family or warehouse that no longer exists), from the address and shows a Spanish notice; nothing is guessed. The same set is encoded in the page address.

## DrillDownKind (extended)

Existing: `inventory_value`, `coverage`, `stockout_risk`, `expiry_risk`, `abc_xyz`, `trend_day`. Added: `demand`, `forecast`, `capital`, `budget`, `expiry_band`.

Row: `sku`, `name`, `figure` (Decimal as string), optional `cost` fields (cost roles only). Total equals the card or chart figure. Order: figure descending by default, ties by SKU ascending; offset paging; sorting spans the whole list.

## SkuDetail

| Field | Notes |
|-------|-------|
| sku, name | no internal id |
| stock, coverage_days, demand, forecast | with period and origin |
| supplier | public id and display name only |
| expiry_lots | lot code, quantity, expiry date, band |
| cost fields | present only for cost-allowed roles |
| state | `ok`, `no_demand_history`, `negative_stock`, `cost_estimated` explanations |

## ChartSeries

| Field | Notes |
|-------|-------|
| key | the frozen v2 `ChartSeries` keys: `demand_forecast`, `abc_xyz`, `expiry_bands`, `coverage_buckets`, `capital_by_group`, `forecast_error`, `stock_value_history` (no parallel vocabulary) |
| title, summary | Spanish text from the catalogue (keys, not literals) |
| points / rows | the same rows feed the chart and the table |
| history_range | earliest and latest day available |
| state | `ok`, `no_data`, `error` (v2); why a chart has no data is carried in `summary_params.reason`, for example `insufficient_history` |

## ExportRequest and ExportFile

Request: `kind` (`cards`, `chart`, `drilldown`), `format` (`csv` only; `xlsx` is refused with `format_unsupported`), the filter set, kind parameters, and two optional values the screen or the gateway adds: `loaded_at` (when the screen loaded its data, so the header can say newer data exists) and `open_orders` (procurement's open orders, passed on by the gateway as text, so the cards file can include capital tied up). File: header block (filters, period, freshness, generation time UTC and Madrid), rows identical to the screen, no notes, tax ids or internal ids. Refusal reasons: `role_not_allowed`, `export_too_large`, `format_unsupported`. Each attempt writes an audit entry: actor, kind, filters, outcome, time; no row content.

## FreshnessStatus

Per source: `source`, `origin` (`erp_sync`, `local_load`), `refreshed_at_utc`, `refreshed_at_original`, `state` (`ok`, `no_data`, `stale`, `error`), `stale_after`. Plus `excluded_records` (malformed or ambiguous movements held for review), `local_load_excluded` (locally loaded products left out of the ERP figures) and `review_list_link`.

## ClosureReport (document)

`specs/014-dashboard-analytics-completion/closure-report.md`. One row per unchecked 006 task or requirement: id, status at start (completed, remaining, unverified), file evidence, final status (delivered and tested, or deferred), reason, owner, follow-up. A second table holds the evidence results (live journey, performance numbers, axe, quickstart, six gates, cost note).

## State transitions

Closure row: `unverified` -> `completed` (found done) or `remaining` -> `delivered` or `deferred (with reason, owner, follow-up)`. No other state is allowed at close.

## Product key at the browser (FR-008a)

| Where | Key |
|-------|-----|
| Browser, gateway routes, page addresses, gateway payloads | `sku` (text, as in the synced catalogue) |
| Service-to-service routes, events, database, cost writer, connector | `variant_id` (integer) |

Rules: a SKU is 1 to 60 characters: letters, digits, `.`, `_` and `-`, starting with a letter or a digit; no slash, no space, no accents (decided 2026-11-18, T107; the gateway refuses anything else with 422 on every route, `SKU_PATTERN` in `services/api-bff/src/routes/api.py`). The SKU is unique among the variants a service holds; if it is not, the request is refused as ambiguous and the product goes to the review list. A SKU resolves to a surrogate id (from 9,000,000) for locally loaded data; such an id never reaches a Siweb request. Drill-down rows, review notes, scenario lines, quality and admin rows carry `sku` and `name`, not `variant_id`.
