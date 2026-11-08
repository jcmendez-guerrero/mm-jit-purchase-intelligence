"""T075: immutable cost versions with source, verification time and supersession.

A cost is never edited. A change inserts a new version and points the previous one at it (``superseded_by``).
The only mutable fields are attestations: ``verified_at/by`` (buyer marks a cost verified) and the jump confirmation.
Last-paid cost is not a source: it can never be stored as, or shown as, a supplier offer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from audit.chain import append as audit
from db.tables import supplier_costs
from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection, Row

from costs.rules import CostRules, is_abnormal_jump, status

SOURCES = ("siweb_product_supplier", "csv_price_list", "manual", "inventory_export")


class CostError(Exception):
    code = "invalid_cost"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


@dataclass(frozen=True)
class NewCost:
    product_id: int
    supplier_id: str
    cost_with_recargo: Decimal
    source: str
    actor: str
    variant_id: int | None = None
    cost_net: Decimal | None = None
    recargo_rate: Decimal | None = None        # fraction (0.052)
    entered_includes_recargo: bool = True
    vat_rate_used: Decimal | None = None
    pack_size: int | None = None
    lead_time_days: int | None = None
    min_order_qty: int | None = None
    currency: str = "EUR"


def _scope(table: Any, product_id: int, supplier_id: str, variant_id: int | None) -> Any:
    cond = (table.c.product_id == product_id) & (table.c.supplier_id == supplier_id)
    return cond & (table.c.variant_id.is_(None) if variant_id is None else table.c.variant_id == variant_id)


def current(conn: Connection, product_id: int, supplier_id: str, variant_id: int | None = None) -> Row[Any] | None:
    return conn.execute(select(supplier_costs).where(_scope(supplier_costs, product_id, supplier_id, variant_id),
                                                     supplier_costs.c.superseded_by.is_(None))
                        .order_by(supplier_costs.c.version.desc()).limit(1)).first()


def history(conn: Connection, product_id: int, supplier_id: str, variant_id: int | None = None) -> list[Row[Any]]:
    return list(conn.execute(select(supplier_costs).where(_scope(supplier_costs, product_id, supplier_id, variant_id))
                             .order_by(supplier_costs.c.version)).all())


def _last_accepted(conn: Connection, product_id: int, supplier_id: str, variant_id: int | None) -> Row[Any] | None:
    """Latest version that is not an unconfirmed jump: that is the value a new cost is compared with."""
    for row in reversed(history(conn, product_id, supplier_id, variant_id)):
        if not (row.jump_flag and row.jump_confirmed_by is None):
            return row
    return None


def _aware(dt: datetime | None) -> datetime | None:
    return None if dt is None else (dt if dt.tzinfo else dt.replace(tzinfo=UTC))


def add_version(conn: Connection, new: NewCost, rules: CostRules, now: datetime | None = None, verified_at: datetime | None = None) -> Row[Any]:
    if new.source not in SOURCES:
        raise CostError(f"source must be one of {SOURCES}")
    if new.cost_with_recargo < 0:
        raise CostError("cost must not be negative")
    now = now or datetime.now(UTC)
    prior = current(conn, new.product_id, new.supplier_id, new.variant_id)
    accepted = _last_accepted(conn, new.product_id, new.supplier_id, new.variant_id)
    jump = is_abnormal_jump(Decimal(str(accepted.cost_with_recargo)) if accepted else None, new.cost_with_recargo, rules)
    version = (conn.execute(select(func.max(supplier_costs.c.version)).where(
        _scope(supplier_costs, new.product_id, new.supplier_id, new.variant_id))).scalar() or 0) + 1
    cid = str(uuid.uuid4())
    row = {
        "id": cid, "product_id": new.product_id, "supplier_id": new.supplier_id, "variant_id": new.variant_id, "version": version,
        "cost_net": new.cost_net, "recargo_rate": new.recargo_rate, "cost_with_recargo": new.cost_with_recargo,
        "entered_includes_recargo": new.entered_includes_recargo, "vat_rate_used": new.vat_rate_used, "currency": new.currency,
        "pack_size": new.pack_size, "lead_time_days": new.lead_time_days, "min_order_qty": new.min_order_qty, "source": new.source,
        "verified_at": verified_at or now, "verified_by": new.actor if new.source != "siweb_product_supplier" else None,
        "superseded_by": None, "created_at": now, "created_by": new.actor, "jump_flag": jump,
    }
    conn.execute(supplier_costs.insert().values(**row))
    if prior is not None:
        conn.execute(update(supplier_costs).where(supplier_costs.c.id == prior.id).values(superseded_by=cid))
    audit(conn, new.actor, "cost.version_added", "supplier_cost", cid,
          before={"id": prior.id, "cost_with_recargo": str(prior.cost_with_recargo)} if prior else None,
          after={"version": version, "cost_with_recargo": str(new.cost_with_recargo), "source": new.source, "jump": jump}, now=now)
    return conn.execute(select(supplier_costs).where(supplier_costs.c.id == cid)).one()


def get(conn: Connection, cost_id: str) -> Row[Any]:
    row = conn.execute(select(supplier_costs).where(supplier_costs.c.id == cost_id)).first()
    if row is None:
        raise CostError("cost not found", "cost_not_found")
    return row


def verify(conn: Connection, cost_id: str, actor: str, now: datetime | None = None) -> None:
    row = get(conn, cost_id)
    if row.superseded_by is not None:
        raise CostError("only the current version can be verified", "cost_not_current")
    now = now or datetime.now(UTC)
    conn.execute(update(supplier_costs).where(supplier_costs.c.id == cost_id).values(verified_at=now, verified_by=actor))
    audit(conn, actor, "cost.verified", "supplier_cost", cost_id, before={"verified_at": str(row.verified_at)}, after={"verified_at": now.isoformat()}, now=now)


def refresh_erp_verification(conn: Connection, cost_id: str, now: datetime) -> None:
    """The ERP import time counts as the verification time of an unchanged ERP cost (no new version)."""
    conn.execute(update(supplier_costs).where(supplier_costs.c.id == cost_id).values(verified_at=now))


def confirm_jump(conn: Connection, cost_id: str, actor: str, now: datetime | None = None) -> None:
    row = get(conn, cost_id)
    if not row.jump_flag:
        raise CostError("this cost has no abnormal jump to confirm", "no_jump_to_confirm")
    if row.jump_confirmed_by is not None:
        return
    now = now or datetime.now(UTC)
    conn.execute(update(supplier_costs).where(supplier_costs.c.id == cost_id).values(jump_confirmed_by=actor, jump_confirmed_at=now))
    audit(conn, actor, "cost.jump_confirmed", "supplier_cost", cost_id, after={"cost_with_recargo": str(row.cost_with_recargo)}, now=now)


def cost_status(row: Row[Any], rules: CostRules, now: datetime) -> str:
    return status(bool(row.jump_flag), row.jump_confirmed_by is not None, _aware(row.verified_at) or now, now, rules)  # type: ignore[arg-type]
