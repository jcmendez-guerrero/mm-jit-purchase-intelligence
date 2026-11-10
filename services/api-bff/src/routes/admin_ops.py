"""Operations console (feature 010): one queue view, alerts, thresholds and the backup and cost cards. Admin only.

Holds no business rule and no cross-schema access: downstream facts come through the existing clients, figures from the
platform arrive as validated snapshots (ops/snapshots.py). A card that cannot be read degrades alone.
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from auth.session import SessionData
from clients.forecast import ForecastClient
from clients.inventory import InventoryClient
from db.ops import OpsError, OpsStore
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from ops.alerts import Facts, evaluate, sync, utc
from ops.summary import summary
from pydantic import BaseModel, ConfigDict, StrictInt
from routes.admin_roles import _mirror_pass, get_store
from routes.admin_status import _card
from routes.api import get_inventory_client
from routes.policies import get_forecast_client
from routes.rbac import require_fresh_mfa, require_roles

router = APIRouter(prefix="/admin", tags=["admin"])
ITEM_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
JOB_STATE = {"queued": "waiting", "running": "running", "done": "succeeded", "failed": "failed"}
RUN_STATE = {"running": "running", "completed": "succeeded", "failed": "failed"}


def get_ops() -> OpsStore:
    return OpsStore(get_store().engine)


def delivery_configured() -> bool:
    return os.environ.get("MMI_ALERT_EMAIL_CONFIGURED") == "1"


def _mirror_items(now: datetime) -> list[dict[str, Any]]:
    status = get_store().mirror_status(now, item_limit=100)
    return [{"kind": "mirror", "id": str(i["id"]), "state": "dead_lettered" if i["status"] == "failed" else "waiting", "attempts": i["attempts"],
             "reason_code": i["last_error_key"]} for i in status["items"]]


def _message_items(ops: OpsStore, now: datetime, limit_hours: int) -> list[dict[str, Any]]:
    snap = ops.latest_snapshot("queues")
    if not snap or snap["status"] != "ok":
        return []
    stale = now - datetime.fromisoformat(snap["captured_at"]) > timedelta(hours=limit_hours)
    return [{"kind": "message", "id": d["queue"], "state": "dead_lettered", "attempts": d["count"], "reason_code": d.get("reason_code"), "stale": stale}
            for d in snap["payload"].get("dead_lettered", []) if d["count"] > 0]


def _downstream_items(jobs: dict[str, Any], runs: dict[str, Any]) -> list[dict[str, Any]] | None:
    """None when neither card could be read (unknown, so alerts for these conditions are left untouched)."""
    if not jobs["ok"] and not runs["ok"]:
        return None
    out: list[dict[str, Any]] = []
    if jobs["ok"]:
        out += [{"kind": "import", "id": j["id"], "state": JOB_STATE.get(j["state"], "waiting"), "attempts": 0, "reason_code": j.get("error_key")}
                for j in jobs["data"].get("jobs", [])]
    if runs["ok"]:
        out += [{"kind": "forecast", "id": r["id"], "state": RUN_STATE.get(r["status"], "waiting"), "attempts": 0, "reason_code": None}
                for r in runs["data"].get("runs", [])]
    return out


async def _queue(session: SessionData, fc: ForecastClient, ops: OpsStore, now: datetime) -> tuple[list[dict[str, Any]], bool]:
    who = {"user_id": session.user_id, "roles": session.roles}
    jobs, runs = await _card(fc.forward("GET", "/imports/jobs", **who)), await _card(fc.forward("GET", "/runs", params={"limit": 10}, **who))
    down = _downstream_items(jobs, runs)
    items = _mirror_items(now) + _message_items(ops, now, ops.settings()["backup_max_age_hours"]) + (down or [])
    return items, down is not None


def _freshness(card: dict[str, Any]) -> dict[str, datetime | None] | None:
    if not card["ok"]:
        return None
    d = card["data"]

    def ts(v: str | None) -> datetime | None:
        if not v:
            return None
        return utc(datetime.fromisoformat(v + "T00:00:00" if len(v) == 10 else v.replace("Z", "+00:00")))

    return {"snapshots": ts(d["stock_snapshots"]["latest_day"]), "movements": ts(d["movements"]["latest_at"]), "aggregates": ts(d["aggregates"]["refreshed_at"])}


def refresh_alerts(ops: OpsStore, now: datetime, source_last: dict[str, datetime | None] | None = None,
                   queue_items: list[dict[str, Any]] | None = None) -> None:
    """One evaluation over what is known. Called when the console reads alerts and by the scheduled worker."""
    settings = ops.settings()
    mirror = get_store().mirror_status(now)
    facts = Facts(now=now, settings=settings, source_last=source_last, queue_items=queue_items, mirror_oldest_pending_seconds=mirror["oldest_pending_seconds"],
                  backup=ops.latest_snapshot("backup"), cost=ops.latest_snapshot("cost"), delivery_configured=delivery_configured())
    signals, evaluated = evaluate(facts)
    sync(ops, signals, evaluated, now, settings["alert_repeat_hours"])


# ---- queue ----
@router.get("/ops/queue")
async def queue(session: SessionData = Depends(require_roles("admin")), fc: ForecastClient = Depends(get_forecast_client)) -> dict[str, Any]:
    items, _ = await _queue(session, fc, get_ops(), datetime.now(UTC))
    return {"items": items}


@router.post("/ops/queue/{kind}/{item_id}/retry", status_code=202)
async def retry(kind: str, item_id: str, background: BackgroundTasks, session: SessionData = Depends(require_roles("admin")),
                _fresh: SessionData = Depends(require_fresh_mfa()), fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    if kind not in ("mirror", "import", "forecast") or not ITEM_ID.match(item_id):
        raise HTTPException(422, "request_invalid")
    store = get_store()
    if kind == "mirror":
        if not item_id.isdigit():
            raise HTTPException(422, "request_invalid")
        if not any(i["id"] == int(item_id) for i in store.mirror_status(item_limit=10_000)["items"]):
            raise HTTPException(404, "ops_item_unknown")
        out: Any = {"requeued": store.requeue_failed(item_id=int(item_id))}     # 0 when it was not dead-lettered: a clear no-op
        background.add_task(_mirror_pass)
    elif kind == "import":
        out = await fc.forward("POST", f"/imports/jobs/{item_id}/rerun", user_id=session.user_id, roles=session.roles)
    else:
        out = await fc.forward("POST", "/runs", user_id=session.user_id, roles=session.roles)
    store.record_action(session.user_id, "ops.queue.retry", f"{kind}:{item_id}", after={k: out.get(k) for k in ("reused", "state", "requeued") if isinstance(out, dict) and k in out})
    return out


# ---- alerts and thresholds ----
@router.get("/alerts")
async def list_alerts(session: SessionData = Depends(require_roles("admin")), fc: ForecastClient = Depends(get_forecast_client),
                      inv: InventoryClient = Depends(get_inventory_client)) -> dict[str, Any]:
    ops, now = get_ops(), datetime.now(UTC)
    items, known = await _queue(session, fc, ops, now)
    freshness = _freshness(await _card(inv.forward("GET", "/status/sources", user_id=session.user_id, roles=session.roles)))
    refresh_alerts(ops, now, freshness, items if known else None)
    return {"items": ops.list_alerts(), "delivery_configured": delivery_configured()}


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge(alert_id: int, session: SessionData = Depends(require_roles("admin")), _fresh: SessionData = Depends(require_fresh_mfa())) -> dict[str, Any]:
    try:
        return get_ops().acknowledge(alert_id, session.user_id)
    except OpsError as exc:
        raise HTTPException(404, exc.code) from exc


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_stale_hours: StrictInt | None = None
    backup_max_age_hours: StrictInt | None = None
    budget_warn_pct: StrictInt | None = None
    budget_critical_pct: StrictInt | None = None
    mirror_lag_minutes: StrictInt | None = None
    alert_repeat_hours: StrictInt | None = None


@router.get("/ops/settings")
def get_settings(_: SessionData = Depends(require_roles("admin"))) -> dict[str, int]:
    return get_ops().settings()


@router.put("/ops/settings")
def put_settings(body: SettingsUpdate, session: SessionData = Depends(require_roles("admin")), _fresh: SessionData = Depends(require_fresh_mfa())) -> dict[str, int]:
    try:
        return get_ops().set_settings(body.model_dump(exclude_none=True), actor=session.user_id)
    except OpsError as exc:
        raise HTTPException(422, exc.code) from exc


# ---- backup and cost cards (figures and arithmetic live in ops/summary.py: routes do no money arithmetic) ----
@router.get("/ops/summary")
def ops_summary(_: SessionData = Depends(require_roles("admin"))) -> dict[str, Any]:
    return summary(get_ops(), datetime.now(UTC))
