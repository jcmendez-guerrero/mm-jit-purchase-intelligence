"""Alert evaluation (feature 010, US4): a pure function from facts to signals, then a de-duplicating sync.

Conditions that could not be evaluated (a downstream card was unavailable) are left alone: their alerts are neither opened nor
closed. Each opening writes ONE stable log marker (ADMIN_ALERT_OPENED) that the platform's e-mail rule matches; the marker carries
codes only. A condition that flaps does not repeat its marker inside ``alert_repeat_hours``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

log = logging.getLogger("mmi.api_bff.alerts")

CONDITIONS = ("source_stale", "job_failed", "message_dead_lettered", "mirror_lag", "backup_old", "backup_missing",
              "budget_warning", "budget_critical", "delivery_unconfigured")
_SAFE = re.compile(r"[^a-z0-9_.:-]")
_BUDGET = ("budget_warning", "budget_critical")
_BACKUP = ("backup_old", "backup_missing")


@dataclass(frozen=True)
class Signal:
    condition_key: str
    subject: str
    severity: str


@dataclass
class Facts:
    now: datetime
    settings: dict[str, int]
    source_last: dict[str, datetime | None] | None = None            # None = unknown
    queue_items: list[dict[str, Any]] | None = None
    mirror_oldest_pending_seconds: int | None = None
    backup: dict[str, Any] | None = None                              # latest backup snapshot as stored (payload, status, captured_at)
    cost: dict[str, Any] | None = None
    delivery_configured: bool = True
    unknown: set[str] = field(default_factory=set)


def _safe(subject: str) -> str:
    return _SAFE.sub("_", subject.lower())[:80]


def evaluate(f: Facts) -> tuple[list[Signal], set[str]]:
    """Returns (signals, conditions that were evaluated)."""
    out: list[Signal] = []
    evaluated: set[str] = set(CONDITIONS)
    if f.source_last is None:
        evaluated.discard("source_stale")
    else:
        limit = timedelta(hours=f.settings["source_stale_hours"])
        for key, last in f.source_last.items():
            if last is None or f.now - last > limit:
                out.append(Signal("source_stale", _safe(key), "warning"))
    if f.queue_items is None:
        evaluated -= {"job_failed", "message_dead_lettered"}
    else:
        for it in f.queue_items:
            sub = _safe(f"{it['kind']}:{it['id']}")
            if it["state"] == "failed":
                out.append(Signal("job_failed", sub, "critical"))
            elif it["state"] == "dead_lettered":
                out.append(Signal("message_dead_lettered", sub, "critical"))
    if f.mirror_oldest_pending_seconds is None:
        evaluated.discard("mirror_lag")
    elif f.mirror_oldest_pending_seconds > f.settings["mirror_lag_minutes"] * 60:
        out.append(Signal("mirror_lag", "role_mirror", "warning"))
    last_ok = (f.backup or {}).get("payload", {}).get("last_success_at") if f.backup and f.backup["status"] == "ok" else None
    if f.backup is None or f.backup["status"] != "ok" or not last_ok:
        out.append(Signal("backup_missing", "backup", "critical"))
    elif f.now - datetime.fromisoformat(last_ok) > timedelta(hours=f.settings["backup_max_age_hours"]):
        out.append(Signal("backup_old", "backup", "warning"))
    cost = f.cost["payload"] if f.cost and f.cost["status"] == "ok" else None
    if cost is None:
        evaluated -= set(_BUDGET)                                      # unknown spend: say nothing, show "unavailable" in the card
    else:
        budget, projected = Decimal(cost["budget"]), Decimal(cost["projected"])
        pct = (projected / budget * 100) if budget > 0 else Decimal(0)
        if pct >= f.settings["budget_critical_pct"]:
            out.append(Signal("budget_critical", "azure_budget", "critical"))
        elif pct >= f.settings["budget_warn_pct"]:
            out.append(Signal("budget_warning", "azure_budget", "warning"))
    if not f.delivery_configured:
        out.append(Signal("delivery_unconfigured", "email", "warning"))
    return out, evaluated


def sync(store: Any, signals: list[Signal], evaluated: set[str], now: datetime, repeat_hours: int,
         repeat_after: dict[str, int] | None = None) -> list[Signal]:
    """Applies signals to the alert table and returns the alerts that were newly opened (one marker each)."""
    opened = store.apply_signals(signals, evaluated, now, repeat_hours, repeat_after)
    for s in opened:
        log.warning("ADMIN_ALERT_OPENED condition=%s subject=%s", s.condition_key, s.subject)
    return opened


def utc(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)
