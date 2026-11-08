"""T060: supplier export → purchasing suppliers (FR-009, FR-019). Customers are excluded; tax ids, bank data, contacts, addresses and notes are
dropped at parse time (only a ``has_note`` flag survives). The ERP contact number (``ID``) is kept as the supplier's ERP reference.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .formats import COUNTRY_ISO, FISCAL_TYPE, fold
from .readers import read_table
from .report import LoadReport
from .validate_file import Limits

TERMS = re.compile(r"^(\d{1,3})\s*(?:d[ií]as?)?$")


@dataclass(frozen=True)
class SupplierRow:
    row: int
    external_id: int
    name: str
    fiscal_type: str
    country: str
    currency: str
    payment_terms_days: int | None
    terms_unparsed: bool
    has_note: bool


@dataclass
class SupplierParse:
    suppliers: list[SupplierRow]
    report: LoadReport
    ok_rows: int = 0


def parse_payment_terms(text: str) -> tuple[int | None, bool]:
    """(days, unparsed): "7 días" and "30" give days; blank gives nothing and is not a problem; anything else is left empty and listed for review."""
    t = fold(text)
    if not t:
        return None, False
    m = TERMS.match(t)
    if m and 0 <= int(m.group(1)) <= 365:
        return int(m.group(1)), False
    return None, True


def parse_suppliers(data: bytes, filename: str, limits: Limits) -> SupplierParse:
    rows = read_table("suppliers", filename, data, limits)
    report = LoadReport(kind="suppliers", file_sha256=hashlib.sha256(data).hexdigest(), rows=len(rows))
    out = SupplierParse([], report)
    seen: set[int] = set()

    def quarantine(n: int, code: str, detail: str) -> None:
        report.quarantined += 1
        report.review(n, code, detail)

    for n, r in enumerate(rows, start=2):
        if fold(r["Tipo Relación"]) == "cliente":
            report.exclude()
            continue
        raw_id = r["ID"].strip()
        if not raw_id.isdigit() or int(raw_id) < 1:
            quarantine(n, "invalid_id", "Número de contacto no válido")
            continue
        ident = int(raw_id)
        if ident in seen:
            quarantine(n, "duplicate_id", "Número de contacto repetido")
            continue
        name = " ".join(r["Nombre Empresa"].split())
        if not name:
            quarantine(n, "missing_name", "Proveedor sin nombre")
            continue
        country_raw = r["País"].strip()
        country = COUNTRY_ISO.get(fold(country_raw)) if country_raw else "ES"
        if country is None:
            quarantine(n, "unknown_country", "País no reconocido")
            continue
        fiscal_raw = fold(r["Tipo Fiscal"])
        fiscal = FISCAL_TYPE.get(fiscal_raw) if fiscal_raw else ("national" if country == "ES" else "foreign")
        if fiscal is None:
            quarantine(n, "unknown_fiscal_type", "Tipo fiscal no reconocido")
            continue
        currency = r["Moneda Habitual"].strip().upper() or "EUR"
        if not re.fullmatch(r"[A-Z]{3}", currency):
            quarantine(n, "invalid_currency", "Moneda no válida")
            continue
        days, unparsed = parse_payment_terms(r["Condiciones Pago"])
        seen.add(ident)
        out.suppliers.append(SupplierRow(n, ident, name, fiscal, country, currency, days, unparsed, bool(r["Notas"].strip())))
        out.ok_rows += 1
    return out
