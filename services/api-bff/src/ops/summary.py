"""Backup and cost cards for the admin console (feature 010, US5). Money is Decimal; figures come only from validated snapshots."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from db.ops import OpsStore


def _stale(snap: dict[str, Any], now: datetime, hours: int) -> bool:
    return now - datetime.fromisoformat(snap["captured_at"]) > timedelta(hours=hours)


def summary(ops: OpsStore, now: datetime) -> dict[str, Any]:
    s = ops.settings()
    out: dict[str, Any] = {}
    backup = ops.latest_snapshot("backup")
    if backup is None or backup["status"] != "ok":
        out["backup"] = {"ok": False, "error": "snapshot_unavailable"}
    else:
        last = backup["payload"].get("last_success_at")
        out["backup"] = {"ok": True, "data": {**backup["payload"], "captured_at": backup["captured_at"], "stale_snapshot": _stale(backup, now, s["backup_max_age_hours"]),
                                              "old": last is None or now - datetime.fromisoformat(last) > timedelta(hours=s["backup_max_age_hours"])}}
    cost = ops.latest_snapshot("cost")
    if cost is None or cost["status"] != "ok":
        out["cost"] = {"ok": False, "error": "snapshot_unavailable"}
    else:
        p = cost["payload"]
        budget, projected = Decimal(p["budget"]), Decimal(p["projected"])
        pct = (projected / budget * 100) if budget > 0 else Decimal(0)
        level = "critical" if pct >= s["budget_critical_pct"] else "warning" if pct >= s["budget_warn_pct"] else "ok"
        out["cost"] = {"ok": True, "data": {**p, "captured_at": cost["captured_at"], "stale_snapshot": _stale(cost, now, 48), "projected_pct": str(pct.quantize(Decimal("0.1"))),
                                            "level": level, "projection_is_estimate": bool(p["partial_month"])}}
    return out
