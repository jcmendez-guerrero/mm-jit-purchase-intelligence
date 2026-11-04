"""T096: buyer edits with optimistic concurrency and constraint re-validation. Every change is recorded."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from audit.chain import append as audit
from costs.resolve import resolve_cost
from costs.rules import load_rules
from db.tables import proposal_lines, proposals, supplier_order_groups
from sqlalchemy import select, update
from sqlalchemy.engine import Connection
from terms.service import current_terms

from proposals.model import money, ticks

EDITABLE = ("draft", "submitted")


class ConcurrencyError(Exception):
    pass


class ProposalStateError(Exception):
    pass


class EditError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class EditResult:
    version: int
    warnings: list[str] = field(default_factory=list)


def _group_totals(conn: Connection, proposal_id: str, supplier_id: str, now: datetime) -> dict[str, Any]:
    rows = conn.execute(select(proposal_lines).where(proposal_lines.c.proposal_id == proposal_id, proposal_lines.c.supplier_id == supplier_id)).all()
    sub = sum((ticks(Decimal(str(r.line_total))) for r in rows), 0)
    qty = sum(r.qty for r in rows)
    t = current_terms(conn, supplier_id, now)
    if not rows:
        return {"subtotal": Decimal(0), "delivery_charge": Decimal(0), "total_cost": Decimal(0), "minimum_status": "met", "free_delivery": False}
    free = bool(t and t.free_delivery_threshold is not None and sub >= ticks(t.free_delivery_threshold))
    charge = 0 if free or not t or t.delivery_charge is None else ticks(t.delivery_charge)
    short = bool(t and ((t.min_order_value is not None and sub < ticks(t.min_order_value)) or (t.min_qty_for_delivery and qty < t.min_qty_for_delivery)))
    return {"subtotal": money(sub), "delivery_charge": money(charge), "total_cost": money(sub + charge),
            "minimum_status": "shortfall" if short else "met", "free_delivery": free}


def edit_line(conn: Connection, proposal_id: str, variant_id: int, expected_version: int, actor: str, qty: int | None = None,
              supplier_id: str | None = None, now: datetime | None = None) -> EditResult:
    now = now or datetime.now(UTC)
    p = conn.execute(select(proposals).where(proposals.c.id == proposal_id)).first()
    if p is None:
        raise ProposalStateError("unknown proposal")
    if p.status not in EDITABLE:
        raise ProposalStateError(f"a {p.status} proposal cannot be edited")
    if p.version != expected_version:
        raise ConcurrencyError(f"proposal is at version {p.version}, not {expected_version}")
    line = conn.execute(select(proposal_lines).where(proposal_lines.c.proposal_id == proposal_id, proposal_lines.c.variant_id == variant_id)).first()
    if line is None:
        raise EditError("unknown_line")
    new_supplier = supplier_id or line.supplier_id
    new_qty = line.qty if qty is None else qty
    if new_qty < 0:
        raise EditError("negative_quantity")
    warnings: list[str] = []
    unit = Decimal(str(line.unit_cost_with_recargo))
    if new_supplier != line.supplier_id or new_qty:
        res = resolve_cost(conn, line.product_id, new_supplier, load_rules(conn), variant_id, now)
        if res.cost is None:
            raise EditError("cost_required")
        if not res.usable:
            raise EditError("cost_blocked")
        warnings += [w for w in res.warnings if w != "cost_required"]
        unit = Decimal(str(res.cost.cost_with_recargo))
        pack, moq = res.cost.pack_size or 1, res.cost.min_order_qty or 0
        if new_qty and new_qty % pack:
            raise EditError("pack_multiple")
        if new_qty and new_qty < moq:
            raise EditError("min_order_qty")
    total = unit * new_qty
    constraints = [c for c in line.constraints_applied if c not in ("manual_quantity", "manual_supplier")]
    if qty is not None and qty != line.qty:
        constraints.append("manual_quantity")
    if new_supplier != line.supplier_id:
        constraints.append("manual_supplier")
    conn.execute(update(proposal_lines).where(proposal_lines.c.id == line.id).values(
        qty=new_qty, supplier_id=new_supplier, unit_cost_with_recargo=unit, line_total=total, manual_override=True, constraints_applied=constraints))
    for sid in {line.supplier_id, new_supplier}:
        g = _group_totals(conn, proposal_id, sid, now)
        exists = conn.execute(select(supplier_order_groups.c.supplier_id).where(supplier_order_groups.c.proposal_id == proposal_id,
                                                                                 supplier_order_groups.c.supplier_id == sid)).first()
        if exists:
            conn.execute(update(supplier_order_groups).where(supplier_order_groups.c.proposal_id == proposal_id, supplier_order_groups.c.supplier_id == sid)
                         .values(**g, shortfall_options=[]))
        elif g["subtotal"] > 0:
            from sqlalchemy import insert

            conn.execute(insert(supplier_order_groups).values(proposal_id=proposal_id, supplier_id=sid, **g, shortfall_options=[]))
        if g["minimum_status"] == "shortfall" and g["subtotal"] > 0:
            warnings.append("supplier_minimum_shortfall")
    if p.budget is not None:
        grand = sum((Decimal(str(r.total_cost)) for r in conn.execute(select(supplier_order_groups).where(supplier_order_groups.c.proposal_id == proposal_id)).all()), Decimal(0))
        if grand > Decimal(str(p.budget)):
            warnings.append("over_budget")
    status = "draft" if p.status == "submitted" else p.status          # any edit after submission resets approval eligibility
    new_version = p.version + 1
    conn.execute(update(proposals).where(proposals.c.id == proposal_id).values(version=new_version, last_edited_by=actor, status=status, updated_at=now, submitted_at=None))
    audit(conn, actor, "proposal.line_edited", "proposal", proposal_id,
          before={"variant_id": variant_id, "qty": line.qty, "supplier_id": line.supplier_id, "version": p.version},
          after={"variant_id": variant_id, "qty": new_qty, "supplier_id": new_supplier, "version": new_version, "status": status}, now=now)
    return EditResult(new_version, sorted(set(warnings)))

