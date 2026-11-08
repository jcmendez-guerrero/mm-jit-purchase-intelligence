# Contract: Dashboard API (BFF)

All routes are `GET`, read-only, under `/api/dashboard`, require a signed-in session and the roles shown. Payload shapes are defined in [dashboard_indicators.v2.schema.json](dashboard_indicators.v2.schema.json); the existing `dashboard_summary.v1` schema is left unchanged. Errors use the project's error codes (`request_invalid`, `downstream_unavailable`, `downstream_refused`, `forbidden`), never raw downstream text.

## Common query parameters (FilterSet)

| Parameter | Type | Rules |
|-----------|------|-------|
| desde, hasta | date (ISO) | `desde <= hasta`; span 7-730 days; default last 60 days |
| almacen | int | existing warehouse id |
| proveedor | string, max 36 | existing supplier public id |
| categoria | `A`, `B`, `C`, `critical` | |
| familia | string, 1-120 | exact synchronised family name |

The same parameters apply to every route below, including export. Unknown parameters are ignored; invalid values return `422 request_invalid`.

## Routes

| Route | Roles | Purpose |
|-------|-------|---------|
| `/overview` | viewer, buyer, approver, admin | Indicators (10 families) with freshness and state; each indicator degrades alone (`{ok:false,error}`) |
| `/charts` | same | Chart series with table rows (`demand_forecast`, `abc_xyz`, `expiry_bands`, `coverage_buckets`, `capital_by_group`, `forecast_error`, `stock_value_history`) |
| `/drilldown` | same | Contributing SKUs for one indicator or chart element |
| `/filters/options` | same | Warehouses, suppliers, categories, families, data range |
| `/freshness` | same | Per-source refresh time, origin, state |
| `/export` | buyer, approver, admin | CSV of cards, a chart table, or a drill-down |
| `/skus/{sku}` | same | SKU detail (stock, coverage, demand, forecast, supplier, expiry lots) |

Existing `/overview` and `/drilldown` behaviour stays backward compatible until the web app switches over; removed fields are announced in the PR (compatibility review, constitution Development Workflow).

### `/drilldown` extra parameters

| Parameter | Rules |
|-----------|-------|
| kind | `inventory_value`, `coverage`, `stockout_risk`, `expiry_risk`, `abc_xyz`, `trend_day`, plus `demand`, `forecast`, `capital`, `budget`, `expiry_band` |
| abc, xyz, day, band | as required by the kind |
| page, page_size | page >= 1; page_size 10-200 (default 50) |
| sort, order | one of the returned columns; `asc` or `desc` |

Response: `rows` (ContributionRow), `total`, `page`, `page_size`, `sum`. **Invariant**: `sum` equals the indicator value for the same FilterSet.

### `/export` extra parameters

| Parameter | Rules |
|-----------|-------|
| kind | `cards`, `chart` (with `chart` key), `drilldown` (with drill-down parameters) |

Response: `text/csv; charset=utf-8` with BOM, `;` separator, decimal comma, Spanish headers, a leading comment block with filters, period, freshness and generation time (UTC and local), `Content-Disposition` attachment. Refusals: `403 forbidden` (role), `413 export_too_large` (over the row cap), both audited.

## Behavioural guarantees

1. No hard-coded or placeholder value in any response; an empty source yields `state: no_data`, never zero.
2. A viewer receives no money fields (`state: hidden_by_role`).
3. Products are identified by `sku`; internal ids appear only inside the opaque `detail_ref`.
4. Data originating from a local load is labelled `origin: local_load` and is not summed with `erp_sync` data.
5. Excluded or quarantined records are counted in `incomplete_count`.
6. Timestamps are UTC ISO-8601 with the original string alongside.
7. Responses never contain free-text notes or tax identifiers.

## Downstream calls (BFF to services)

| Service | Call | Contract owner |
|---------|------|----------------|
| inventory-service | `/dashboard/*` (extended, same prefix) | inventory |
| forecast-service | `/accuracy` (extended with history) | forecast |
| procurement-service | `/summary/spend` (budget and open orders) | procurement |

Changes to the forecast and procurement endpoints are additive and raised with their owners through Agent 00 before implementation.
