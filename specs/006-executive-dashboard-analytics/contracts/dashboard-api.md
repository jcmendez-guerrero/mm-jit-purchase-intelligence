# Contract: Dashboard API (BFF)

All routes are `GET`, read-only, under `/api/dashboard`, require a signed-in session and the roles shown. Payload shapes are defined in [dashboard_indicators.v2.schema.json](../../../packages/contracts/dto/dashboard_indicators.v2.schema.json); the existing `dashboard_summary.v1` schema is left unchanged. Errors use the project's error codes (`request_invalid`, `downstream_unavailable`, `downstream_refused`, `forbidden`), never raw downstream text.

## Common query parameters (FilterSet)

The API keeps the English parameter names the dashboard already uses; the page address uses the Spanish names (`almacen`, `proveedor`, `categoria`, `familia`, `desde`, `hasta`) and the web app maps between them.

| Parameter | Type | Rules |
|-----------|------|-------|
| date_from, date_to | date (ISO) | `date_from <= date_to`; span 7-730 days; default last 60 days. Forwarded to the indicators and the spend; the trend and the other cards still use `days` until T031/T033 |
| warehouse_id | int >= 0 | existing warehouse id |
| supplier_id | string, `[A-Za-z0-9_-]{1,36}` | supplier public id. Applied to the stock figures (supplier of the lot cost), the spend and the open orders; WAPE and bias are company-wide and name it in `filters_unsupported` |
| category | `A`, `B`, `C`, `critical` | |
| family | string, 1-120 | exact synchronised family name |
| days | int 7-365 | existing trend window |

The inventory service already validates and applies `supplier_id` (`FilterSet`, supplier scope over lot costs). Invalid values return `422 request_invalid`; unknown parameters are ignored.

## Routes

| Route | Roles | Purpose |
|-------|-------|---------|
| `/overview` | viewer, buyer, approver, admin | The existing cards (`summary`, `spend`, `accuracy`, ...; each degrades alone as `{ok:false,error}`) plus `indicators`: the ten indicators in the v2 shape and fixed order (stock value, coverage, demand, forecast, stockout risk, expiry exposure, capital tied up, purchasing budget, WAPE, bias), each with value, unit, state, basis, definition key and freshness. The window is the last `days` days up to today until the date range is wired (T033) |
| `/charts` | same | Chart series with table rows (`demand_forecast`, `abc_xyz`, `expiry_bands`, `coverage_buckets`, `capital_by_group`, `forecast_error`, `stock_value_history`) |
| `/drilldown` | same | Contributing SKUs for one indicator or chart element |
| `/filters/options` | same | Warehouses, suppliers, categories, families, data range |
| `/freshness` | same | Per-source refresh time, origin, state |
| `/export` | buyer, approver, admin | CSV of cards, a chart table, or a drill-down |
| `/skus/{sku}` | same | SKU detail (stock, coverage, demand, forecast, supplier, expiry lots) |

Existing `/overview` and `/drilldown` behaviour stays backward compatible until the web app switches over; removed fields are announced in the PR (compatibility review, constitution Development Workflow).

### `/drilldown` extra parameters

The stock, coverage, risk and expiry lists describe the current state, so the date range does not narrow them; the page response is the frozen `DrillPage` and carries no `filters_unsupported`, so the web names that limit next to the list (T034). Warehouse, category, family and supplier do apply.

| Parameter | Rules |
|-----------|-------|
| kind | `inventory_value`, `coverage`, `stockout_risk`, `expiry_risk`, `abc_xyz`, `trend_day`, plus `demand`, `forecast`, `capital`, `budget`, `expiry_band` |
| abc, xyz, day, band | as required by the kind |
| limit, offset | limit 1-200 (default 50); offset >= 0 |
| sort, order | sort `sku`, `name` or `figure`; order `asc` (default) or `desc`; `order` without `sort` is refused. Sorting covers the whole list, ties fall back to SKU ascending |

Response (`DrillPage` in the v2 schema, checked by `services/inventory-service/tests/test_dashboard_drill_contract.py`): `kind`, `rows` (ContributionRow: `variant_id` only to open the detail and never shown, `sku`, `name`, `figure`), `total`, `truncated`, `offset`, `sum` (null for kinds without a total). **Invariant**: `sum` equals the indicator value for the same FilterSet.

### `/export` extra parameters

| Parameter | Rules |
|-----------|-------|
| kind | `cards`, `chart` (with `chart` key), `drilldown` (with drill-down parameters) |

Response: `text/csv; charset=utf-8` with BOM, `;` separator, decimal comma, Spanish headers, a leading comment block with filters, period, freshness and generation time (UTC and local), `Content-Disposition` attachment. Refusals: `403 forbidden` (role), `413 export_too_large` (over the row cap), both audited.

## Behavioural guarantees

1. No hard-coded or placeholder value in any response; an empty source yields `state: no_data`, never zero.
2. A viewer receives no money fields (`state: hidden_by_role`).
3. Products are identified by `sku`. The internal id travels as `variant_id` in each drill-down row only so the screen can open the product detail; it is never displayed. T040 and T042 replace it with a lookup by SKU.
4. Data originating from a local load is labelled `origin: local_load` and is not summed with `erp_sync` data.
5. Excluded or quarantined records are counted in `incomplete_count`.
6. Timestamps are UTC ISO-8601 with the original string alongside.
7. Responses never contain free-text notes or tax identifiers.

## Downstream calls (BFF to services)

| Service | Call | Contract owner |
|---------|------|----------------|
| inventory-service | `/dashboard/*` (extended, same prefix); `GET /dashboard/indicators` returns the seven indicators inventory owns (stock value, coverage, demand, forecast, stockout risk, expiry exposure, capital tied up) with `date_from`, `date_to`, the filters and an optional `open_orders` amount (`^\d{1,12}(\.\d{1,2})?$`, passed through by the gateway from procurement) that the capital total adds to the stock at cost; money indicators are `hidden_by_role` for roles without cost access, and capital is `error` with no value when `open_orders` is missing | inventory |
| forecast-service | `/accuracy` (additive: `?history=N`, 0 to 52, adds `history`, the overall WAPE and bias of each scored run newest first; every response also carries `percent`, the same WAPE and bias times 100 per group, so the gateway does no arithmetic; approved by the owner 2026-11-09) | forecast |
| procurement-service | `/summary/spend` (additive: `date_from` and `date_to` together, at most 366 days, add `range` with the cap in force on each ISO week's Monday, the spend of that week's newest live proposal, their sums; always adds `open_orders`, the confirmed orders not yet received at confirmed cost; approved by the owner 2026-11-09) | procurement |

Both changes are additive (no existing field removed or changed), each needs its own tests in the owning service, and Agent 00 is informed (audit file, T075).
