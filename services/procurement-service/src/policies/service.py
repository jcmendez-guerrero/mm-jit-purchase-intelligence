"""T084: purchase policy sets (service level, safety stock, min/max, cadence) and budget caps.

Append-only and effective-dated like supplier terms: a save adds a row with a ``valid_from`` of today or later and the next
``revision`` for its (scope, key); earlier runs keep resolving the row that was in force on their own date. A save must name the
revision it edited, so two people cannot silently overwrite each other. The most specific scope wins per field:
product (variant) > segment (A/B/C/critical/sparse) > global.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from audit.chain import append as audit
from db.tables import budget_caps, policy_sets, product_refs
from sqlalchemy import func, insert, select
from sqlalchemy.engine import Connection, Row
from sqlalchemy.exc import IntegrityError

SCOPES = ("global", "segment", "product")
SEGMENTS = ("A", "B", "C", "critical", "sparse")
FIELDS = ("service_level", "safety_stock_units", "min_units", "max_units", "replenishment_cadence_days")
MIN_LEVEL, MAX_LEVEL = Decimal("0.5"), Decimal("0.9999")


class PolicyError(Exception):
    code = "policy_out_of_range"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class PolicyConflict(Exception):
    code = "revision_conflict"

    def __init__(self, current_revision: int) -> None:
        super().__init__(f"current revision is {current_revision}")
        self.current_revision = current_revision


@dataclass(frozen=True)
class PolicyValues:
    service_level: Decimal | None = None
    safety_stock_units: int | None = None
    min_units: int | None = None
    max_units: int | None = None
    replenishment_cadence_days: int | None = None


def validate_key(scope: str, key: str) -> None:
    if scope not in SCOPES:
        raise PolicyError("scope")
    if scope == "global" and key != "*":
        raise PolicyError("global uses key *")
    if scope == "segment" and key not in SEGMENTS:
        raise PolicyError("segment key")
    if scope == "product" and not (key.isdigit() and int(key) >= 1):
        raise PolicyError("product key is the variant id")


def validate_values(v: PolicyValues) -> None:
    if isinstance(v.service_level, float):
        raise TypeError("floats are not allowed for money or levels")
    if v.service_level is not None and not (MIN_LEVEL <= v.service_level <= MAX_LEVEL):
        raise PolicyError("service level must be between 50 % and 99.99 %")
    for name in ("safety_stock_units", "min_units", "max_units"):
        n = getattr(v, name)
        if n is not None and not (0 <= n <= 1_000_000):
            raise PolicyError(f"{name} out of range")
    if v.min_units is not None and v.max_units is not None and v.max_units < v.min_units:
        raise PolicyError("max below min")
    c = v.replenishment_cadence_days
    if c is not None and not (1 <= c <= 90):
        raise PolicyError("cadence out of range")
    if all(getattr(v, f) is None for f in FIELDS):
        raise PolicyError("nothing to set")


def _current_revision(conn: Connection, scope: str, key: str) -> int:
    return int(conn.execute(select(func.max(policy_sets.c.revision)).where(policy_sets.c.scope == scope, policy_sets.c.key == key)).scalar() or 0)


def _insert_or_conflict(conn: Connection, stmt: Any, current: Callable[[], int]) -> None:
    """A second save that read the same revision only fails at the database (unique revision): that is a conflict, not a server error, and stores nothing."""
    try:
        with conn.begin_nested():
            conn.execute(stmt)
    except IntegrityError as exc:
        raise PolicyConflict(current()) from exc


def _snapshot(row: Row[Any] | None) -> dict[str, Any] | None:
    """The previous values, for the audit trail: what a change replaced."""
    if row is None:
        return None
    return {"revision": int(row.revision), "valid_from": row.valid_from.isoformat(), **{f: (None if getattr(row, f) is None else str(getattr(row, f))) for f in FIELDS}}


def _latest_policy(conn: Connection, scope: str, key: str) -> Row[Any] | None:
    return conn.execute(select(policy_sets).where(policy_sets.c.scope == scope, policy_sets.c.key == key).order_by(policy_sets.c.revision.desc()).limit(1)).first()


def save_policy(conn: Connection, scope: str, key: str, values: PolicyValues, actor: str, *, valid_from: date | None = None, expected_revision: int | None = None,
                today: date | None = None) -> int:
    """Returns the new revision. ``expected_revision`` must equal the current one (0 for the first save)."""
    validate_key(scope, key)
    validate_values(values)
    today = today or datetime.now(UTC).date()
    start = valid_from or today
    if start < today:
        raise PolicyError("a policy cannot start in the past: earlier runs keep the policy they used", "policy_out_of_range")
    current = _current_revision(conn, scope, key)
    if expected_revision is not None and expected_revision != current:
        raise PolicyConflict(current)
    latest = conn.execute(select(func.max(policy_sets.c.valid_from)).where(policy_sets.c.scope == scope, policy_sets.c.key == key)).scalar()
    if latest is not None and start < latest:
        # an earlier date than a scheduled revision would be silently overridden when that revision takes effect
        raise PolicyError("a revision is already scheduled after this date", "policy_overlap")
    rev = current + 1
    pid = str(uuid.uuid4())
    previous = _snapshot(_latest_policy(conn, scope, key))
    _insert_or_conflict(conn, insert(policy_sets).values(id=pid, scope=scope, key=key, service_level=values.service_level, safety_stock_units=values.safety_stock_units,
                                                         min_units=values.min_units, max_units=values.max_units, replenishment_cadence_days=values.replenishment_cadence_days,
                                                         valid_from=start, revision=rev, changed_by=actor), lambda: _current_revision(conn, scope, key))
    audit(conn, actor, "policy.saved", "policy_set", pid, before=previous, after={"scope": scope, "key": key, "revision": rev, "valid_from": start.isoformat(),
                                                                                  **{f: (None if getattr(values, f) is None else str(getattr(values, f))) for f in FIELDS}})
    return rev


def clear_policy(conn: Connection, scope: str, key: str, actor: str, *, expected_revision: int | None = None, today: date | None = None) -> int:
    """Removes an override by writing a new revision with every field empty: the lower scope or the default applies again and no past revision is touched."""
    validate_key(scope, key)
    today = today or datetime.now(UTC).date()
    current = _current_revision(conn, scope, key)
    if current == 0:
        raise PolicyError("nothing to clear", "policy_out_of_range")
    if expected_revision is not None and expected_revision != current:
        raise PolicyConflict(current)
    latest = conn.execute(select(func.max(policy_sets.c.valid_from)).where(policy_sets.c.scope == scope, policy_sets.c.key == key)).scalar()
    if latest is not None and today < latest:
        raise PolicyError("a revision is already scheduled after this date", "policy_overlap")
    rev, pid = current + 1, str(uuid.uuid4())
    previous = _snapshot(_latest_policy(conn, scope, key))
    _insert_or_conflict(conn, insert(policy_sets).values(id=pid, scope=scope, key=key, service_level=None, safety_stock_units=None, min_units=None, max_units=None,
                                                         replenishment_cadence_days=None, valid_from=today, revision=rev, changed_by=actor),
                        lambda: _current_revision(conn, scope, key))
    audit(conn, actor, "policy.cleared", "policy_set", pid, before=previous, after={"scope": scope, "key": key, "revision": rev, "valid_from": today.isoformat()})
    return rev


def policy_row(conn: Connection, scope: str, key: str, as_of: date) -> Row[Any] | None:
    return conn.execute(select(policy_sets).where(policy_sets.c.scope == scope, policy_sets.c.key == key, policy_sets.c.valid_from <= as_of)
                        .order_by(policy_sets.c.valid_from.desc(), policy_sets.c.revision.desc()).limit(1)).first()


@dataclass(frozen=True)
class EffectivePolicy:
    values: PolicyValues
    sources: dict[str, str]            # field -> scope:key that supplied it
    revisions: dict[str, int]          # scope:key -> revision used (recorded on the proposal, FR-026)


def resolve_policy(conn: Connection, variant_id: int, segments: tuple[str, ...], as_of: date) -> EffectivePolicy:
    """Most specific wins per field: product, then each segment (given in priority order), then global."""
    chain = [("product", str(variant_id)), *[("segment", s) for s in segments], ("global", "*")]
    out: dict[str, Any] = {}
    sources: dict[str, str] = {}
    revisions: dict[str, int] = {}
    for scope, key in chain:
        row = policy_row(conn, scope, key, as_of)
        if row is None:
            continue
        for f in FIELDS:
            val = getattr(row, f)
            if val is not None and f not in out:
                out[f] = Decimal(str(val)) if f == "service_level" else int(val)
                sources[f] = f"{scope}:{key}"
                revisions[f"{scope}:{key}"] = int(row.revision)
    return EffectivePolicy(PolicyValues(**out), sources, revisions)


def effective_view(conn: Connection, variant_id: int, segments: tuple[str, ...], as_of: date) -> dict[str, dict[str, Any]]:
    """Per rule: the value in force, where it comes from (product, segment, global or default) and its revision. Nothing in force means the computed default applies."""
    chain = [("product", str(variant_id)), *[("segment", s) for s in segments], ("global", "*")]
    out: dict[str, dict[str, Any]] = {f: {"value": None, "source": "default", "key": None, "revision": None, "valid_from": None} for f in FIELDS}
    for scope, key in chain:
        row = policy_row(conn, scope, key, as_of)
        if row is None:
            continue
        for f in FIELDS:
            val = getattr(row, f)
            if val is not None and out[f]["source"] == "default":
                out[f] = {"value": str(val), "source": scope, "key": key, "revision": int(row.revision), "valid_from": row.valid_from.isoformat()}
    return out


def _sku_key(sku: str | None) -> str:
    return (sku or "").strip().lower()


def variant_for_sku(conn: Connection, sku: str) -> int:
    """People use SKUs; the variant id is internal. A SKU that matches no product, or more than one (also by case or spacing), is refused."""
    key = _sku_key(sku)
    if not key:
        raise PolicyError("sku required", "sku_unknown")
    ids = sorted({int(r.variant_id) for r in conn.execute(select(product_refs.c.variant_id).where(func.lower(func.trim(product_refs.c.sku)) == key)).all()})
    if not ids:
        raise PolicyError("sku unknown", "sku_unknown")
    if len(ids) > 1:
        raise PolicyError("sku matches more than one product", "sku_ambiguous")
    return ids[0]


def variant_known(conn: Connection, variant_id: int) -> bool:
    return conn.execute(select(product_refs.c.variant_id).where(product_refs.c.variant_id == variant_id)).first() is not None


def sku_for_variant(conn: Connection, variant_id: int) -> str | None:
    r = conn.execute(select(product_refs.c.sku).where(product_refs.c.variant_id == variant_id)).first()
    return None if r is None or r.sku is None else str(r.sku).strip()


def history(conn: Connection, scope: str, key: str) -> list[dict[str, Any]]:
    rows = conn.execute(select(policy_sets).where(policy_sets.c.scope == scope, policy_sets.c.key == key).order_by(policy_sets.c.revision)).all()
    return [{"revision": r.revision, "valid_from": r.valid_from.isoformat(), "changed_by": r.changed_by,
             **{f: (None if getattr(r, f) is None else str(getattr(r, f))) for f in FIELDS}} for r in rows]


def listing(conn: Connection, as_of: date) -> list[dict[str, Any]]:
    keys = conn.execute(select(policy_sets.c.scope, policy_sets.c.key).distinct()).all()
    out = []
    for scope, key in sorted((k.scope, k.key) for k in keys):
        r = policy_row(conn, scope, key, as_of)
        cur = _current_revision(conn, scope, key)
        out.append({"scope": scope, "key": key, "revision": cur, "in_force": None if r is None else {
            "valid_from": r.valid_from.isoformat(), **{f: (None if getattr(r, f) is None else str(getattr(r, f))) for f in FIELDS}}})
    return out


# ---- budget caps -------------------------------------------------------------------------------------------------------------------

CAP_PERIODS = ("week", "month")
CAP_SCOPES = ("global", "supplier", "category")


def _cap_filter(period: str, scope: str, scope_key: str | None) -> Any:
    return (budget_caps.c.period == period, budget_caps.c.scope == scope,
            budget_caps.c.scope_key.is_(None) if scope_key is None else budget_caps.c.scope_key == scope_key)


def budget_cap_revision(conn: Connection, period: str, scope: str, scope_key: str | None) -> int:
    return int(conn.execute(select(func.max(budget_caps.c.revision)).where(*_cap_filter(period, scope, scope_key))).scalar() or 0)


def save_budget_cap(conn: Connection, period: str, scope: str, scope_key: str | None, amount: Decimal, actor: str, *, valid_from: date | None = None,
                    today: date | None = None, expected_revision: int | None = None) -> str:
    if isinstance(amount, float):
        raise TypeError("floats are not allowed for money")
    if period not in CAP_PERIODS or scope not in CAP_SCOPES or amount < 0 or amount > Decimal("100000000"):
        raise PolicyError("budget cap out of range")
    if (scope == "global") != (scope_key is None):
        raise PolicyError("scope key")
    today = today or datetime.now(UTC).date()
    start = valid_from or today
    if start < today:
        raise PolicyError("a budget cap cannot start in the past")
    prev = budget_cap_revision(conn, period, scope, scope_key)
    if expected_revision is not None and expected_revision != prev:
        raise PolicyConflict(prev)
    latest = conn.execute(select(func.max(budget_caps.c.valid_from)).where(*_cap_filter(period, scope, scope_key))).scalar()
    if latest is not None and start < latest:
        raise PolicyError("a budget cap is already scheduled after this date", "policy_overlap")
    cid = str(uuid.uuid4())
    last = conn.execute(select(budget_caps).where(*_cap_filter(period, scope, scope_key)).order_by(budget_caps.c.revision.desc()).limit(1)).first()
    before = None if last is None else {"revision": int(last.revision), "amount": str(last.amount), "valid_from": last.valid_from.isoformat()}
    _insert_or_conflict(conn, insert(budget_caps).values(id=cid, period=period, scope=scope, scope_key=scope_key, amount=amount, valid_from=start, revision=prev + 1, changed_by=actor),
                        lambda: budget_cap_revision(conn, period, scope, scope_key))
    audit(conn, actor, "budget_cap.saved", "budget_cap", cid, before=before, after={"period": period, "scope": scope, "scope_key": scope_key, "amount": str(amount), "valid_from": start.isoformat(),
                                                                       "revision": prev + 1})
    return cid


def budget_versions(conn: Connection, as_of: date) -> dict[str, int]:
    """The global weekly and monthly caps in force and their revisions, recorded next to the policy revisions a proposal used (SC-006)."""
    out: dict[str, int] = {}
    for period in CAP_PERIODS:
        row = conn.execute(select(budget_caps).where(budget_caps.c.period == period, budget_caps.c.scope == "global", budget_caps.c.valid_from <= as_of)
                           .order_by(budget_caps.c.valid_from.desc(), budget_caps.c.revision.desc()).limit(1)).first()
        if row is not None:
            out[f"budget:{period}:global:*"] = int(row.revision)
    return out


WEEKS_PER_MONTH = Decimal("4.33")


def _weekly_equivalents(conn: Connection, as_of: date, scope: str, scope_key: str | None) -> list[tuple[Decimal, str]]:
    """The weekly and monthly caps in force for one scope as weekly amounts (a monthly cap is split over 4.33 weeks), each with the period that supplied it."""
    out: list[tuple[Decimal, str]] = []
    for period in CAP_PERIODS:
        row = conn.execute(select(budget_caps).where(*_cap_filter(period, scope, scope_key), budget_caps.c.valid_from <= as_of)
                           .order_by(budget_caps.c.valid_from.desc(), budget_caps.c.revision.desc()).limit(1)).first()
        if row is not None:
            amount = Decimal(str(row.amount))
            out.append((amount if period == "week" else (amount / WEEKS_PER_MONTH).quantize(Decimal("0.01")), period))
    return out


def effective_weekly_budget_with_source(conn: Connection, as_of: date) -> tuple[Decimal | None, str | None]:
    """The tighter of the global weekly and monthly caps, and which one it is ("global_week" or "global_month")."""
    caps = _weekly_equivalents(conn, as_of, "global", None)
    if not caps:
        return None, None
    amount, period = min(caps)
    return amount, f"global_{period}"


def effective_weekly_budget(conn: Connection, as_of: date) -> Decimal | None:
    """The global weekly cap in force (a monthly cap is split over 4.33 weeks); None when none is set."""
    return effective_weekly_budget_with_source(conn, as_of)[0]


def supplier_weekly_budgets(conn: Connection, as_of: date) -> dict[str, Decimal]:
    """supplier_id -> the tighter of that supplier's weekly and monthly caps in force; suppliers without a cap are absent."""
    keys = [r.scope_key for r in conn.execute(select(budget_caps.c.scope_key).where(budget_caps.c.scope == "supplier").distinct()).all() if r.scope_key]
    out: dict[str, Decimal] = {}
    for key in keys:
        caps = _weekly_equivalents(conn, as_of, "supplier", key)
        if caps:
            out[str(key)] = min(caps)[0]
    return out
