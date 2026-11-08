"""T048: product-supplier links, keyed by SKU for people (FR-015, FR-016, FR-040).

A link is a supplier offer: an immutable cost version with its source and verification time (the existing cost rules apply).
ERP ids are resolved from the SKU here and only inside the platform; nothing in this module sends anything to the ERP, so a
supplier without an ERP counterpart simply reports ``pending_link``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from audit.chain import append as audit
from costs.directory import SqlProductDirectory
from costs.recargo import RecargoTable, UnknownVatError, gross_from_net, net_from_gross
from costs.rules import CostRules
from costs.store import CostError, NewCost, add_version, current
from db.tables import erp_supplier_links, product_refs, supplier_costs, supplier_review_items, suppliers
from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection, Row

from suppliers.dedupe import name_key
from suppliers.export_costs import get_export_cost
from suppliers.service import SupplierError, add_review_item, get_supplier

LINK_SOURCES = ("manual", "inventory_export")


class LinkError(Exception):
    def __init__(self, code: str, message: str = "", field: str | None = None) -> None:
        super().__init__(message or code)
        self.code, self.field = code, field


@dataclass(frozen=True)
class LinkInput:
    cost: Decimal | None = None
    includes_recargo: bool = True
    source: str = "manual"
    pack_size: int | None = None
    min_qty: int | None = None


@dataclass
class LinkResult:
    cost: Row[Any]
    erp_link: str
    write_case: str | None
    warnings: list[str] = field(default_factory=list)


def resolve_sku(conn: Connection, sku: str, refresh: Callable[[], None] | None = None) -> Row[Any]:
    """The variant and product behind a SKU. ``refresh`` (optional) reloads the product references once when the SKU is not known yet."""
    key = (sku or "").strip().lower()
    if not key:
        raise LinkError("link_sku_unknown", field="sku")
    for attempt in (0, 1):
        row = conn.execute(select(product_refs).where(func.lower(product_refs.c.sku) == key).order_by(product_refs.c.variant_id).limit(1)).first()
        if row is not None:
            return row
        if attempt == 0 and refresh is not None:
            refresh()
        else:
            break
    raise LinkError("link_sku_unknown", field="sku")


def _erp_state(conn: Connection, supplier: Row[Any], product_id: int) -> tuple[str, str | None]:
    if supplier.external_contact_id is None or supplier.erp_link_state == "unverified":
        return "no_link", "pending_link"                       # nothing is sent to the ERP; the buyer creates the link there
    link = conn.execute(select(erp_supplier_links.c.has_cost).where(erp_supplier_links.c.product_id == product_id,
                                                                    erp_supplier_links.c.supplier_id == supplier.id)).first()
    if link is None:
        return "no_link", "pending_link"
    if not link.has_cost:
        return "link_without_cost", "missing_cost"
    return "link_with_cost", None


def put_link(conn: Connection, supplier_id: str, sku: str, data: LinkInput, actor: str, rules: CostRules, table: RecargoTable, *,
             now: datetime | None = None, refresh: Callable[[], None] | None = None) -> LinkResult:
    supplier = get_supplier(conn, supplier_id)
    if supplier.status != "active":
        raise LinkError("supplier_deactivated")
    if supplier.currency != "EUR":
        raise LinkError("link_currency_mismatch", field="currency")
    ref = resolve_sku(conn, sku, refresh)
    pid = int(ref.product_id)
    directory = SqlProductDirectory(conn)
    vat = directory.vat_for_product(pid)
    amount, includes, source = data.cost, data.includes_recargo, data.source
    if source not in LINK_SOURCES:
        raise LinkError("link_cost_invalid", field="source")
    if amount is None:
        export = get_export_cost(conn, ref.sku or sku)
        if export is None or export["export_cost"] is None:
            raise LinkError("link_cost_invalid", field="cost")
        amount, includes, source = Decimal(str(export["export_cost"])), False, "inventory_export"
        if vat is None and export["tax_rate"] is not None:
            vat = Decimal(str(export["tax_rate"]))
    if amount < 0:
        raise LinkError("link_cost_invalid", field="cost")
    net = rate = None
    gross = amount
    try:
        pct = table.rate_for(vat)
        rate = pct / 100
        if includes:
            net = net_from_gross(amount, pct)
        else:
            net, gross = amount, gross_from_net(amount, pct)
    except UnknownVatError as exc:
        if not includes:
            raise LinkError("vat_unknown", field="cost") from exc
    now = now or datetime.now(UTC)
    try:
        row = add_version(conn, NewCost(product_id=pid, supplier_id=supplier_id, cost_with_recargo=gross, source=source, actor=actor, cost_net=net,
                                        recargo_rate=rate, entered_includes_recargo=includes, vat_rate_used=vat, pack_size=data.pack_size,
                                        min_order_qty=data.min_qty, currency=supplier.currency), rules, now)
    except CostError as exc:
        raise LinkError("link_cost_invalid", str(exc), field="cost") from exc
    erp, case = _erp_state(conn, supplier, pid)
    audit(conn, actor, "supplier.link_saved", "supplier_link", f"{supplier_id}:{ref.sku}"[:60],
          after={"source": source, "version": int(row.version), "erp_link": erp}, now=now)
    return LinkResult(row, erp, case, ["abnormal_jump"] if row.jump_flag else [])


def remove_link(conn: Connection, supplier_id: str, sku: str, actor: str, *, now: datetime | None = None) -> None:
    ref = resolve_sku(conn, sku)
    cost = current(conn, int(ref.product_id), supplier_id, None)
    if cost is None:
        raise LinkError("link_not_found")
    conn.execute(update(supplier_costs).where(supplier_costs.c.id == cost.id).values(superseded_by="removed"))    # history stays, the offer ends
    audit(conn, actor, "supplier.link_removed", "supplier_link", f"{supplier_id}:{ref.sku}"[:60], before={"version": int(cost.version)}, now=now)


def list_links(conn: Connection, supplier_id: str) -> list[dict[str, Any]]:
    try:
        supplier = get_supplier(conn, supplier_id)
    except SupplierError:
        return []
    out = []
    for c in conn.execute(select(supplier_costs).where(supplier_costs.c.supplier_id == supplier_id, supplier_costs.c.superseded_by.is_(None))
                          .order_by(supplier_costs.c.product_id, supplier_costs.c.variant_id)).all():
        ref = conn.execute(select(product_refs).where(product_refs.c.product_id == c.product_id).order_by(product_refs.c.variant_id).limit(1)).first()
        erp, _ = _erp_state(conn, supplier, int(c.product_id))
        out.append({"sku": None if ref is None else ref.sku, "name": None if ref is None else ref.name, "product_id": int(c.product_id),
                    "cost": str(Decimal(str(c.cost_with_recargo)).quantize(Decimal("0.0001"))), "currency": c.currency, "cost_source": c.source,
                    "includes_recargo": bool(c.entered_includes_recargo), "pack_size": c.pack_size, "min_qty": c.min_order_qty,
                    "verified_at": (c.verified_at if c.verified_at.tzinfo else c.verified_at.replace(tzinfo=UTC)).isoformat(), "erp_link": erp})
    return out


def _review_once(conn: Connection, kind: str, supplier_id: str | None, detail: str, now: datetime) -> None:
    exists = conn.execute(select(supplier_review_items.c.id).where(supplier_review_items.c.kind == kind, supplier_review_items.c.detail == detail,
                                                                   supplier_review_items.c.status == "open")).first()
    if exists is None:
        add_review_item(conn, kind, supplier_id, detail, now)


def auto_link(conn: Connection, rows: list[dict[str, str]], actor: str, rules: CostRules, table: RecargoTable, *, now: datetime | None = None,
              refresh: Callable[[], None] | None = None) -> dict[str, int]:
    """FR-033: link a product to the supplier named in the inventory export only when exactly one active purchasing supplier has that name
    (ignoring case, accents and punctuation). Everything else is listed for review; nothing is guessed."""
    now = now or datetime.now(UTC)
    out = {"linked": 0, "existing": 0, "no_match": 0, "ambiguous": 0, "inactive": 0, "sku_unknown": 0, "no_cost": 0}
    by_key: dict[str, list[Row[Any]]] = {}
    for s in conn.execute(select(suppliers).where(suppliers.c.merged_into.is_(None))).all():
        by_key.setdefault(name_key(s.name), []).append(s)
    for r in rows:
        sku, name = (r.get("sku") or "").strip(), (r.get("supplier_name") or "").strip()
        if not sku or not name:
            continue
        candidates = by_key.get(name_key(name), [])
        usable = [s for s in candidates if s.status == "active" and s.classification != "non_purchasing"]
        detail = f"Producto {sku[:60]}"
        if len(usable) > 1:
            out["ambiguous"] += 1
            _review_once(conn, "link_ambiguous", None, detail, now)
            continue
        if not usable:
            if candidates:
                out["inactive"] += 1
                _review_once(conn, "link_inactive_supplier", candidates[0].id, detail, now)
            else:
                out["no_match"] += 1
                _review_once(conn, "link_no_match", None, detail, now)
            continue
        try:
            ref = resolve_sku(conn, sku, refresh)
            if current(conn, int(ref.product_id), usable[0].id, None) is not None:
                out["existing"] += 1
                continue
            put_link(conn, usable[0].id, sku, LinkInput(source="inventory_export"), actor, rules, table, now=now, refresh=refresh)
            out["linked"] += 1
        except LinkError as exc:
            if exc.code == "link_sku_unknown":
                out["sku_unknown"] += 1
            elif exc.code in ("link_cost_invalid", "vat_unknown"):
                out["no_cost"] += 1
            elif exc.code == "link_currency_mismatch":
                _review_once(conn, "currency_mismatch", usable[0].id, detail, now)
            else:
                raise
    return out
