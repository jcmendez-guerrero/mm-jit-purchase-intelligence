"""T101: explicit supplier merge and review-item resolution (FR-018). Never automatic; always audited; history is kept."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from audit.chain import append as audit
from costs.rules import CostRules
from costs.store import NewCost, add_version, current
from db.tables import supplier_costs, supplier_review_items, suppliers
from sqlalchemy import select, update
from sqlalchemy.engine import Connection
from terms.service import current_terms, save_terms

from suppliers.service import SupplierError, deactivation_preview, flag_open_proposals, get_supplier


class MergeError(Exception):
    def __init__(self, code: str, message: str = "", open_lines: int = 0) -> None:
        super().__init__(message or code)
        self.code, self.open_lines = code, open_lines


def merge_suppliers(conn: Connection, merged_id: str, kept_id: str, actor: str, *, confirm: bool, now: datetime | None = None,
                    rules: CostRules | None = None) -> dict[str, Any]:
    if merged_id == kept_id:
        raise MergeError("merge_same_supplier")
    try:
        merged, kept = get_supplier(conn, merged_id), get_supplier(conn, kept_id)
    except SupplierError as exc:
        raise MergeError(exc.code) from exc
    if merged.status != "active" or kept.status != "active":
        raise MergeError("supplier_deactivated")
    if merged.currency != kept.currency:
        raise MergeError("merge_currency_mismatch")
    open_lines = deactivation_preview(conn, merged_id)["open_proposal_lines"]
    if open_lines and not confirm:
        raise MergeError("merge_open_lines", open_lines=open_lines)
    now = now or datetime.now(UTC)
    rules = rules or CostRules()
    moved = kept_existing = 0
    for c in conn.execute(select(supplier_costs).where(supplier_costs.c.supplier_id == merged_id, supplier_costs.c.superseded_by.is_(None))).all():
        if current(conn, int(c.product_id), kept_id, c.variant_id) is not None:
            kept_existing += 1
        else:
            add_version(conn, NewCost(product_id=int(c.product_id), supplier_id=kept_id, variant_id=c.variant_id, cost_with_recargo=c.cost_with_recargo, source=c.source,
                                      actor=actor, cost_net=c.cost_net, recargo_rate=c.recargo_rate, entered_includes_recargo=bool(c.entered_includes_recargo),
                                      vat_rate_used=c.vat_rate_used, pack_size=c.pack_size, lead_time_days=c.lead_time_days, min_order_qty=c.min_order_qty,
                                      currency=c.currency), rules, now)
            moved += 1
        conn.execute(update(supplier_costs).where(supplier_costs.c.id == c.id).values(superseded_by="merged"))
    terms = current_terms(conn, merged_id, now)
    copied = False
    if terms is not None and current_terms(conn, kept_id, now) is None:
        save_terms(conn, kept_id, terms, actor, now, source="manual", reason="Fusión de proveedores")
        copied = True
    flag_open_proposals(conn, merged_id, now)
    conn.execute(update(suppliers).where(suppliers.c.id == merged_id).values(status="deactivated", merged_into=kept_id, deactivated_by=actor, deactivated_at=now,
                                                                            version=int(merged.version) + 1, updated_by=actor, updated_at=now))
    out = {"moved": moved, "kept_existing": kept_existing, "terms_copied": copied}
    audit(conn, actor, "supplier.merged", "supplier", merged_id, before={"status": "active"}, after={"merged_into": kept_id, **out}, now=now)
    return out


def resolve_review_item(conn: Connection, item_id: str, decision: str, actor: str, *, merge_into: str | None = None, now: datetime | None = None) -> None:
    item = conn.execute(select(supplier_review_items).where(supplier_review_items.c.id == item_id)).first()
    if item is None:
        raise MergeError("review_item_not_found")
    if item.status != "open":
        raise MergeError("review_item_closed")
    if decision not in ("merge_into", "keep_both", "ignore"):
        raise MergeError("request_invalid")
    now = now or datetime.now(UTC)
    if decision == "merge_into":
        if not merge_into or item.supplier_id is None:
            raise MergeError("request_invalid")
        merge_suppliers(conn, item.supplier_id, merge_into, actor, confirm=True, now=now)
    status = "ignored" if decision == "ignore" else "resolved"
    conn.execute(update(supplier_review_items).where(supplier_review_items.c.id == item_id).values(status=status, resolved_by=actor, resolved_at=now))
    audit(conn, actor, "supplier.review_resolved", "supplier_review", item_id, after={"decision": decision}, now=now)
