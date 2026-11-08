"""T063: import of the supplier export's rows (FR-019). New suppliers arrive unverified (the contact number is not yet known to be the API's);
existing ones are never overwritten except for a still-empty payment term. Nothing is merged and nothing is sent to the ERP.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from db.tables import supplier_review_items, suppliers
from sqlalchemy import select, update
from sqlalchemy.engine import Connection

from suppliers.dedupe import find_by_name
from suppliers.import_rules import suggest_classification
from suppliers.service import SupplierInput, add_review_item, create_supplier


def _open_item_exists(conn: Connection, kind: str, supplier_id: str) -> bool:
    return conn.execute(select(supplier_review_items.c.id).where(supplier_review_items.c.kind == kind, supplier_review_items.c.supplier_id == supplier_id,
                                                                 supplier_review_items.c.status == "open")).first() is not None


def import_suppliers(conn: Connection, rows: list[dict[str, Any]], actor: str, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(UTC)
    out = {"created": 0, "existing": 0, "possible_duplicates": 0, "unparsed_terms": 0, "suggested_non_purchasing": 0}
    for r in rows:
        existing = conn.execute(select(suppliers).where(suppliers.c.external_contact_id == r["external_contact_id"])).first()
        if existing is not None:
            out["existing"] += 1
            if existing.payment_terms_days is None and r["payment_terms_days"] is not None:
                conn.execute(update(suppliers).where(suppliers.c.id == existing.id).values(payment_terms_days=r["payment_terms_days"], version=int(existing.version) + 1,
                                                                                         updated_by=actor, updated_at=now))
            continue
        classification = suggest_classification(r["name"])
        out["possible_duplicates"] += bool(find_by_name(conn, r["name"]))
        s = create_supplier(conn, SupplierInput(name=r["name"], fiscal_type=r["fiscal_type"], country=r["country"], currency=r["currency"],
                                                payment_terms_days=r["payment_terms_days"], classification=classification), actor, confirm_duplicate=True, now=now,
                            origin="imported", external_contact_id=r["external_contact_id"], erp_link_state="unverified", has_note=bool(r["has_note"]))
        out["created"] += 1
        out["suggested_non_purchasing"] += classification == "non_purchasing"
        if r["terms_unparsed"] and not _open_item_exists(conn, "payment_terms_unparsed", s.id):
            add_review_item(conn, "payment_terms_unparsed", s.id, "Plazo de pago no interpretado", now)
            out["unparsed_terms"] += 1
    return out
