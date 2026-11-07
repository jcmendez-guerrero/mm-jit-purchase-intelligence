"""T089: per-variant stocking settings. ``always_stocked`` keeps a floor in stock and checks monthly; ``on_request`` is never proposed."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from audit.chain import append as audit
from db.tables import stocking_settings
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from policies.service import PolicyConflict, PolicyError

MODES = ("standard", "always_stocked", "on_request")
MAX_FLOOR = 10_000


def get_stocking(conn: Connection, variant_id: int) -> dict[str, Any]:
    r = conn.execute(select(stocking_settings).where(stocking_settings.c.variant_id == variant_id)).first()
    if r is None:
        return {"variant_id": variant_id, "stocking_mode": "standard", "min_floor_units": 0, "revision": 0}
    return {"variant_id": variant_id, "stocking_mode": r.stocking_mode, "min_floor_units": r.min_floor_units, "revision": r.revision,
            "changed_by": r.changed_by, "updated_at": r.updated_at.isoformat()}


def save_stocking(conn: Connection, variant_id: int, mode: str, floor: int, actor: str, *, expected_revision: int | None = None, now: datetime | None = None) -> int:
    if variant_id < 1 or mode not in MODES or not (0 <= floor <= MAX_FLOOR):
        raise PolicyError("stocking out of range")
    if mode == "always_stocked" and floor < 1:
        raise PolicyError("always stocked needs a floor of at least 1", "stocking_floor_required")
    now = now or datetime.now(UTC)
    cur = get_stocking(conn, variant_id)
    if expected_revision is not None and expected_revision != cur["revision"]:
        raise PolicyConflict(int(cur["revision"]))
    rev = int(cur["revision"]) + 1
    if cur["revision"] == 0:
        conn.execute(insert(stocking_settings).values(variant_id=variant_id, stocking_mode=mode, min_floor_units=floor, valid_from=now.date(), revision=rev, changed_by=actor, updated_at=now))
    else:
        conn.execute(update(stocking_settings).where(stocking_settings.c.variant_id == variant_id).values(
            stocking_mode=mode, min_floor_units=floor, valid_from=now.date(), revision=rev, changed_by=actor, updated_at=now))
    audit(conn, actor, "stocking.saved", "stocking", str(variant_id), before={"mode": cur["stocking_mode"], "floor": cur["min_floor_units"]}, after={"mode": mode, "floor": floor, "revision": rev}, now=now)
    return rev


def stocking_map(conn: Connection) -> dict[int, tuple[str, int]]:
    return {r.variant_id: (r.stocking_mode, r.min_floor_units) for r in conn.execute(select(stocking_settings)).all() if r.stocking_mode != "standard"}


MONTHLY_CHECK_DAYS = 30


def last_order_dates(conn: Connection) -> dict[int, Any]:
    """Date of the newest confirmed order line per variant: the always-stocked monthly check looks at it."""
    from db.tables import inbound_order_lines, inbound_orders
    from sqlalchemy import func

    rows = conn.execute(select(inbound_order_lines.c.variant_id, func.max(inbound_orders.c.confirmed_at).label("at")).join(
        inbound_orders, inbound_orders.c.id == inbound_order_lines.c.order_id).group_by(inbound_order_lines.c.variant_id)).all()
    return {r.variant_id: (r.at.date() if hasattr(r.at, "date") else r.at) for r in rows if r.at is not None}
