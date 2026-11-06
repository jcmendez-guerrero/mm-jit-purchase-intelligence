"""MMI 002: product-supplier overrides of the supplier terms (ADR-019). Same rules as supplier terms: append-only, effective-dated,
validated, optimistically locked, audited. Fields left as None inherit the supplier value; a product override can add a disable
but never re-enable a disabled supplier. Nothing here is written to the ERP."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from audit.chain import append as audit
from db.tables import product_supplier_terms, suppliers
from sqlalchemy import func, insert, select
from sqlalchemy.engine import Connection, Row

from terms.service import SOURCES, TermsConflict, TermsError, _aware, _bad, check_int, check_window, in_force

TermsOverrideConflict = TermsConflict


@dataclass(frozen=True)
class OverrideTerms:
    pack_multiple: int | None = None
    min_qty_units: int | None = None
    lead_time_days: int | None = None
    payment_terms_days: int | None = None
    preferred: bool | None = None
    reliability: int | None = None
    disabled: bool | None = None


FIELDS = tuple(OverrideTerms.__dataclass_fields__)


def validate_override(t: OverrideTerms) -> None:
    if t.pack_multiple is not None and t.pack_multiple < 1:
        raise _bad("pack_multiple must be at least 1")
    check_int(t.min_qty_units, "min_qty_units", 0, quantity=True)
    check_int(t.lead_time_days, "lead_time_days", 0, 365)
    check_int(t.payment_terms_days, "payment_terms_days", 0, 365)
    check_int(t.reliability, "reliability", 0, 100)


def _rows(conn: Connection, variant_id: int, supplier_id: str) -> list[Row[Any]]:
    return list(conn.execute(select(product_supplier_terms).where(product_supplier_terms.c.variant_id == variant_id, product_supplier_terms.c.supplier_id == supplier_id)
                             .order_by(product_supplier_terms.c.valid_from, product_supplier_terms.c.id)).all())


def _to_terms(r: Row[Any]) -> OverrideTerms:
    return OverrideTerms(**{f: getattr(r, f) for f in FIELDS})


def current_override_version(conn: Connection, variant_id: int, supplier_id: str) -> int:
    return int(conn.execute(select(func.coalesce(func.max(product_supplier_terms.c.version), 0)).where(
        product_supplier_terms.c.variant_id == variant_id, product_supplier_terms.c.supplier_id == supplier_id)).scalar() or 0)


def current_override_row(conn: Connection, variant_id: int, supplier_id: str, as_of: datetime | None = None) -> Row[Any] | None:
    return in_force(_rows(conn, variant_id, supplier_id), as_of or datetime.now(UTC))  # type: ignore[no-any-return]


def current_override(conn: Connection, variant_id: int, supplier_id: str, as_of: datetime | None = None) -> OverrideTerms | None:
    r = current_override_row(conn, variant_id, supplier_id, as_of)
    return None if r is None else _to_terms(r)


def override_history(conn: Connection, variant_id: int, supplier_id: str) -> list[dict[str, Any]]:
    return [{"version": r.version, "valid_from": _aware(r.valid_from), "valid_to": _aware(r.valid_to), "source": r.source, "reason": r.reason,
             "changed_by": r.changed_by, "terms": _to_terms(r)} for r in sorted(_rows(conn, variant_id, supplier_id), key=lambda x: x.version)]


def save_override(conn: Connection, variant_id: int, supplier_id: str, terms: OverrideTerms, actor: str, now: datetime | None = None, *,
                  valid_from: datetime | None = None, valid_to: datetime | None = None, expected_version: int | None = None,
                  source: str = "manual", reason: str | None = None) -> int:
    validate_override(terms)
    if source not in SOURCES or (reason is not None and len(reason) > 500):
        raise _bad("invalid source or reason")
    if conn.execute(select(suppliers.c.id).where(suppliers.c.id == supplier_id)).first() is None:
        raise TermsError("unknown supplier")
    now = _aware(now) or datetime.now(UTC)
    current = current_override_version(conn, variant_id, supplier_id)
    if expected_version is not None and expected_version != current:
        raise TermsConflict(current)
    vfrom = _aware(valid_from) or now
    rows = _rows(conn, variant_id, supplier_id)
    check_window(rows, vfrom, _aware(valid_to))
    before = in_force(rows, vfrom)
    version = current + 1
    conn.execute(insert(product_supplier_terms).values(
        variant_id=variant_id, supplier_id=supplier_id, version=version, valid_from=vfrom, valid_to=_aware(valid_to), source=source, reason=reason,
        changed_by=actor, revision=version, **{f: getattr(terms, f) for f in FIELDS}))
    audit(conn, actor, "terms.override_saved", "product_supplier", f"{variant_id}:{supplier_id}"[:60],
          before=None if before is None else {f: getattr(before, f) for f in FIELDS},
          after={**{f: getattr(terms, f) for f in FIELDS}, "version": version, "valid_from": vfrom.isoformat(), "source": source}, now=now)
    return version
