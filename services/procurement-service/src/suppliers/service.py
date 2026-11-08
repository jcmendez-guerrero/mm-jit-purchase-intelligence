"""T046: suppliers managed in the platform (FR-012 to FR-018, FR-021).

Tax ids, bank details and free-text notes have no place here: the input type does not carry them. Every change is versioned
(optimistic concurrency on ``version``) and goes into the hash-chained audit. Nothing is sent to the ERP.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from audit.chain import append as audit
from db.tables import proposal_lines, proposals, supplier_review_items, suppliers
from sqlalchemy import func, insert, or_, select, update
from sqlalchemy.engine import Connection, Row

from suppliers.dedupe import find_by_name, name_key

FISCAL_TYPES = ("national", "intracommunity", "foreign")
CLASSIFICATIONS = ("purchasing", "non_purchasing", "unclassified")
CHANNELS = ("email", "phone", "web", "other")
EDITABLE = ("name", "fiscal_type", "country", "currency", "payment_terms_days", "order_channel", "classification")
OPEN_PROPOSAL_STATES = ("draft", "submitted", "approved")


class SupplierError(Exception):
    def __init__(self, code: str, message: str = "", field: str | None = None, duplicates: list[str] | None = None) -> None:
        super().__init__(message or code)
        self.code, self.field, self.duplicates = code, field, duplicates or []


class SupplierConflict(Exception):
    def __init__(self, current_version: int) -> None:
        super().__init__("supplier_version_conflict")
        self.code, self.current_version = "supplier_version_conflict", current_version


@dataclass(frozen=True)
class SupplierInput:
    name: str
    fiscal_type: str
    country: str
    currency: str
    payment_terms_days: int | None = None
    order_channel: str | None = None
    classification: str = "purchasing"


def _bad(field: str) -> SupplierError:
    return SupplierError("supplier_invalid", field, field=field)


def validate(d: SupplierInput) -> None:
    if not isinstance(d.name, str) or not d.name.strip() or len(d.name.strip()) > 200:
        raise _bad("name")
    if d.fiscal_type not in FISCAL_TYPES:
        raise _bad("fiscal_type")
    if not (isinstance(d.country, str) and len(d.country) == 2 and d.country.isalpha() and d.country.isupper()):
        raise _bad("country")
    if not (isinstance(d.currency, str) and len(d.currency) == 3 and d.currency.isalpha() and d.currency.isupper()):
        raise _bad("currency")
    if d.payment_terms_days is not None and not (isinstance(d.payment_terms_days, int) and not isinstance(d.payment_terms_days, bool) and 0 <= d.payment_terms_days <= 365):
        raise _bad("payment_terms_days")
    if d.order_channel is not None and d.order_channel not in CHANNELS:
        raise _bad("order_channel")
    if d.classification not in CLASSIFICATIONS:
        raise _bad("classification")


def _aware(ts: datetime | None) -> datetime | None:
    return None if ts is None else (ts if ts.tzinfo else ts.replace(tzinfo=UTC))


def get_supplier(conn: Connection, supplier_id: str) -> Row[Any]:
    row = conn.execute(select(suppliers).where(suppliers.c.id == supplier_id)).first()
    if row is None:
        raise SupplierError("supplier_not_found")
    return row


def add_review_item(conn: Connection, kind: str, supplier_id: str | None, detail: str, now: datetime) -> str:
    rid = str(uuid.uuid4())
    conn.execute(insert(supplier_review_items).values(id=rid, kind=kind, supplier_id=supplier_id, detail=detail[:200], status="open", created_at=now))
    return rid


def create_supplier(conn: Connection, data: SupplierInput, actor: str, *, confirm_duplicate: bool = False, now: datetime | None = None,
                    origin: str = "platform", external_contact_id: int | None = None, erp_link_state: str = "none", has_note: bool = False) -> Row[Any]:
    validate(data)
    now = now or datetime.now(UTC)
    dups = find_by_name(conn, data.name)
    if dups and not confirm_duplicate:
        raise SupplierError("supplier_possible_duplicate", duplicates=dups)
    sid = str(uuid.uuid4())
    conn.execute(insert(suppliers).values(
        id=sid, external_contact_id=external_contact_id, name=data.name.strip(), name_key=name_key(data.name), status="active",
        classification=data.classification, origin=origin, erp_link_state=erp_link_state, fiscal_type=data.fiscal_type, country=data.country,
        currency=data.currency, payment_terms_days=data.payment_terms_days, order_channel=data.order_channel, has_note=has_note, version=1,
        created_by=actor, created_at=now, updated_by=actor, updated_at=now))
    if dups:
        add_review_item(conn, "possible_duplicate", sid, f"Coincide con {len(dups)} proveedor(es) existente(s)", now)
    audit(conn, actor, "supplier.created", "supplier", sid, after={"origin": origin, "classification": data.classification, "currency": data.currency,
                                                                    "country": data.country}, now=now)
    return get_supplier(conn, sid)


def update_supplier(conn: Connection, supplier_id: str, changes: dict[str, Any], actor: str, expected_version: int, *, now: datetime | None = None,
                    confirm_duplicate: bool = False) -> Row[Any]:
    row = get_supplier(conn, supplier_id)
    unknown = set(changes) - set(EDITABLE)
    if unknown:
        raise _bad(sorted(unknown)[0])
    if row.status != "active":
        raise SupplierError("supplier_deactivated")
    if int(row.version) != expected_version:
        raise SupplierConflict(int(row.version))
    merged = {f: getattr(row, f) for f in EDITABLE} | changes
    validate(SupplierInput(**merged))
    now = now or datetime.now(UTC)
    if "name" in changes and name_key(changes["name"]) != name_key(row.name):
        dups = find_by_name(conn, changes["name"], exclude_id=supplier_id)
        if dups and not confirm_duplicate:
            raise SupplierError("supplier_possible_duplicate", duplicates=dups)
    values = {k: (v.strip() if k == "name" else v) for k, v in changes.items()}
    if "name" in values:
        values["name_key"] = name_key(values["name"])
    conn.execute(update(suppliers).where(suppliers.c.id == supplier_id).values(**values, version=int(row.version) + 1, updated_by=actor, updated_at=now))
    audit(conn, actor, "supplier.updated", "supplier", supplier_id, before={k: getattr(row, k) for k in changes if k != "name"},
          after={k: v for k, v in changes.items() if k != "name"} | ({"renamed": True} if "name" in changes else {}), now=now)
    return get_supplier(conn, supplier_id)


def deactivation_preview(conn: Connection, supplier_id: str) -> dict[str, Any]:
    q = (select(proposal_lines.c.proposal_id, proposal_lines.c.variant_id).join(proposals, proposals.c.id == proposal_lines.c.proposal_id)
         .where(proposal_lines.c.supplier_id == supplier_id, proposals.c.status.in_(OPEN_PROPOSAL_STATES)).order_by(proposal_lines.c.proposal_id, proposal_lines.c.variant_id))
    lines = conn.execute(q).all()
    return {"open_proposal_lines": len(lines), "lines": [{"proposal_id": r.proposal_id, "variant_id": r.variant_id} for r in lines[:50]],
            "proposals": sorted({r.proposal_id for r in lines})}


def flag_open_proposals(conn: Connection, supplier_id: str, now: datetime) -> int:
    """One review item per open proposal that still has lines for this supplier: the buyer re-generates or reallocates them."""
    prev = deactivation_preview(conn, supplier_id)
    for pid in prev["proposals"]:
        n = conn.execute(select(func.count()).select_from(proposal_lines).where(proposal_lines.c.proposal_id == pid, proposal_lines.c.supplier_id == supplier_id)).scalar()
        add_review_item(conn, "proposal_reallocation", supplier_id, f"{n} línea(s) de una propuesta abierta necesitan otro proveedor", now)
    return len(prev["proposals"])


def deactivate_supplier(conn: Connection, supplier_id: str, actor: str, *, confirm: bool, now: datetime | None = None) -> dict[str, Any]:
    row = get_supplier(conn, supplier_id)
    if row.status != "active":
        raise SupplierError("supplier_deactivated")
    preview = deactivation_preview(conn, supplier_id)
    if not confirm:
        return {**preview, "deactivated": False}
    now = now or datetime.now(UTC)
    conn.execute(update(suppliers).where(suppliers.c.id == supplier_id).values(status="deactivated", deactivated_by=actor, deactivated_at=now,
                                                                              version=int(row.version) + 1, updated_by=actor, updated_at=now))
    flag_open_proposals(conn, supplier_id, now)
    audit(conn, actor, "supplier.deactivated", "supplier", supplier_id, before={"status": "active"},
          after={"status": "deactivated", "open_proposal_lines": preview["open_proposal_lines"]}, now=now)
    return {**preview, "deactivated": True}


def reactivate_supplier(conn: Connection, supplier_id: str, actor: str, *, now: datetime | None = None) -> Row[Any]:
    row = get_supplier(conn, supplier_id)
    if row.merged_into is not None:
        raise SupplierError("supplier_merged")
    if row.status == "active":
        return row
    now = now or datetime.now(UTC)
    conn.execute(update(suppliers).where(suppliers.c.id == supplier_id).values(status="active", deactivated_by=None, deactivated_at=None,
                                                                              version=int(row.version) + 1, updated_by=actor, updated_at=now))
    audit(conn, actor, "supplier.reactivated", "supplier", supplier_id, before={"status": "deactivated"}, after={"status": "active"}, now=now)
    return get_supplier(conn, supplier_id)


def list_suppliers(conn: Connection, *, status: str | None = None, classification: str | None = None, q: str | None = None) -> list[Row[Any]]:
    stmt = select(suppliers).where(suppliers.c.merged_into.is_(None)).order_by(func.lower(suppliers.c.name))
    if status:
        stmt = stmt.where(suppliers.c.status == status)
    if classification:
        stmt = stmt.where(suppliers.c.classification == classification)
    if q and q.strip():
        k = name_key(q)
        stmt = stmt.where(or_(suppliers.c.name_key.contains(k), func.lower(suppliers.c.name).contains(q.strip().lower())))
    return list(conn.execute(stmt).all())
