"""T129: how well the previous run forecast what then happened (WAPE, bias, stock-out share), by demand group and overall.

When a newer series export reaches at least ``WINDOW`` days beyond the previous run's last day, the previous run's 7-day forecast is compared with the
real ERP demand of those 7 days. A variant with a stocked-out (censored) day in the window is not scored, because its demand was not observable; it
counts towards the stock-out share instead. Seeds are never used here: only real demand is compared. Evaluating the same run twice changes nothing.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from db.tables import forecast_accuracy, forecast_runs, forecast_values
from sqlalchemy import insert, select
from sqlalchemy.engine import Connection

WINDOW = 7
METRICS = ("wape", "bias", "stockout_rate")


def _window_demand(s: dict[str, Any], first: date, last: date) -> tuple[int, bool] | None:
    start = date.fromisoformat(s["start_day"])
    n = len(s["demand"])
    if first < start or last > start + timedelta(days=n - 1):
        return None
    lo = (first - start).days
    return sum(s["demand"][lo:lo + WINDOW]), any(s["censored"][lo:lo + WINDOW])


def evaluate_previous(conn: Connection, export: dict[str, Any]) -> str | None:
    """Scores the latest completed run against ``export``; returns its run id when new rows were stored."""
    prev = conn.execute(select(forecast_runs).where(forecast_runs.c.status == "completed").order_by(forecast_runs.c.finished_at.desc()).limit(1)).first()
    if prev is None or not prev.through_day:
        return None
    if conn.execute(select(forecast_accuracy.c.id).where(forecast_accuracy.c.run_id == prev.id).limit(1)).first():
        return None
    first = date.fromisoformat(prev.through_day) + timedelta(days=1)
    last = first + timedelta(days=WINDOW - 1)
    means = {r.variant_id: r.mean for r in conn.execute(select(forecast_values).where(forecast_values.c.run_id == prev.id, forecast_values.c.horizon_days == WINDOW,
                                                                                  forecast_values.c.eligible.is_(True))).all() if r.mean is not None}
    groups: dict[str, dict[str, Any]] = {}

    def bucket(name: str) -> dict[str, Any]:
        return groups.setdefault(name, {"abs": 0.0, "act": 0.0, "fc": 0.0, "scored": 0, "stocked_out": 0, "total": 0})

    for s in export["series"]:
        vid = int(s["variant_id"])
        if vid not in means:
            continue
        got = _window_demand(s, first, last)
        if got is None:
            continue
        actual, censored = got
        abc = (s.get("segment") or {}).get("abc") or "?"
        for name in ("all", abc):
            b = bucket(name)
            b["total"] += 1
            if censored:
                b["stocked_out"] += 1
                continue
            b["scored"] += 1
            b["abs"] += abs(actual - means[vid])
            b["act"] += actual
            b["fc"] += means[vid]
    if not groups:
        return None
    rows = []
    for name, b in groups.items():
        if b["act"] > 0:
            rows.append({"run_id": prev.id, "segment": name, "metric": "wape", "value": Decimal(str(round(b["abs"] / b["act"], 6))), "window_days": WINDOW})
            rows.append({"run_id": prev.id, "segment": name, "metric": "bias", "value": Decimal(str(round((b["fc"] - b["act"]) / b["act"], 6))), "window_days": WINDOW})
        rows.append({"run_id": prev.id, "segment": name, "metric": "stockout_rate", "value": Decimal(str(round(b["stocked_out"] / b["total"], 6))), "window_days": WINDOW})
    conn.execute(insert(forecast_accuracy), rows)
    return str(prev.id)


def _history(conn: Connection, limit: int) -> list[dict[str, Any]]:
    """Overall WAPE and bias of each scored run, newest first (feature 006: accuracy over time)."""
    rows = conn.execute(select(forecast_accuracy.c.run_id, forecast_accuracy.c.metric, forecast_accuracy.c.value, forecast_runs.c.through_day, forecast_runs.c.finished_at)
                        .join(forecast_runs, forecast_runs.c.id == forecast_accuracy.c.run_id)
                        .where(forecast_accuracy.c.segment == "all", forecast_accuracy.c.metric.in_(("wape", "bias"))).order_by(forecast_runs.c.finished_at.desc())).all()
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        if r.run_id not in out and len(out) >= limit:
            continue
        out.setdefault(r.run_id, {"run_id": r.run_id, "through_day": r.through_day, "metrics": {}})["metrics"][r.metric] = str(Decimal(str(r.value)).quantize(Decimal("0.0001")))
    return list(out.values())


def latest_accuracy(conn: Connection, history: int = 0) -> dict[str, Any]:
    run = conn.execute(select(forecast_accuracy.c.run_id).join(forecast_runs, forecast_runs.c.id == forecast_accuracy.c.run_id).order_by(forecast_runs.c.finished_at.desc()).limit(1)).first()
    if run is None:
        return {"run_id": None, "window_days": WINDOW, "metrics": {}, "percent": {}, "history": []}
    out: dict[str, dict[str, str]] = {}
    for r in conn.execute(select(forecast_accuracy).where(forecast_accuracy.c.run_id == run.run_id).order_by(forecast_accuracy.c.segment, forecast_accuracy.c.metric)).all():
        out.setdefault(r.segment, {})[r.metric] = str(Decimal(str(r.value)).quantize(Decimal("0.0001")))
    percent = {seg: {k: str((Decimal(v) * 100).quantize(Decimal("0.01"))) for k, v in m.items() if k in ("wape", "bias")} for seg, m in out.items()}      # for the dashboard: the gateway does no arithmetic
    return {"run_id": run.run_id, "window_days": WINDOW, "metrics": out, "percent": {s: p for s, p in percent.items() if p}, "history": _history(conn, history) if history > 0 else []}
