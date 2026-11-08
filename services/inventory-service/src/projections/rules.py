"""T086: demand exclusions and censoring rules (FR-017).

Exclusions mark days whose sales say nothing about normal demand (a promotion, a supplier outage, a closure). Excluded days stay in
the data but are treated as not observable, so the forecast ignores them; deactivating an exclusion restores them. Rules are
edited here instead of being fixed constants: ``min_zero_stock_days`` is how many consecutive days at or below zero stock it takes
before those days are treated as hidden demand. Every change is audited and followed by a rebuild (the caller does that).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

from audit import append as audit
from db.tables import censoring_rules, demand_exclusions
from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import Connection

EARLIEST = date(2015, 1, 1)
MAX_AHEAD_DAYS = 548                       # about 18 months
RULE_LIMITS: Mapping[str, tuple[int, int, int]] = {"min_zero_stock_days": (1, 30, 1)}     # name -> (min, max, default)


class RuleError(Exception):
    def __init__(self, message: str, code: str = "policy_out_of_range") -> None:
        super().__init__(message)
        self.code = code


def _check_range(from_day: date, to_day: date, today: date) -> None:
    if to_day < from_day:
        raise RuleError("exclusion ends before it starts")
    if from_day < EARLIEST or to_day > today + timedelta(days=MAX_AHEAD_DAYS):
        raise RuleError("exclusion outside the plausible date range", "import_date_out_of_range")


def add_exclusion(conn: Connection, variant_id: int | None, from_day: date, to_day: date, reason: str, actor: str, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    _check_range(from_day, to_day, now.date())
    reason = (reason or "").strip()
    if len(reason) < 3 or len(reason) > 500:
        raise RuleError("a reason is required", "override_reason_required")
    if variant_id is not None and variant_id < 1:
        raise RuleError("variant")
    res = conn.execute(insert(demand_exclusions).values(variant_id=variant_id, from_day=from_day, to_day=to_day, reason=reason, active=True, revision=1, changed_by=actor))
    xid = int(res.inserted_primary_key[0])
    audit(conn, actor, "demand_exclusion.added", "demand_exclusion", str(xid), after={"variant_id": variant_id, "from": from_day.isoformat(), "to": to_day.isoformat(), "reason": reason}, now=now)
    return xid


def set_exclusion_active(conn: Connection, xid: int, active: bool, actor: str, now: datetime | None = None) -> None:
    row = conn.execute(select(demand_exclusions).where(demand_exclusions.c.id == xid)).first()
    if row is None:
        raise RuleError("unknown exclusion", "unknown_exclusion")
    if bool(row.active) == active:
        return
    conn.execute(update(demand_exclusions).where(demand_exclusions.c.id == xid).values(active=active, revision=row.revision + 1, changed_by=actor))
    audit(conn, actor, "demand_exclusion.reactivated" if active else "demand_exclusion.deactivated", "demand_exclusion", str(xid), before={"active": bool(row.active)}, after={"active": active}, now=now)


def list_exclusions(conn: Connection, only_active: bool = False) -> list[dict[str, Any]]:
    q = select(demand_exclusions).order_by(demand_exclusions.c.from_day, demand_exclusions.c.id)
    if only_active:
        q = q.where(demand_exclusions.c.active)
    return [{"id": r.id, "variant_id": r.variant_id, "from_day": r.from_day.isoformat(), "to_day": r.to_day.isoformat(), "reason": r.reason, "active": bool(r.active),
             "revision": r.revision, "changed_by": r.changed_by} for r in conn.execute(q).all()]


class Exclusions:
    """Lookup used by the rebuild: is (variant, day) excluded?"""

    def __init__(self, conn: Connection) -> None:
        self._rows = [(r.variant_id, r.from_day, r.to_day) for r in conn.execute(select(demand_exclusions).where(demand_exclusions.c.active)).all()]

    def __call__(self, variant_id: int, day: date) -> bool:
        return any((v is None or v == variant_id) and a <= day <= b for v, a, b in self._rows)

    def __bool__(self) -> bool:
        return bool(self._rows)


def set_censoring_rule(conn: Connection, rule: str, value: int, actor: str, today: date | None = None, now: datetime | None = None) -> int:
    if rule not in RULE_LIMITS:
        raise RuleError("unknown rule")
    lo, hi, _ = RULE_LIMITS[rule]
    if not (lo <= value <= hi):
        raise RuleError("rule value out of range")
    rev = int(conn.execute(select(func.max(censoring_rules.c.revision)).where(censoring_rules.c.rule == rule)).scalar() or 0) + 1
    conn.execute(insert(censoring_rules).values(rule=rule, value=value, valid_from=today or datetime.now(UTC).date(), revision=rev, changed_by=actor))
    audit(conn, actor, "censoring_rule.saved", "censoring_rule", rule, after={"value": value, "revision": rev}, now=now)
    return rev


def censoring_value(conn: Connection, rule: str) -> int:
    r = conn.execute(select(censoring_rules.c.value).where(censoring_rules.c.rule == rule).order_by(censoring_rules.c.revision.desc()).limit(1)).first()
    return int(r.value) if r else RULE_LIMITS[rule][2]


def list_rules(conn: Connection) -> list[dict[str, Any]]:
    return [{"rule": name, "value": censoring_value(conn, name), "min": lim[0], "max": lim[1], "default": lim[2]} for name, lim in RULE_LIMITS.items()]
