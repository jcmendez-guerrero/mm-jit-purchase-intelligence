"""Feature 014 (FR-011, FR-012): the dashboard in a file. The rows come from the same code as the screen (``build_indicators``, ``build_charts``, ``drilldown``), so the file and
the screen always agree; the row type holds only SKU, name and figures, so no note, tax id or internal id can reach a file.

The file is CSV for a Spanish-locale spreadsheet: UTF-8 with a byte-order mark, semicolon separator, decimal comma. A text cell that starts with ``=``, ``+``, ``-``, ``@``, a tab
or a carriage return is prefixed with an apostrophe so no program runs it as a formula; numeric cells are numbers and are never altered. A result above ``MAX_ROWS`` is refused,
never cut off. XLSX is not offered (the writer lives in procurement-service; see the feature 014 closure report).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from businessday import LOCAL_TZ
from sqlalchemy.engine import Connection

from dashboard.drilldown import KINDS as DRILL_KINDS
from dashboard.drilldown import drilldown
from dashboard.filters import FilterSet
from dashboard.freshness import inventory_freshness
from dashboard.indicators import build_indicators
from dashboard.kpis import ForecastMeans
from dashboard.series import BUILDERS, build_charts

MAX_ROWS = 5000
PAGE = 200
BOM = "﻿"
UNSAFE_START = ("=", "+", "-", "@", "\t", "\r")

TITLES = {
    "inventory_value": "Productos que forman el valor del inventario", "coverage": "Productos con menos días de cobertura",
    "stockout_risk": "Productos con riesgo de rotura de stock", "expiry_risk": "Productos con riesgo de caducidad", "abc_xyz": "Productos del grupo ABC/XYZ",
    "trend_day": "Productos vendidos en el día", "demand": "Productos que forman la demanda del periodo", "forecast": "Productos que forman la previsión de 28 días",
    "capital": "Productos que forman el capital inmovilizado en stock", "expiry_band": "Productos que caducan en el tramo",
}
FIGURE = {"inventory_value": ("Valor (EUR)", True), "abc_xyz": ("Valor (EUR)", True), "capital": ("Valor (EUR)", True), "expiry_band": ("Valor (EUR)", True),
          "coverage": ("Días de cobertura", True), "trend_day": ("Unidades", True), "demand": ("Unidades", True), "forecast": ("Unidades", True)}
CHART_TITLES = {
    "demand_forecast": "Demanda real y previsión", "abc_xyz": "Productos por grupo ABC/XYZ", "expiry_bands": "Valor que caduca por tramo",
    "coverage_buckets": "Productos por días de cobertura", "capital_by_group": "Capital en stock por grupo ABC", "stock_value_history": "Evolución del inventario valorado",
}
COLUMN = {"band": "Tramo", "bucket": "Cobertura", "group": "Grupo", "products": "Productos", "value": "Valor (EUR)", "day": "Día", "actual": "Unidades reales",
          "forecast_mean": "Previsión (media)", "forecast_upper": "Previsión (límite superior)"}
CELL = {"expired": "Caducado", "d0_30": "0 a 30 días", "d31_60": "31 a 60 días", "d0_7": "Hasta 7 días", "d8_14": "8 a 14 días", "d15_30": "15 a 30 días",
        "d61_plus": "Más de 60 días", "no_demand": "Sin demanda", "none": "Sin clasificar"}
INDICATORS = {"capital_tied_up": "Capital inmovilizado", "stock_value": "Valor del stock", "coverage_days": "Cobertura", "demand": "Demanda", "forecast": "Previsión", "stockout_risk": "Riesgo de rotura",
              "expiry_exposure": "Exposición a caducidad"}
UNITS = {"EUR": "EUR", "days": "días", "units": "unidades", "count": "productos", "percent": "%"}
STATES = {"ok": "Correcto", "no_data": "Sin datos", "stale": "Desactualizado", "error": "Error", "hidden_by_role": "Oculto por rol"}
FRESH_STATES = {"ok": "al día", "stale": "desactualizado", "no_data": "sin datos"}
SOURCES = {"inventory_snapshot": "Existencias", "movements": "Movimientos", "aggregates": "Agregados"}


class ExportTooLarge(Exception):
    code = "export_too_large"


class ExportRequestInvalid(Exception):
    code = "request_invalid"


@dataclass
class Export:
    title: str
    columns: list[tuple[str, bool]]                      # (label, numeric)
    rows: list[list[Any]]
    total: list[Any] | None = None
    notes: list[tuple[str, str]] = field(default_factory=list)
    header: list[tuple[str, str]] = field(default_factory=list)


def neutralise(value: Any) -> str:
    """A text cell is kept as text: anything a spreadsheet could read as a formula gets a leading apostrophe."""
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(UNSAFE_START) else text


def number(value: Any) -> str:
    """A numeric cell in Spanish format (decimal comma, no thousands separator). Never prefixed: a negative figure is a number, not a formula."""
    if value is None:
        return ""
    return str(value).replace(".", ",") if isinstance(value, (str, Decimal)) else str(value)


def _filters_text(fs: FilterSet) -> str:
    parts = [(f"Almacén: {fs.warehouse_id}" if fs.warehouse_id is not None else ""), (f"Categoría: {fs.category}" if fs.category else ""),
             (f"Familia: {fs.family}" if fs.family else ""), (f"Proveedor: {fs.supplier_id}" if fs.supplier_id else "")]
    return ", ".join(p for p in parts if p) or "Sin filtros"


def _header(conn: Connection, title: str, fs: FilterSet, now: datetime) -> list[tuple[str, str]]:
    fresh = "; ".join(f"{SOURCES.get(f.source, f.source)}: {FRESH_STATES.get(f.state, f.state)}"
                      + (f" ({f.refreshed_at.astimezone(UTC).isoformat(timespec='seconds')})" if f.refreshed_at else "") for f in inventory_freshness(conn, now))
    return [("Informe", title), ("Filtros", _filters_text(fs)), ("Periodo", f"{fs.date_from.isoformat()} a {fs.date_to.isoformat()}"), ("Frescura", fresh),
            ("Generado (UTC)", now.astimezone(UTC).isoformat(timespec="seconds")), ("Generado (Madrid)", now.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M"))]


def _cards(conn: Connection, today: date, fs: FilterSet, forecast: ForecastMeans | None, now: datetime, open_orders: Decimal | None = None) -> Export:
    payload = build_indicators(conn, today, fs, forecast, ["buyer"], open_orders, now)
    # Capital needs procurement's open orders: without them the row is left out (never half a total) and named in the header.
    rows = [[INDICATORS[i["key"]], i["value"], UNITS.get(i["unit"], i["unit"]), STATES.get(i["state"], i["state"])] for i in payload["indicators"]
            if i["key"] in INDICATORS and (i["key"] != "capital_tied_up" or open_orders is not None)]
    outside = "presupuesto de compras y error de previsión" if open_orders is not None else "capital inmovilizado, presupuesto de compras y error de previsión"
    return Export("Indicadores del panel", [("Indicador", False), ("Valor", True), ("Unidad", False), ("Estado", False)], rows,
                  notes=[("Fuera de este archivo", f"{outside[0].upper()}{outside[1:]}: dependen de compras y de previsión")])


def _chart(conn: Connection, key: str, today: date, fs: FilterSet, forecast: ForecastMeans | None) -> Export:
    chart = build_charts(conn, [key], today, fs, forecast, True)[0]
    title = CHART_TITLES[key]
    if chart["state"] != "ok":
        reason = chart.get("summary_params", {}).get("reason", chart["state"])
        return Export(title, [(COLUMN.get(c, c), i > 0) for i, c in enumerate(chart["columns"])], [], notes=[("Estado", f"Sin datos ({reason})")])
    cols = chart["columns"]
    rows = [[CELL.get(str(v), v) if i == 0 else v for i, v in enumerate(r)] for r in chart["rows"]]
    return Export(title, [(COLUMN.get(c, c), i > 0) for i, c in enumerate(cols)], rows)


def _drill(conn: Connection, kind: str, today: date, fs: FilterSet, forecast: ForecastMeans | None, params: dict[str, Any]) -> Export:
    if kind not in DRILL_KINDS:
        raise ExportRequestInvalid()
    days, end = None, None
    if kind == "demand":
        days, end = (fs.date_to - fs.date_from).days + 1, fs.date_to
    f = fs.to_filters()
    a = {k: params.get(k) for k in ("abc", "xyz", "day", "sort", "order", "band")}

    def page(offset: int) -> dict[str, Any]:
        return drilldown(conn, kind, today, f, forecast, a["abc"], a["xyz"], a["day"], PAGE, offset, a["sort"], a["order"], days, a["band"], end)

    first = page(0)
    if first["total"] > MAX_ROWS:
        raise ExportTooLarge()
    rows = list(first["rows"])
    while len(rows) < first["total"]:
        rows += page(len(rows))["rows"]
    figure = FIGURE.get(kind) if kind not in ("stockout_risk", "expiry_risk") else None
    cols = [("SKU", False), ("Producto", False)] + ([figure] if figure else [])
    out = [[r["sku"], r["name"]] + ([r["figure"]] if figure else []) for r in rows]
    title = TITLES[kind] + (f" {a['abc']}{a['xyz']}" if kind == "abc_xyz" and a["abc"] and a["xyz"] else "") + (f" {a['day']}" if kind == "trend_day" and a["day"] else "") \
        + (f" ({CELL.get(a['band'] or '', a['band'])})" if kind == "expiry_band" and a["band"] else "")
    return Export(title, cols, out, total=["Total", "", first["sum"]] if figure and first["sum"] is not None else None)


def build_export(conn: Connection, kind: str, today: date, fs: FilterSet, forecast: ForecastMeans | None, *, chart: str | None = None,
                 drill_kind: str | None = None, params: dict[str, Any] | None = None, now: datetime | None = None, open_orders: Decimal | None = None, loaded_at: datetime | None = None) -> Export:
    """The file content for one view of the dashboard. Raises ``ExportRequestInvalid`` for an unknown view and ``ExportTooLarge`` above the row limit."""
    now = now or datetime.now(UTC)
    if kind == "cards":
        out = _cards(conn, today, fs, forecast, now, open_orders)
    elif kind == "chart":
        if chart not in BUILDERS:
            raise ExportRequestInvalid()
        out = _chart(conn, chart, today, fs, forecast)
    elif kind == "drilldown":
        out = _drill(conn, drill_kind or "", today, fs, forecast, params or {})
    else:
        raise ExportRequestInvalid()
    if len(out.rows) > MAX_ROWS:
        raise ExportTooLarge()
    out.header = _header(conn, out.title, fs, now)
    if loaded_at is not None:                                       # the file always holds the latest data; say so when the screen was showing older data
        aware = lambda t: t.replace(tzinfo=UTC) if t.tzinfo is None else t      # noqa: E731 - sources give naive and aware times alike
        latest = max((aware(f.refreshed_at) for f in inventory_freshness(conn, now) if f.refreshed_at is not None), default=None)
        if latest is not None and latest > aware(loaded_at):
            out.notes.append(("Aviso", "El archivo contiene datos más recientes que los que se veían en pantalla al exportar"))
    return out


def to_csv(e: Export) -> bytes:
    buf = io.StringIO(newline="")
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    for key, value in [*e.header, *e.notes]:
        w.writerow([key, neutralise(value)])
    w.writerow([])
    w.writerow([label for label, _numeric in e.columns])
    for row in [*e.rows, *([e.total] if e.total else [])]:
        w.writerow([number(v) if numeric else neutralise(v) for v, (_label, numeric) in zip(row, e.columns, strict=False)])
    return (BOM + buf.getvalue()).encode("utf-8")
