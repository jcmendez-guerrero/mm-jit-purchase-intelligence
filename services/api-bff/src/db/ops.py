"""Settings, alerts and operations snapshots for the BFF schema (feature 010). Same engine as the role store, no cross-schema SQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from audit import append as append_audit
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from .tables import alert_observations, alerts, ops_settings, ops_snapshots

DEFAULTS: dict[str, int] = {"source_stale_hours": 36, "backup_max_age_hours": 26, "budget_warn_pct": 80, "budget_critical_pct": 100,
                            "mirror_lag_minutes": 15, "alert_repeat_hours": 24, "job_failed_observations": 2}
RANGES: dict[str, tuple[int, int]] = {"source_stale_hours": (1, 720), "backup_max_age_hours": (1, 720), "budget_warn_pct": (1, 500),
                                      "budget_critical_pct": (1, 500), "mirror_lag_minutes": (1, 1440), "alert_repeat_hours": (1, 720), "job_failed_observations": (1, 20)}


class OpsError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _aware(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _alert(r: Any) -> dict[str, Any]:
    return {"id": r.id, "condition_key": r.condition_key, "subject": r.subject, "severity": r.severity, "state": r.state,
            "opened_at": _aware(r.opened_at).isoformat(), "last_seen_at": _aware(r.last_seen_at).isoformat(),
            "acknowledged_by": r.acknowledged_by, "acknowledged_at": _aware(r.acknowledged_at).isoformat() if r.acknowledged_at else None,
            "reason_code": r.reason_code}


class OpsStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    # ---- settings ----
    def settings(self) -> dict[str, int]:
        with self.engine.connect() as conn:
            stored = {r.key: int(r.value) for r in conn.execute(select(ops_settings)).all()}
        return {**DEFAULTS, **{k: v for k, v in stored.items() if k in DEFAULTS}}

    def set_settings(self, updates: dict[str, Any], actor: str, now: datetime | None = None) -> dict[str, int]:
        if not updates or any(k not in DEFAULTS for k in updates):
            raise OpsError("ops_settings_invalid")
        for k, v in updates.items():
            lo, hi = RANGES[k]
            if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
                raise OpsError("ops_settings_invalid")
        merged = {**self.settings(), **updates}
        if merged["budget_warn_pct"] >= merged["budget_critical_pct"]:
            raise OpsError("ops_settings_invalid")
        now = now or datetime.now(UTC)
        with self.engine.begin() as conn:
            for k, v in updates.items():
                if conn.execute(select(ops_settings.c.key).where(ops_settings.c.key == k)).first():
                    conn.execute(update(ops_settings).where(ops_settings.c.key == k).values(value=v, updated_by=actor, updated_at=now))
                else:
                    conn.execute(insert(ops_settings).values(key=k, value=v, updated_by=actor, updated_at=now))
            append_audit(conn, actor, "ops.settings.changed", "ops_settings", "thresholds", after=dict(sorted(updates.items())), now=now)
        return merged

    # ---- snapshots ----
    def add_snapshot(self, kind: str, captured_at: datetime, original: str, payload: dict[str, Any], status: str) -> bool:
        """Returns False when the same (kind, captured_at) is already stored, so re-reading an input file is harmless."""
        with self.engine.begin() as conn:
            dup = conn.execute(select(ops_snapshots.c.id).where(ops_snapshots.c.kind == kind, ops_snapshots.c.captured_at == captured_at)).first()
            if dup:
                return False
            conn.execute(insert(ops_snapshots).values(kind=kind, captured_at=captured_at, captured_at_original=original[:40], payload=payload, status=status))
            return True

    def latest_snapshot(self, kind: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            r = conn.execute(select(ops_snapshots).where(ops_snapshots.c.kind == kind).order_by(ops_snapshots.c.captured_at.desc(), ops_snapshots.c.id.desc()).limit(1)).first()
        if not r:
            return None
        return {"kind": r.kind, "captured_at": _aware(r.captured_at).isoformat(), "captured_at_original": r.captured_at_original,
                "payload": r.payload, "status": r.status}

    # ---- alerts ----
    def apply_signals(self, signals: list[Any], evaluated: set[str], now: datetime, repeat_hours: int,
                      repeat_after: dict[str, int] | None = None) -> list[Any]:
        """Opens, refreshes and closes alerts. Returns the signals whose opening should be announced (one marker each).

        ``repeat_after`` maps a condition to the number of consecutive evaluations that must see it before an alert opens
        ("fails repeatedly"); a condition that disappears resets its count.
        """
        notify: list[Any] = []
        repeat_after = repeat_after or {}
        wanted = {(s.condition_key, s.subject): s for s in signals}
        with self.engine.begin() as conn:
            live = {(r.condition_key, r.subject): r for r in conn.execute(select(alerts).where(alerts.c.state != "closed")).all()}
            seen = {(r.condition_key, r.subject): r for r in conn.execute(select(alert_observations)).all()}
            for key, sig in wanted.items():
                if key in live:
                    conn.execute(update(alerts).where(alerts.c.id == live[key].id).values(last_seen_at=now, severity=sig.severity))
                    continue
                need = repeat_after.get(key[0], 1)
                if need > 1:
                    count = (seen[key].count + 1) if key in seen else 1
                    if key in seen:
                        conn.execute(update(alert_observations).where(alert_observations.c.condition_key == key[0], alert_observations.c.subject == key[1]).values(count=count, last_seen_at=now))
                    else:
                        conn.execute(insert(alert_observations).values(condition_key=key[0], subject=key[1], count=count, last_seen_at=now))
                    if count < need:
                        continue
                last_open = conn.execute(select(func.max(alerts.c.opened_at)).where(alerts.c.condition_key == key[0], alerts.c.subject == key[1])).scalar()
                try:
                    with conn.begin_nested():
                        conn.execute(insert(alerts).values(condition_key=key[0], subject=key[1], severity=sig.severity, state="open", opened_at=now,
                                                           last_seen_at=now, reason_code=key[0]))
                except IntegrityError:
                    continue                                              # a concurrent evaluation opened it first
                if last_open is None or now - _aware(last_open) >= timedelta(hours=repeat_hours):
                    notify.append(sig)
            for key, row in live.items():
                if key not in wanted and key[0] in evaluated:
                    conn.execute(update(alerts).where(alerts.c.id == row.id).values(state="closed", closed_at=now))
            for key in seen:
                if key not in wanted and key[0] in evaluated:
                    conn.execute(delete(alert_observations).where(alert_observations.c.condition_key == key[0], alert_observations.c.subject == key[1]))
        return notify

    def list_alerts(self, closed_limit: int = 20) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            live = conn.execute(select(alerts).where(alerts.c.state != "closed").order_by(alerts.c.severity, alerts.c.id)).all()
            closed = conn.execute(select(alerts).where(alerts.c.state == "closed").order_by(alerts.c.closed_at.desc()).limit(closed_limit)).all()
        return [_alert(r) for r in (*live, *closed)]

    def acknowledge(self, alert_id: int, actor: str, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(UTC)
        with self.engine.begin() as conn:
            row = conn.execute(select(alerts).where(alerts.c.id == alert_id)).first()
            if row is None:
                raise OpsError("ops_item_unknown")
            if row.state == "open":
                conn.execute(update(alerts).where(alerts.c.id == alert_id).values(state="acknowledged", acknowledged_by=actor, acknowledged_at=now))
                append_audit(conn, actor, "alert.acknowledged", "alert", str(alert_id), after={"condition": row.condition_key}, now=now)
            row = conn.execute(select(alerts).where(alerts.c.id == alert_id)).first()
        return _alert(row)
