"""T128: dashboard routes for the buyer console. Read-only; filters come from live data."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from dashboard.drilldown import KINDS, DrillError, drilldown
from dashboard.export import ExportRequestInvalid, ExportTooLarge, build_export, to_csv
from dashboard.filters import FilterError, FilterSet
from dashboard.freshness import freshness_payload
from dashboard.indicators import build_indicators
from dashboard.kpis import (
    Filters,
    abc_xyz_distribution,
    business_today,
    compute_summary,
    demand_trend,
    filter_options,
    forecast_series,
    log,
)
from dashboard.roles import can_see_money, hide_cell_values, hide_money, hide_money_page
from dashboard.series import BUILDERS, CHART_KEYS, build_charts
from dashboard.sku import SkuNotFound, sku_detail
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, Query, Response
from sqlalchemy.engine import Connection


def build_dashboard_router(app: FastAPI, conn_dep: Callable[..., Connection]) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter(prefix="/dashboard")

    def filters(warehouse_id: int | None, category: str | None, family: str | None = None, supplier_id: str | None = None) -> Filters:
        try:
            return FilterSet.parse(business_today(), warehouse_id=warehouse_id, category=category, family=family, supplier_id=supplier_id).to_filters()
        except FilterError as exc:
            raise HTTPException(422, "request_invalid") from exc

    def means() -> Any:
        return getattr(app.state, "forecast_means", None)

    @router.get("/filters/options")
    def options(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        return filter_options(conn)

    @router.get("/summary")
    def summary(warehouse_id: int | None = None, category: str | None = None, family: str | None = None, supplier_id: str | None = None, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        f = filters(warehouse_id, category, family, supplier_id)
        today = business_today()
        try:
            s = compute_summary(conn, today, f, means())
            forecast_ok = True
        except Exception:
            s, forecast_ok = compute_summary(conn, today, f, None), False
        return hide_money({**s.as_json(), "forecast_available": forecast_ok and means() is not None}, _p.roles)

    @router.get("/indicators")
    def indicators(date_from: date | None = None, date_to: date | None = None, warehouse_id: int | None = None, category: str | None = None, family: str | None = None,
                   supplier_id: str | None = None, open_orders: str | None = Query(default=None, pattern=r"^\d{1,12}(\.\d{1,2})?$"),
                   conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        """``open_orders`` is the amount of confirmed unreceived orders that procurement owns; the gateway passes it through and the capital total is made here."""
        today = business_today()
        try:
            fs = FilterSet.parse(today, date_from, date_to, warehouse_id, supplier_id, category, family)
        except FilterError as exc:
            raise HTTPException(422, "request_invalid") from exc
        return build_indicators(conn, today, fs, means(), _p.roles, None if open_orders is None else Decimal(open_orders))

    @router.get("/demand-trend")
    def trend(days: int = Query(default=60, ge=7, le=365), warehouse_id: int | None = None, category: str | None = None, family: str | None = None, supplier_id: str | None = None,
              date_from: date | None = None, date_to: date | None = None, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        """The last ``days`` days, or the range ``date_from``..``date_to`` when given (same rules as every filter). The forecast describes the days after today, so a range that ends before today has none."""
        today = business_today()
        f = filters(warehouse_id, category, family, supplier_id)
        if date_from is None and date_to is None:
            start, end, span = today - timedelta(days=days), today, days
        else:
            try:
                fs = FilterSet.parse(today, date_from, date_to)
            except FilterError as exc:
                raise HTTPException(422, "request_invalid") from exc
            start, end, span = fs.date_from, fs.date_to, (fs.date_to - fs.date_from).days + 1
        fc = forecast_series(conn, today, f, means()) if end == today else {"points": [], "variants": 0, "seed_assisted": 0, "reason": "range_in_past"}
        return {"from": start.isoformat(), "to": end.isoformat(), "series": demand_trend(conn, end, span, f),
                "estimated": fc["points"], "estimated_basis": {"variants": fc["variants"], "seed_assisted": fc["seed_assisted"], "reason": fc["reason"], "upper_level": "0.95"}}

    @router.get("/drilldown")
    def drill(kind: str = Query(max_length=20), abc: str | None = Query(default=None, max_length=1), xyz: str | None = Query(default=None, max_length=1),
              day: str | None = Query(default=None, max_length=10), warehouse_id: int | None = None, category: str | None = None, family: str | None = None,
              supplier_id: str | None = None, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
              sort: str | None = Query(default=None, max_length=10), order: str | None = Query(default=None, max_length=4),
              band: str | None = Query(default=None, max_length=10), date_from: date | None = None, date_to: date | None = None,
              conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        """``demand`` is the units sold in the range ``date_from``..``date_to`` (the card's window); ``band`` picks an expiry band."""
        if kind not in KINDS:
            raise HTTPException(422, "request_invalid")
        today = business_today()
        days, end = None, None
        if kind == "demand":
            try:
                fs = FilterSet.parse(today, date_from, date_to)
            except FilterError as exc:
                raise HTTPException(422, "request_invalid") from exc
            days, end = (fs.date_to - fs.date_from).days + 1, fs.date_to
        try:
            return hide_money_page(drilldown(conn, kind, today, filters(warehouse_id, category, family, supplier_id), means(), abc, xyz, day, limit, offset, sort, order, days, band, end), _p.roles)
        except DrillError as exc:
            raise HTTPException(422, exc.code) from exc

    @router.get("/freshness")
    def freshness(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        """How fresh each source is, where it came from, and how many records were left out of the figures (counts only)."""
        return freshness_payload(conn)

    @router.get("/charts")
    def charts(keys: str | None = Query(default=None, max_length=200), date_from: date | None = None, date_to: date | None = None, warehouse_id: int | None = None,
               category: str | None = None, family: str | None = None, supplier_id: str | None = None, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        """The chart tables for the given filters, one per key (all of them when none are named). Each chart degrades alone; a role without cost access gets no money column."""
        wanted = list(CHART_KEYS) if keys is None else keys.split(",")
        if not wanted or any(k not in BUILDERS for k in wanted):
            raise HTTPException(422, "request_invalid")
        today = business_today()
        try:
            fs = FilterSet.parse(today, date_from, date_to, warehouse_id, supplier_id, category, family)
        except FilterError as exc:
            raise HTTPException(422, "request_invalid") from exc
        return {"charts": build_charts(conn, wanted, today, fs, means(), can_see_money(_p.roles))}

    @router.get("/export")
    def export_file(kind: str = Query(pattern="^(cards|chart|drilldown)$"), chart: str | None = Query(default=None, max_length=30), drill_kind: str | None = Query(default=None, max_length=20),
                    abc: str | None = Query(default=None, max_length=1), xyz: str | None = Query(default=None, max_length=1), day: str | None = Query(default=None, max_length=10),
                    band: str | None = Query(default=None, max_length=10), sort: str | None = Query(default=None, max_length=10), order: str | None = Query(default=None, max_length=4),
                    format: str = Query(default="csv", max_length=8), date_from: date | None = None, date_to: date | None = None, warehouse_id: int | None = None,
                    category: str | None = None, family: str | None = None, supplier_id: str | None = None,
                    conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> Response:
        """One view of the dashboard as a CSV file: the rows and totals of the screen with a header block. Only roles that may see costs; above the row limit it is refused, never cut."""
        if not can_see_money(_p.roles):                       # the file carries amounts: the roles that may see costs only (a viewer is refused)
            raise HTTPException(403, "role_not_allowed")
        if format != "csv":
            raise HTTPException(400, "format_unsupported")
        today = business_today()
        try:
            fs = FilterSet.parse(today, date_from, date_to, warehouse_id, supplier_id, category, family)
            made = build_export(conn, kind, today, fs, means(), chart=chart, drill_kind=drill_kind, params={"abc": abc, "xyz": xyz, "day": day, "band": band, "sort": sort, "order": order})
        except ExportTooLarge as exc:
            log.warning("dashboard_export_refused kind=%s reason=%s", kind, exc.code)
            raise HTTPException(413, exc.code) from exc
        except (FilterError, ExportRequestInvalid, DrillError) as exc:
            raise HTTPException(422, getattr(exc, "code", "request_invalid")) from exc
        body = to_csv(made)
        log.info("dashboard_export kind=%s rows=%d bytes=%d", kind, len(made.rows), len(body))
        return Response(body, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="panel-{kind}-{today:%Y%m%d}.csv"', "X-Export-Rows": str(len(made.rows))})

    @router.get("/skus/{sku}")
    def sku_page(sku: str = Path(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,59}$"), conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        """One product by SKU; cost fields exist only in the response of a role that may see costs."""
        try:
            return sku_detail(conn, sku, business_today(), means(), can_see_money(_p.roles))
        except SkuNotFound as exc:
            raise HTTPException(404, exc.code) from exc

    @router.get("/abc-xyz")
    def abc_xyz(date_from: date | None = None, date_to: date | None = None, warehouse_id: int | None = None, category: str | None = None, family: str | None = None,
                supplier_id: str | None = None, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        f = filters(warehouse_id, category, family, supplier_id)
        try:
            FilterSet.parse(business_today(), date_from, date_to)
        except FilterError as exc:
            raise HTTPException(422, "request_invalid") from exc
        unsupported = [n for n, given in (("warehouse", warehouse_id is not None), ("date_range", date_from is not None or date_to is not None)) if given]
        return {"cells": hide_cell_values([{**d, "value": str(d["value"].quantize(Decimal("0.01")))} for d in abc_xyz_distribution(conn, f)], _p.roles), "filters_unsupported": unsupported}

    return router
