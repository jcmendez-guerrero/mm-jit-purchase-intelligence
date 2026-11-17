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

Invalid values are ignored with a notice entry `ignored_filters: [{name, reason}]` in the response, shown by the UI. The same set is encoded in the page address.

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

Request: `kind` (`cards`, `chart`, `drilldown`), `format` (`csv`, `xlsx` where supported), the filter set, kind parameters. File: header block (filters, period, freshness, generation time UTC and Madrid), rows identical to the screen, no notes, tax ids or internal ids. Refusal reasons: `role_not_allowed`, `export_too_large`, `format_unsupported`. Each attempt writes an audit entry: actor, kind, filters, outcome, time; no row content.

## FreshnessStatus

Per source: `source`, `origin` (`erp_sync`, `local_load`), `refreshed_at_utc`, `refreshed_at_original`, `state` (`ok`, `no_data`, `stale`, `error`), `stale_after`. Plus `excluded_records` (count) and `review_list_link`.

## ClosureReport (document)

`specs/014-dashboard-analytics-completion/closure-report.md`. One row per unchecked 006 task or requirement: id, status at start (completed, remaining, unverified), file evidence, final status (delivered and tested, or deferred), reason, owner, follow-up. A second table holds the evidence results (live journey, performance numbers, axe, quickstart, six gates, cost note).

## State transitions

Closure row: `unverified` -> `completed` (found done) or `remaining` -> `delivered` or `deferred (with reason, owner, follow-up)`. No other state is allowed at close.
