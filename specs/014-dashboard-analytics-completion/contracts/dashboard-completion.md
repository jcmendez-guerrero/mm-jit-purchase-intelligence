# Contract: Dashboard API completion (BFF)

Additive to `specs/006-executive-dashboard-analytics/contracts/dashboard-api.md`, which stays the contract of record for the common filter parameters, existing routes and behavioural guarantees. The JSON Schemas themselves live in `packages/contracts/dto` and are added first, through Agent 00; `v2` indicators are not changed.

All routes: GET only (export included), session cookie, es-ES error messages, stable error codes, no raw downstream text. The BFF validates request shape and forwards; it does no money arithmetic (no sums or percentages).

## Routes added or completed

| Route | Roles | Purpose | Errors |
|-------|-------|---------|--------|
| `GET /dashboard/charts` | viewer, buyer, approver, admin | Chart series with table rows for the requested chart keys and filter set | `400 invalid_filter`, `502 downstream_unavailable` (per chart where possible) |
| `GET /dashboard/skus/{sku}` | same | SKU detail; cost fields only for cost roles | `404 sku_not_found`, `400 invalid_sku` |
| `GET /dashboard/freshness` | same | Per-source freshness, origin, state, excluded count | `502` per source degrades alone |
| `GET /dashboard/export` | buyer, approver, admin | CSV (and XLSX where supported) of cards, a chart table or a drill-down | `403 role_not_allowed` (audited), `413 export_too_large`, `400 format_unsupported` |
| `GET /dashboard/drilldown` | same | New `kind` values: `demand`, `forecast`, `capital`, `budget`, `expiry_band` | `400 invalid_kind` |
| `GET /dashboard/filters/options` | same | Options from current data and the available date range | none new |

## Rules

- Invalid filter values are refused by the server (422 `request_invalid`); the web app drops them from the address and shows a Spanish notice.
- Viewer responses never contain `cost`, `capital` or `budget` money fields, in any route; absence is asserted in tests, not only hiding in the UI.
- Export: header block first (filters, period, freshness, generation time), semicolon separator, decimal comma, UTF-8 with BOM; text cells starting with `=`, `+`, `-`, `@`, tab or carriage return are prefixed so they stay text; no notes, tax ids or internal ids; rows and totals equal the screen for the same parameters.
- Export is idempotent and side-effect free apart from its audit entry (one per request, allowed or refused).
- Chart `state` is `ok`, `no_data` or `error` (the frozen v2 `ChartSeries`); `no_data` carries `summary_params.reason` (for example `insufficient_history`), never an empty zero-filled series. The charts route returns v2 `ChartSeries` objects, so no new chart schema is added.
- Freshness `state` is `ok`, `no_data`, `stale` or `error` (the vocabulary of the indicator freshness block); `no_data` and `error` never render as zero.
- Local-load figures carry `origin: local_load` and are never summed with `erp_sync` figures.

## Downstream calls

| Service | Call | Owner |
|---------|------|-------|
| inventory-service | `/dashboard/charts`, `/dashboard/skus/{sku}`, `/dashboard/freshness`, `/dashboard/export`, extended `/dashboard/drilldown` | inventory-service |
| forecast-service | `/accuracy` with `history` (already approved in 006) | forecast-service |
| procurement-service | `/summary/spend` with date range (already approved in 006) | procurement-service |

No call to the ERP connector or cost writer exists from these routes.

## Contract tests

Schema validation of each new payload; `v1` and `v2` indicator schemas unchanged; viewer absence of cost fields; GET-only test across all dashboard routes; export audit entries for allowed and refused attempts.
