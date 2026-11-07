"""T080 / MMI 002: supplier order terms - effective-dated, append-only versions, validated, optimistic concurrency, audited.

A save never changes an existing row: it appends version n+1 with its own ``valid_from`` (and an optional explicit
``valid_to``). The version in force on a date is the latest one that has started and has not expired, so history is complete
and a future change can be planned. Nothing here talks to the ERP: lead time, schedules, pack multiples and discounts are
MMI-owned and stay local (ADR-019).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from audit.chain import append as audit
from db.tables import supplier_terms, suppliers
from proposals.model import Discount
from sqlalchemy import func, insert, select
from sqlalchemy.engine import Connection, Row

__all__ = ["Discount", "Terms", "TermsConflict", "TermsError", "current_terms", "current_version", "history", "save_terms", "validate", "versions"]

MAX_TIERS = 5
SOURCES = ("erp", "import", "manual")
_CUTOFF = re.compile(r"([01][0-9]|2[0-3]):[0-5][0-9]")


class TermsError(Exception):
    """A refusal with a stable code (see packages/contracts/errors/error_codes.json)."""

    code = "invalid_terms"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class TermsConflict(Exception):
    """The caller edited a stale version; ``current_version`` tells it which one is in force now."""

    code = "revision_conflict"

    def __init__(self, current_version: int) -> None:
        super().__init__(f"current version is {current_version}")
        self.current_version = current_version


@dataclass(frozen=True)
class Terms:
    min_order_value: Decimal | None = None
    min_qty_for_delivery: int | None = None
    free_delivery_threshold: Decimal | None = None
    delivery_charge: Decimal | None = None
    order_days: tuple[int, ...] = ()
    delivery_schedule: str | None = None
    lead_time_days: int | None = None
    order_cutoff_time: str | None = None
    delivery_weekdays: tuple[int, ...] = ()
    discounts: tuple[Discount, ...] = ()
    payment_terms_days: int | None = None
    preferred: bool = False
    reliability: int | None = None
    disabled: bool = False
    valid_to: datetime | None = field(default=None, compare=True)


def _aware(ts: datetime | None) -> datetime | None:
    return None if ts is None else (ts if ts.tzinfo else ts.replace(tzinfo=UTC))


def _dec(v: Any) -> Decimal | None:
    return None if v is None else Decimal(str(v))


def _bad(message: str, code: str = "terms_invalid_value") -> TermsError:
    return TermsError(message, code)


def check_weekdays(days: tuple[int, ...] | None) -> None:
    if days is not None and (len(set(days)) != len(days) or any(not isinstance(d, int) or not 1 <= d <= 7 for d in days)):
        raise _bad("weekdays must be unique ISO weekdays 1..7", "terms_invalid_weekday")


def check_int(value: int | None, name: str, lo: int, hi: int | None = None, quantity: bool = False) -> None:
    """``quantity`` marks counts of goods, where a negative number is a negative amount; other ranges are plain invalid values."""
    if value is None:
        return
    if quantity and value < 0:
        raise _bad(f"{name} must not be negative", "terms_negative_amount")
    if value < lo or (hi is not None and value > hi):
        raise _bad(f"{name} is out of range")


def check_money(value: Decimal | None, name: str) -> None:
    if value is not None and value < 0:
        raise _bad(f"{name} must not be negative", "terms_negative_amount")


def check_discounts(discounts: tuple[Discount, ...] | None) -> None:
    if not discounts:
        return
    if len(discounts) > MAX_TIERS:
        raise _bad("too many discount tiers")
    for d in discounts:
        if d.kind not in ("percent", "amount") or d.basis not in ("order_value", "order_units"):
            raise _bad("unknown discount kind or basis")
        check_money(d.threshold, "discount threshold")
        if d.kind == "amount":
            check_money(d.value, "discount amount")
        elif not Decimal(0) < d.value <= Decimal(100):
            raise _bad("a percentage discount must be above 0 and at most 100")


def validate(t: Terms) -> None:
    for name in ("min_order_value", "free_delivery_threshold", "delivery_charge"):
        check_money(getattr(t, name), name)
    check_int(t.min_qty_for_delivery, "min_qty_for_delivery", 0, quantity=True)
    check_weekdays(t.order_days)
    check_weekdays(t.delivery_weekdays)
    check_discounts(t.discounts)
    if t.free_delivery_threshold is not None and t.min_order_value is not None and t.free_delivery_threshold < t.min_order_value:
        raise _bad("free_delivery_threshold cannot be below min_order_value", "terms_threshold_below_minimum")
    check_int(t.lead_time_days, "lead_time_days", 0, 365)
    check_int(t.payment_terms_days, "payment_terms_days", 0, 365)
    check_int(t.reliability, "reliability", 0, 100)
    if t.order_cutoff_time is not None and not _CUTOFF.fullmatch(t.order_cutoff_time):
        raise _bad("order_cutoff_time must be HH:MM")
    if t.delivery_schedule is not None and len(t.delivery_schedule) > 200:
        raise _bad("delivery_schedule is too long")


def _discounts_json(ds: tuple[Discount, ...]) -> list[dict[str, str]]:
    return [{"kind": d.kind, "basis": d.basis, "threshold": str(d.threshold), "value": str(d.value)} for d in ds]


def _discounts_from(raw: Any) -> tuple[Discount, ...]:
    return tuple(Discount(x["kind"], x["basis"], Decimal(x["threshold"]), Decimal(x["value"])) for x in (raw or []))


def _dump(t: Terms) -> dict[str, Any]:
    return {"min_order_value": None if t.min_order_value is None else str(t.min_order_value), "min_qty_for_delivery": t.min_qty_for_delivery,
            "free_delivery_threshold": None if t.free_delivery_threshold is None else str(t.free_delivery_threshold),
            "delivery_charge": None if t.delivery_charge is None else str(t.delivery_charge), "order_days": list(t.order_days),
            "delivery_schedule": t.delivery_schedule, "lead_time_days": t.lead_time_days, "order_cutoff_time": t.order_cutoff_time,
            "delivery_weekdays": list(t.delivery_weekdays), "discounts": _discounts_json(t.discounts), "payment_terms_days": t.payment_terms_days,
            "preferred": t.preferred, "reliability": t.reliability, "disabled": t.disabled,
            "valid_to": None if t.valid_to is None else t.valid_to.isoformat()}


def row_to_terms(r: Row[Any]) -> Terms:
    return Terms(_dec(r.min_order_value), r.min_qty_for_delivery, _dec(r.free_delivery_threshold), _dec(r.delivery_charge), tuple(r.order_days or ()),
                 r.delivery_schedule, r.lead_time_days, r.order_cutoff_time, tuple(r.delivery_weekdays or ()), _discounts_from(r.discounts), r.payment_terms_days,
                 bool(r.preferred), r.reliability, bool(r.disabled), _aware(r.valid_to))


def versions(conn: Connection, supplier_id: str) -> list[Row[Any]]:
    return list(conn.execute(select(supplier_terms).where(supplier_terms.c.supplier_id == supplier_id)
                             .order_by(supplier_terms.c.valid_from, supplier_terms.c.id)).all())


def current_version(conn: Connection, supplier_id: str) -> int:
    """The latest saved version number (0 when none). This is the concurrency token the editor sends back."""
    return int(conn.execute(select(func.coalesce(func.max(supplier_terms.c.version), 0)).where(supplier_terms.c.supplier_id == supplier_id)).scalar() or 0)


def check_window(rows: list[Any], vfrom: datetime, vto: datetime | None) -> None:
    """A window must end after it starts, must not start inside another explicit window, and must not swallow a later version."""
    if vto is not None and vto <= vfrom:
        raise _bad("the validity window must end after it starts", "terms_window_overlap")
    for r in rows:
        rf, rt = _aware(r.valid_from), _aware(r.valid_to)
        if rf is None:
            continue
        if rt is not None and rf < vfrom < rt:
            raise _bad("the new version starts inside another version's validity window", "terms_window_overlap")
        if vto is not None and vfrom < rf < vto:
            raise _bad("the new validity window would cover a later version", "terms_window_overlap")


def in_force(rows: list[Any], as_of: datetime) -> Any | None:
    """The row valid on ``as_of``: the latest started version, unless its explicit window has ended."""
    chosen = None
    for r in rows:
        rf = _aware(r.valid_from)
        if rf is not None and rf <= as_of:
            chosen = r
    if chosen is None:
        return None
    rt = _aware(chosen.valid_to)
    return None if rt is not None and as_of >= rt else chosen


def current_terms(conn: Connection, supplier_id: str, as_of: datetime | None = None) -> Terms | None:
    row = in_force(versions(conn, supplier_id), as_of or datetime.now(UTC))
    return None if row is None else row_to_terms(row)


def current_row(conn: Connection, supplier_id: str, as_of: datetime | None = None) -> Row[Any] | None:
    return in_force(versions(conn, supplier_id), as_of or datetime.now(UTC))  # type: ignore[no-any-return]


def history(conn: Connection, supplier_id: str) -> list[dict[str, Any]]:
    return [{"version": r.version, "valid_from": _aware(r.valid_from), "valid_to": _aware(r.valid_to), "source": r.source, "reason": r.reason,
             "changed_by": r.changed_by, "terms": row_to_terms(r)} for r in sorted(versions(conn, supplier_id), key=lambda x: x.version)]


def save_terms(conn: Connection, supplier_id: str, terms: Terms, actor: str, now: datetime | None = None, *, valid_from: datetime | None = None,
               expected_version: int | None = None, source: str = "manual", reason: str | None = None) -> int:
    """Appends a new version and returns its number. Earlier versions are never modified."""
    validate(terms)
    if source not in SOURCES or (reason is not None and len(reason) > 500):
        raise _bad("invalid source or reason")
    if conn.execute(select(suppliers.c.id).where(suppliers.c.id == supplier_id)).first() is None:
        raise TermsError("unknown supplier")
    now = _aware(now) or datetime.now(UTC)
    current = current_version(conn, supplier_id)
    if expected_version is not None and expected_version != current:
        raise TermsConflict(current)
    vfrom = _aware(valid_from) or now
    existing = versions(conn, supplier_id)
    check_window(existing, vfrom, _aware(terms.valid_to))
    before_row = in_force(existing, vfrom)
    version = current + 1
    conn.execute(insert(supplier_terms).values(
        supplier_id=supplier_id, min_order_value=terms.min_order_value, min_qty_for_delivery=terms.min_qty_for_delivery,
        free_delivery_threshold=terms.free_delivery_threshold, delivery_charge=terms.delivery_charge, order_days=list(terms.order_days),
        delivery_schedule=terms.delivery_schedule, valid_from=vfrom, valid_to=_aware(terms.valid_to), changed_by=actor, version=version, revision=version,
        lead_time_days=terms.lead_time_days, order_cutoff_time=terms.order_cutoff_time, delivery_weekdays=list(terms.delivery_weekdays),
        discounts=_discounts_json(terms.discounts), payment_terms_days=terms.payment_terms_days, preferred=terms.preferred, reliability=terms.reliability,
        disabled=terms.disabled, source=source, reason=reason))
    audit(conn, actor, "terms.saved", "supplier_terms", supplier_id, before=None if before_row is None else _dump(row_to_terms(before_row)),
          after={**_dump(terms), "version": version, "valid_from": vfrom.isoformat(), "source": source}, now=now)
    return version
