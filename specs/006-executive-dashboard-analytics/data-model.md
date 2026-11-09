# Data Model: Executive Dashboard & Analytics

All entities are read models inside inventory-service (schema owned by that service) unless stated. No cross-schema SQL. Money is `Decimal` (stored as numeric, serialised as a string with two decimals). Timestamps are stored UTC together with the original string.

## FilterSet (request value, not stored)

| Field | Type | Rules |
|-------|------|-------|
| date_from, date_to | date | `date_from <= date_to`; span 7-730 days; default last 60 days; future end clipped with a notice |
| warehouse_id | int, optional | must exist in the synced warehouses |
| supplier_id | string (public id), optional | the supplier of the lot cost that values the stock; an unknown id gives empty figures |
| category | enum A, B, C, critical, optional | |
| family | string 1-120, optional | exact synchronised ERP family name |

Invalid values are refused with `request_invalid`; they are never coerced silently.

## Indicator (response value)

| Field | Type | Notes |
|-------|------|-------|
| key | enum | stock_value, coverage_days, demand, forecast, stockout_risk, expiry_exposure, capital_tied_up, purchasing_budget, wape, bias |
| value | string or null | Decimal or integer as string; null with state `no_data` |
| unit | enum | EUR, days, units, count, percent |
| period | object | from, to |
| state | enum | ok, no_data, stale, error, hidden_by_role |
| basis | string key | translation key for the calculation basis |
| definition_key | string | translation key for the definition |
| freshness | DataFreshness | |
| incomplete_count | int | records excluded or estimated, linked to the review list |
| parts | list of Part | optional breakdown that explains the value: for capital tied up `stock_at_cost` and `open_orders`; for the purchasing budget one part per cap used with its period, and `spend` |
| filters_unsupported | list of strings | filters this indicator cannot honour, stated in text |

## Part (inside an Indicator)

| Field | Type | Notes |
|-------|------|-------|
| key | string | e.g. `stock_at_cost`, `open_orders`, `cap_week`, `cap_month`, `spend` |
| label_key | string | translation key |
| value | string or null | Decimal as string; the parts of capital add up to the indicator value |
| period | object, optional | `from` and `to` of the weeks or months the part covers |

## DataFreshness

| Field | Type | Notes |
|-------|------|-------|
| source | enum | inventory_snapshot, movements, forecast, accuracy, budget_spend |
| refreshed_at | datetime UTC | plus `refreshed_at_original` string |
| origin | enum | erp_sync, local_load, forecast, proposal |
| state | enum | ok, no_data, stale, error |
| stale_after_hours | int | from server configuration |

Rule: an indicator whose inputs mix `erp_sync` and `local_load` is not produced; the two are returned as separate labelled values.

## DailyKpis extension (stored, existing table)

No new tables. The existing `agg_daily_kpis` table (one row per day, warehouse and category, written by the aggregate refresh) gains four columns in migration 0007:

| Field | Type | Notes |
|-------|------|-------|
| capital_tied_up | numeric, nullable | stock value plus confirmed unreceived orders (definition pending, T003) |
| demand_units | integer, nullable | real ERP sales in the day |
| forecast_units | numeric, nullable | forecast for the next 28 days |
| origin | string, default `erp_sync` | `local_load` for data from the local loader |

Existing rows keep NULL and `erp_sync`. Retention: 25 months, removed by the refresh job. The supplier filter needs no stored link: it reads `lot_cost_projection` (variant, supplier, lot, unit cost).

## ContributionRow (response value)

| Field | Type | Notes |
|-------|------|-------|
| variant_id | integer | internal id, sent only so the screen can open the product detail; never displayed |
| sku | string or null | shown first |
| name | string or null | shown second |
| figure | string or null | Decimal string; null for kinds without a figure |

Page envelope (`DrillPage`): `kind`, `rows`, `total`, `truncated`, `offset`, `sum`, where `sum` covers every row and equals the indicator value for the same FilterSet (asserted in tests).

## SkuDetail

Existing product detail extended with expiry lots (quantity, expiry date, acquisition cost only for cost-allowed roles).

## ChartSeries (response value)

| Field | Type |
|-------|------|
| key | demand_forecast, abc_xyz, expiry_bands, coverage_buckets, capital_by_group, forecast_error, stock_value_history |
| title_key, summary_params | translation key and parameters for the text summary |
| columns, rows | the table view; the chart is drawn from the same rows |
| range_available | from, to (for history charts) |
| state | ok, no_data, error |

## ExportRecord (stored in the BFF audit chain)

| Field | Type |
|-------|------|
| actor, role | string |
| export_kind | cards, chart_table, drilldown |
| filters | FilterSet snapshot |
| row_count | int |
| outcome | ok, refused_role, refused_cap, error |
| at | datetime UTC |

No file content is stored.

## State and validation notes

- Indicator state: `ok` -> `stale` when `refreshed_at` older than threshold; `ok` -> `no_data` when the source has no rows; `error` when the source call fails (card degrades alone); `hidden_by_role` when the role may not see money.
- Quarantined or ambiguous source records are counted in `incomplete_count` and are never summed into `value`.
- Division by zero in coverage yields state `ok` with value null and basis `no_demand`, never infinity.
