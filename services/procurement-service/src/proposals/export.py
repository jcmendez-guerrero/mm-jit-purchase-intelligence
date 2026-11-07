"""T103: CSV and Excel exports of an approved proposal, in the Spanish locale profile.

CSV: UTF-8 with BOM, semicolon delimiter, comma decimals, dd/mm/yyyy dates. Excel: native numeric cells with an euro
number format and Spanish headers. Headers come from the es-ES catalogue. Exporting writes nothing to the ERP; it marks
the proposal exported (an audited state change).
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from approvals.workflow import is_approval_valid
from audit.chain import append as audit
from db.tables import product_refs, proposal_lines, proposals, supplier_order_groups, suppliers
from i18n import t
from sqlalchemy import select, update
from sqlalchemy.engine import Connection

HEADERS = ("export.supplier", "export.sku", "export.product", "export.variant", "export.qty", "export.unit_cost", "export.line_total", "export.expected_delivery")


class ExportError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def neutralise(value: Any) -> Any:
    """Text that a spreadsheet could execute is made inert (supplier and product names come from the ERP and are not trusted). Numbers stay numbers."""
    if value is None or isinstance(value, bool | int | float | Decimal):
        return value
    text = str(value)
    return "'" + text if text.startswith(DANGEROUS) else text


def es_decimal(value: Decimal, places: int = 2) -> str:
    q = Decimal(1).scaleb(-places)
    return f"{value.quantize(q):f}".replace(".", ",")


def es_date(d: Any) -> str:
    return "" if d is None else d.strftime("%d/%m/%Y")


def rows_for(conn: Connection, proposal_id: str, supplier_id: str | None = None) -> list[list[Any]]:
    q = select(proposal_lines).where(proposal_lines.c.proposal_id == proposal_id, proposal_lines.c.qty > 0).order_by(proposal_lines.c.supplier_id, proposal_lines.c.variant_id)
    if supplier_id:
        q = q.where(proposal_lines.c.supplier_id == supplier_id)
    names = {r.id: r.name for r in conn.execute(select(suppliers)).all()}
    eta = {g.supplier_id: g.expected_delivery_date for g in conn.execute(select(supplier_order_groups).where(supplier_order_groups.c.proposal_id == proposal_id)).all()}
    ref = {r.variant_id: r for r in conn.execute(select(product_refs)).all()}
    out = []
    for ln in conn.execute(q).all():
        r = ref.get(ln.variant_id)
        out.append([names.get(ln.supplier_id, ln.supplier_id), (r.sku if r else None) or "", (r.name if r else None) or "", ln.variant_id, ln.qty,
                    Decimal(str(ln.unit_cost_with_recargo)), Decimal(str(ln.line_total)), eta.get(ln.supplier_id)])
    return out


def export_csv(rows: list[list[Any]]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow([t(h) for h in HEADERS])
    for r in rows:
        w.writerow([neutralise(r[0]), neutralise(r[1]), neutralise(r[2]), r[3], r[4], es_decimal(r[5], 4), es_decimal(r[6]), es_date(r[7])])
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


def export_xlsx(rows: list[list[Any]]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = t("export.sheet")
    ws.append([t(h) for h in HEADERS])
    for r in rows:
        ws.append([neutralise(r[0]), neutralise(r[1]), neutralise(r[2]), r[3], r[4], float(r[5]), float(r[6]), r[7]])
    for row in ws.iter_rows(min_row=2):
        row[5].number_format = '#,##0.0000 "€"'
        row[6].number_format = '#,##0.00 "€"'
        row[7].number_format = "DD/MM/YYYY"
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def export_proposal(conn: Connection, proposal_id: str, fmt: str, actor: str, supplier_id: str | None = None, now: datetime | None = None) -> bytes:
    if fmt not in ("csv", "xlsx"):
        raise ExportError("unsupported_format")
    now = now or datetime.now(UTC)
    p = conn.execute(select(proposals).where(proposals.c.id == proposal_id)).first()
    if p is None:
        raise ExportError("unknown_proposal")
    if p.status not in ("approved", "exported") or not is_approval_valid(conn, proposal_id):
        raise ExportError("proposal_not_approved")
    rows = rows_for(conn, proposal_id, supplier_id)
    data = export_csv(rows) if fmt == "csv" else export_xlsx(rows)
    if p.status == "approved":
        conn.execute(update(proposals).where(proposals.c.id == proposal_id).values(status="exported", updated_at=now))
    audit(conn, actor, "proposal.exported", "proposal", proposal_id, before={"status": p.status}, after={"status": "exported", "format": fmt, "rows": len(rows)}, now=now)
    return data
