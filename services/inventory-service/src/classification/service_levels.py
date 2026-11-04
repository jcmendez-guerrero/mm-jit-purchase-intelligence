"""T068: service-level targets with defaults, per-product override and change history.

Defaults (research R8): clinical-critical 99 %, ABC A 97 %, B 95 %, C 90 %, sparse items (intermittent/lumpy) 85 %,
applied only when lower than the ABC value and never to clinical-critical products. A change is a new row with a
``valid_from``; a proposal uses the target valid on its own date, so history is kept and later edits never rewrite
earlier proposals.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from db.tables import service_level_config
from mmi_common.time import utc_now
from sqlalchemy import insert, select
from sqlalchemy.engine import Connection

DEFAULTS: dict[tuple[str, str], Decimal] = {
    ("critical", "*"): Decimal("0.99"),
    ("abc", "A"): Decimal("0.97"),
    ("abc", "B"): Decimal("0.95"),
    ("abc", "C"): Decimal("0.90"),
    ("sparse", "*"): Decimal("0.85"),
}
SPARSE_PATTERNS = ("intermittent", "lumpy")
SCOPES = ("abc", "critical", "sparse", "product")


class ServiceLevelError(Exception):
    pass


def set_target(conn: Connection, scope: str, key: str, target: Decimal, changed_by: str, valid_from: datetime | None = None) -> None:
    if scope not in SCOPES:
        raise ServiceLevelError(f"scope must be one of {SCOPES}")
    if scope == "abc" and key not in ("A", "B", "C"):
        raise ServiceLevelError("abc key must be A, B or C")
    if scope == "product" and not key.isdigit():
        raise ServiceLevelError("product key must be the product id")
    if scope in ("critical", "sparse") and key != "*":
        raise ServiceLevelError(f'{scope} uses key "*"')
    if not (Decimal("0.5") <= target < Decimal(1)):
        raise ServiceLevelError("target must be at least 0.50 and below 1.00")
    conn.execute(insert(service_level_config).values(scope=scope, key=key, target=target, valid_from=valid_from or utc_now(), changed_by=changed_by))


def _aware(dt: datetime) -> datetime:
    from datetime import UTC

    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _lookup(conn: Connection, scope: str, key: str, as_of: datetime) -> Decimal | None:
    rows = conn.execute(select(service_level_config.c.target, service_level_config.c.valid_from)
                        .where(service_level_config.c.scope == scope, service_level_config.c.key == key)
                        .order_by(service_level_config.c.valid_from.desc(), service_level_config.c.id.desc())).all()
    for r in rows:
        if _aware(r.valid_from) <= as_of:
            return Decimal(str(r.target))
    return None


def effective_target(conn: Connection, product_id: int, abc: str, pattern: str, critical: bool, as_of: datetime | None = None) -> Decimal:
    as_of = as_of or utc_now()
    override = _lookup(conn, "product", str(product_id), as_of)
    if override is not None:
        return override
    if critical:
        return _lookup(conn, "critical", "*", as_of) or DEFAULTS[("critical", "*")]
    base = _lookup(conn, "abc", abc, as_of) or DEFAULTS[("abc", abc)]
    if pattern in SPARSE_PATTERNS:
        base = min(base, _lookup(conn, "sparse", "*", as_of) or DEFAULTS[("sparse", "*")])
    return base


def history(conn: Connection, scope: str | None = None) -> list[dict[str, object]]:
    q = select(service_level_config).order_by(service_level_config.c.valid_from, service_level_config.c.id)
    if scope:
        q = q.where(service_level_config.c.scope == scope)
    return [{"scope": r.scope, "key": r.key, "target": str(r.target), "valid_from": _aware(r.valid_from).isoformat(), "changed_by": r.changed_by}
            for r in conn.execute(q).all()]
