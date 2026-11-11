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
from db.tables import censoring_rules, demand_exclusions, variants
from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import Connection

EARLIEST = date(2015, 1, 1)
MAX_AHEAD_DAYS = 548                       # about 18 months
RULE_LIMITS: Mapping[str, tuple[int, int, int]] = {"min_zero_stock_days": (1, 30, 1)}     # name -> (min, max, default)
REASONS = ("promotion", "closure", "supplier_outage", "bulk_sale", "other")                # pick list; the code is what the audit shows
MAX_DETAIL = 100


class RuleError(Exception):
    def __init__(self, message: str, code: str = "policy_out_of_range") -> None:
        super().__init__(message)
        self.code = code


class RuleConflict(Exception):
    code = "revision_conflict"

    def __init__(self, current: int) -> None:
        super().__init__(f"current revision is {current}")
        self.current_revision = current


def _check_range(from_day: date, to_day: date, today: date) -> None:
    if to_day < from_day:
        raise RuleError("exclusion ends before it starts")
    if from_day < EARLIEST or to_day > today + timedelta(days=MAX_AHEAD_DAYS):
        raise RuleError("exclusion outside the plausible date range", "import_date_out_of_range")


def add_exclusion(conn: Connection, variant_id: int | None, from_day: date, to_day: date, reason_code: str, actor: str, now: datetime | None = None,
                  detail: str | None = None, sku: str | None = None) -> int:
    now = now or datetime.now(UTC)
    _check_range(from_day, to_day, now.date())
    detail = (detail or "").strip() or None
    if reason_code not in REASONS or (detail is not None and len(detail) > MAX_DETAIL):
        raise RuleError("reason must come from the list", "exclusion_reason_invalid")
    if variant_id is not None and variant_id < 1:
        raise RuleError("variant")
    res = conn.execute(insert(demand_exclusions).values(variant_id=variant_id, from_day=from_day, to_day=to_day, reason=reason_code, reason_detail=detail, active=True,
                                                        revision=1, changed_by=actor))
    xid = int(res.inserted_primary_key[0])
    # the audit shows the pick-list code and the SKU, never the free-text detail or the ERP id
    audit(conn, actor, "demand_exclusion.added", "demand_exclusion", str(xid), after={"sku": sku, "from": from_day.isoformat(), "to": to_day.isoformat(), "reason_code": reason_code}, now=now)
    return xid


def exclusion_revision(conn: Connection, xid: int) -> int | None:
    r = conn.execute(select(demand_exclusions.c.revision).where(demand_exclusions.c.id == xid)).first()
    return None if r is None else int(r.revision)


def set_exclusion_active(conn: Connection, xid: int, active: bool, actor: str, now: datetime | None = None, expected_revision: int | None = None) -> None:
    row = conn.execute(select(demand_exclusions).where(demand_exclusions.c.id == xid)).first()
    if row is None:
        raise RuleError("unknown exclusion", "unknown_exclusion")
    if expected_revision is not None and expected_revision != row.revision:
        raise RuleConflict(int(row.revision))
    if bool(row.active) == active:
        return
    done = conn.execute(update(demand_exclusions).where(demand_exclusions.c.id == xid, demand_exclusions.c.revision == row.revision)       # a simultaneous toggle changes nothing
                        .values(active=active, revision=row.revision + 1, changed_by=actor))
    if done.rowcount == 0:
        raise RuleConflict(exclusion_revision(conn, xid) or int(row.revision))
    audit(conn, actor, "demand_exclusion.reactivated" if active else "demand_exclusion.deactivated", "demand_exclusion", str(xid), before={"active": bool(row.active)}, after={"active": active}, now=now)


def list_exclusions(conn: Connection, only_active: bool = False, with_detail: bool = False) -> list[dict[str, Any]]:
    q = select(demand_exclusions, variants.c.sku).select_from(demand_exclusions.outerjoin(variants, variants.c.external_id == demand_exclusions.c.variant_id)) \
        .order_by(demand_exclusions.c.from_day, demand_exclusions.c.id)
    if only_active:
        q = q.where(demand_exclusions.c.active)
    out = []
    for r in conn.execute(q).all():
        row = {"id": r.id, "sku": None if r.sku is None else str(r.sku).strip(), "from_day": r.from_day.isoformat(), "to_day": r.to_day.isoformat(), "reason_code": r.reason,
               "active": bool(r.active), "revision": r.revision, "changed_by": r.changed_by}
        if with_detail:
            row["detail"] = r.reason_detail
        out.append(row)
    return out


def rule_versions(conn: Connection) -> dict[str, int]:
    """What a forecast run records next to its parameters: the exclusion-set revision (every add or toggle moves it) and each censoring rule's revision."""
    out = {"exclusions": int(conn.execute(select(func.coalesce(func.sum(demand_exclusions.c.revision), 0))).scalar() or 0)}
    for name in RULE_LIMITS:
        out[f"censoring.{name}"] = censoring_revision(conn, name)
    return out


class Exclusions:
    """Lookup used by the rebuild: is (variant, day) excluded?"""

    def __init__(self, conn: Connection) -> None:
        self._rows = [(r.variant_id, r.from_day, r.to_day) for r in conn.execute(select(demand_exclusions).where(demand_exclusions.c.active)).all()]

    def __call__(self, variant_id: int, day: date) -> bool:
        return any((v is None or v == variant_id) and a <= day <= b for v, a, b in self._rows)

    def __bool__(self) -> bool:
        return bool(self._rows)


def censoring_revision(conn: Connection, rule: str) -> int:
    return int(conn.execute(select(func.max(censoring_rules.c.revision)).where(censoring_rules.c.rule == rule)).scalar() or 0)


def set_censoring_rule(conn: Connection, rule: str, value: int, actor: str, today: date | None = None, now: datetime | None = None,
                       expected_revision: int | None = None) -> int:
    if rule not in RULE_LIMITS:
        raise RuleError("unknown rule")
    lo, hi, _ = RULE_LIMITS[rule]
    if not (lo <= value <= hi):
        raise RuleError("rule value out of range")
    current = censoring_revision(conn, rule)
    if expected_revision is not None and expected_revision != current:
        raise RuleConflict(current)
    rev = current + 1
    conn.execute(insert(censoring_rules).values(rule=rule, value=value, valid_from=today or datetime.now(UTC).date(), revision=rev, changed_by=actor))
    audit(conn, actor, "censoring_rule.saved", "censoring_rule", rule, after={"value": value, "revision": rev}, now=now)
    return rev


def censoring_value(conn: Connection, rule: str) -> int:
    r = conn.execute(select(censoring_rules.c.value).where(censoring_rules.c.rule == rule).order_by(censoring_rules.c.revision.desc()).limit(1)).first()
    return int(r.value) if r else RULE_LIMITS[rule][2]


def list_rules(conn: Connection) -> list[dict[str, Any]]:
    return [{"rule": name, "value": censoring_value(conn, name), "min": lim[0], "max": lim[1], "default": lim[2], "revision": censoring_revision(conn, name)}
            for name, lim in RULE_LIMITS.items()]
