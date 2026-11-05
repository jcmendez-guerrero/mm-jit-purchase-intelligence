"""T098: per-supplier order confirmation (actual quantities and costs) and the inbound projection event.

The buyer confirms the order placed manually with a supplier, after approval. Confirmed quantities replace proposal
quantities as the inbound quantities later proposals use. A confirmed cost that differs from the current one is stored as a
new buyer-confirmed cost version (the buyer's explicit confirmation also settles any jump flag) and, when it differs from the
ERP value, a cost write request is created for review (never sent automatically).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from approvals.workflow import is_approval_valid
from audit.chain import append as audit
from costs.rules import load_rules
from costs.store import NewCost, add_version, confirm_jump, current
from costs.writes import WriteRequestResult, request_write
from db.tables import inbound_order_lines, inbound_orders, proposal_lines, proposals, supplier_order_groups
from mmi_common.time import get_correlation_id, set_correlation_id
from proposals.edit import ProposalStateError
from proposals.publisher import BlobWriter, order_confirmed
from sqlalchemy import insert, select
from sqlalchemy.engine import Connection


class OrderError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ConfirmLine:
    variant_id: int
    qty: int
    cost_with_recargo: Decimal


@dataclass
class ConfirmResult:
    order_id: str
    cost_writes: list[WriteRequestResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def confirm_order(conn: Connection, proposal_id: str, supplier_id: str, lines: list[ConfirmLine], actor: str, writer: BlobWriter,
                  now: datetime | None = None, erp_purchase_ref: int | None = None, expected_delivery: date | None = None) -> ConfirmResult:
    now = now or datetime.now(UTC)
    p = conn.execute(select(proposals).where(proposals.c.id == proposal_id)).first()
    if p is None:
        raise ProposalStateError("unknown proposal")
    if p.status not in ("approved", "exported") or not is_approval_valid(conn, proposal_id):
        raise OrderError("proposal_not_approved")
    if conn.execute(select(inbound_orders.c.id).where(inbound_orders.c.proposal_id == proposal_id, inbound_orders.c.supplier_id == supplier_id)).first():
        raise OrderError("already_confirmed")
    proposed = {r.variant_id: r for r in conn.execute(select(proposal_lines).where(proposal_lines.c.proposal_id == proposal_id,
                                                                                   proposal_lines.c.supplier_id == supplier_id)).all()}
    if not proposed:
        raise OrderError("supplier_not_in_proposal")
    seen: set[int] = set()
    for ln in lines:
        if ln.variant_id not in proposed:
            raise OrderError(f"line_not_in_proposal:{ln.variant_id}")
        if ln.variant_id in seen:
            raise OrderError(f"duplicate_line:{ln.variant_id}")
        if ln.qty < 0 or ln.cost_with_recargo < 0:
            raise OrderError("negative_value")
        seen.add(ln.variant_id)
    rules = load_rules(conn)
    oid = str(uuid.uuid4())
    group = conn.execute(select(supplier_order_groups.c.expected_delivery_date).where(
        supplier_order_groups.c.proposal_id == proposal_id, supplier_order_groups.c.supplier_id == supplier_id)).first()
    conn.execute(insert(inbound_orders).values(id=oid, proposal_id=proposal_id, supplier_id=supplier_id, status="confirmed", confirmed_by=actor, confirmed_at=now,
                                               expected_delivery=expected_delivery or (group.expected_delivery_date if group else None), erp_purchase_ref=erp_purchase_ref))
    result = ConfirmResult(oid)
    event_lines: list[dict[str, Any]] = []
    for ln in lines:
        if ln.qty == 0:
            continue                                                     # not ordered: nothing inbound
        src = proposed[ln.variant_id]
        conn.execute(insert(inbound_order_lines).values(order_id=oid, variant_id=ln.variant_id, qty=ln.qty, confirmed_cost_with_recargo=ln.cost_with_recargo, received_qty=0))
        event_lines.append({"variant_id": ln.variant_id, "qty": ln.qty, "cost_with_recargo": str(ln.cost_with_recargo)})
        cur = current(conn, src.product_id, supplier_id, None)
        if cur is None or Decimal(str(cur.cost_with_recargo)) != ln.cost_with_recargo:
            new = add_version(conn, NewCost(product_id=src.product_id, supplier_id=supplier_id, cost_with_recargo=ln.cost_with_recargo, source="manual", actor=actor,
                                            pack_size=cur.pack_size if cur else None, lead_time_days=cur.lead_time_days if cur else None,
                                            min_order_qty=cur.min_order_qty if cur else None), rules, now)
            if new.jump_flag:
                confirm_jump(conn, new.id, actor, now)                   # the buyer agreed this price with the supplier
                result.warnings.append(f"cost_jump_confirmed:{ln.variant_id}")
            w = request_write(conn, new.id, "order_confirmed", actor, now)
            if w.status != "unchanged":
                result.cost_writes.append(w)
                result.warnings += [f"{x}:{ln.variant_id}" for x in w.warnings]
    audit(conn, actor, "order.confirmed", "inbound_order", oid, after={"proposal_id": proposal_id, "supplier_id": supplier_id, "lines": len(event_lines)}, now=now)
    order_confirmed(conn, writer, oid, proposal_id, supplier_id, event_lines, get_correlation_id() or set_correlation_id())
    return result


def open_inbound(conn: Connection, today: date) -> dict[int, list[tuple[int, int]]]:
    """Per variant: (remaining quantity, days until arrival) for orders not yet fully received. Feeds the next proposal."""
    out: dict[int, list[tuple[int, int]]] = {}
    for o in conn.execute(select(inbound_orders).where(inbound_orders.c.status.in_(("confirmed", "partially_received")))).all():
        eta = max((o.expected_delivery - today).days, 0) if o.expected_delivery else 0
        for ln in conn.execute(select(inbound_order_lines).where(inbound_order_lines.c.order_id == o.id)).all():
            remaining = ln.qty - ln.received_qty
            if remaining > 0:
                out.setdefault(ln.variant_id, []).append((remaining, eta))
    return out
