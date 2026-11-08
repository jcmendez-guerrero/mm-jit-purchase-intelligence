"""T076: ingest supplier-cost rows read from the ERP.

The ERP cost already includes recargo. ``supplier_cif`` is not accepted at all. A row with no cost (null or zero) is
recorded as an ERP link without a cost: that is the case in which the buyer's entry may later be written back (FR-040a).
The import time is the verification time. An unchanged cost refreshes that time without creating a version.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from db.tables import erp_supplier_links, suppliers
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection
from suppliers.dedupe import name_key

from costs.directory import SqlProductDirectory
from costs.recargo import RecargoTable, UnknownVatError, net_from_gross
from costs.rules import CostRules
from costs.store import NewCost, add_version, current, refresh_erp_verification
from costs.writes import relink_pending

SOURCE = "siweb_product_supplier"
ACTOR = "siweb-import"


@dataclass
class ImportSummary:
    new_versions: int = 0
    unchanged: int = 0
    no_cost: int = 0
    jumps: int = 0


def get_or_create_supplier(conn: Connection, contact_id: int, name: str | None) -> str:
    row = conn.execute(select(suppliers.c.id, suppliers.c.name).where(suppliers.c.external_contact_id == contact_id)).first()
    if row:
        if name and row.name != name:
            conn.execute(update(suppliers).where(suppliers.c.id == row.id).values(name=name, name_key=name_key(name)))
        return str(row.id)
    sid = str(uuid.uuid4())
    shown = name or f"Proveedor {contact_id}"
    conn.execute(insert(suppliers).values(id=sid, external_contact_id=contact_id, name=shown, name_key=name_key(shown), origin="erp", erp_link_state="linked",
                                          classification="purchasing"))
    return sid


def import_supplier_rows(conn: Connection, rows: Iterable[dict[str, Any]], rules: CostRules, table: RecargoTable, now: datetime | None = None) -> ImportSummary:
    """``rows`` use the connector's normalised shape: product_id, contact_id, supplier_name, purchase_cost (EUR, Decimal)."""
    now = now or datetime.now(UTC)
    directory = SqlProductDirectory(conn)
    out = ImportSummary()
    for r in rows:
        sid = get_or_create_supplier(conn, int(r["contact_id"]), r.get("supplier_name"))
        pid = int(r["product_id"])
        cost: Decimal | None = r.get("purchase_cost")
        has_cost = cost is not None and cost > 0
        if cost is None:
            cost = Decimal(0)
        link = conn.execute(select(erp_supplier_links.c.product_id).where(erp_supplier_links.c.product_id == pid, erp_supplier_links.c.supplier_id == sid)).first()
        if link is None:
            conn.execute(insert(erp_supplier_links).values(product_id=pid, supplier_id=sid, has_cost=has_cost, last_seen_at=now))
            relink_pending(conn, pid, sid, now)     # a parked pending_link request becomes reviewable again
        else:
            conn.execute(update(erp_supplier_links).where(erp_supplier_links.c.product_id == pid, erp_supplier_links.c.supplier_id == sid)
                         .values(has_cost=has_cost, last_seen_at=now))
        if not has_cost:
            out.no_cost += 1
            continue
        existing = current(conn, pid, sid, None)
        same = (existing is not None and existing.source == SOURCE and Decimal(str(existing.cost_with_recargo)) == cost
                and existing.lead_time_days == r.get("lead_time_days") and existing.min_order_qty == r.get("min_order_qty"))
        if same:
            refresh_erp_verification(conn, existing.id, now)
            out.unchanged += 1
            continue
        vat = directory.vat_for_product(pid)
        net = rate = None
        if vat is not None:
            try:
                pct = table.rate_for(vat)
                net, rate = net_from_gross(cost, pct), pct / 100
            except UnknownVatError:
                pass
        created = add_version(conn, NewCost(
            product_id=pid, supplier_id=sid, cost_with_recargo=cost, source=SOURCE, actor=ACTOR, cost_net=net, recargo_rate=rate,
            entered_includes_recargo=True, vat_rate_used=vat, lead_time_days=r.get("lead_time_days"), min_order_qty=r.get("min_order_qty"),
            currency=r.get("currency") or "EUR"), rules, now, verified_at=now)
        out.new_versions += 1
        out.jumps += bool(created.jump_flag)
    return out
