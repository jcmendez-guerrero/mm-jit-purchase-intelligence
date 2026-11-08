"""T030: movements XLSX → platform movements, keyed by SKU. Nothing is guessed (research R4, R5).

What the Siweb-shaped payload can express is passed through, so the platform's own checks quarantine it: malformed expiry
(kept as raw text), missing warehouse (stored as unassigned), ambiguous local times and sales without a reference. What it
cannot express goes to the loader's review list: unknown SKU, unmapped type/reason, unreadable date or quantity, a sign
that contradicts the reason. Notes are reduced to a flag.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime

from .formats import NEGATIVE_REASONS, POSITIVE_REASONS, REASON_MAP, fold
from .parse_inventory import sku_key
from .readers import read_table
from .report import LoadReport
from .validate_file import Limits
from .values import parse_decimal

DATE_FORMATS = ("%d/%m/%Y, %H:%M", "%d/%m/%Y %H:%M")
EXPIRY = re.compile(r"^\d{2}/\d{2}/\d{4}$")


@dataclass
class Movement:
    row: int
    when: datetime                 # offset-less local time, as the ERP API serves it
    raw_date: str
    sku: str                       # folded key
    product_name: str
    warehouse: str | None
    batch: str | None
    expiry_iso: str | None
    expiry_raw: str
    expiry_valid: bool
    reason: str
    quantity: int
    has_note: bool
    reference: str | None


@dataclass
class MovementParse:
    movements: list[Movement]
    report: LoadReport
    ok_rows: int = 0


def _parse_when(text: str) -> datetime | None:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt)  # noqa: DTZ007 - offset-less local time on purpose
        except ValueError:
            continue
    return None


def _parse_expiry(text: str) -> tuple[str | None, bool]:
    t = text.strip()
    if not t:
        return None, True
    if EXPIRY.match(t):
        try:
            return datetime.strptime(t, "%d/%m/%Y").date().isoformat(), True  # noqa: DTZ007
        except ValueError:
            return None, False
    return None, False


def parse_movements(data: bytes, filename: str, limits: Limits, known_skus: set[str]) -> MovementParse:
    rows = read_table("movements", filename, data, limits)
    report = LoadReport(kind="movements", file_sha256=hashlib.sha256(data).hexdigest(), rows=len(rows))
    out = MovementParse([], report)

    def quarantine(n: int, code: str, detail: str) -> None:
        report.quarantined += 1
        report.review(n, code, detail)

    for n, r in enumerate(rows, start=2):
        when = _parse_when(r["Fecha"])
        if when is None:
            quarantine(n, "invalid_date", "Fecha con formato no válido")
            continue
        key = sku_key(r["SKU"])
        if key not in known_skus:
            quarantine(n, "unknown_sku", "SKU no presente en el inventario cargado")
            continue
        reason = REASON_MAP.get((fold(r["Tipo"]), fold(r["Motivo"])))
        if reason is None:
            quarantine(n, "unmapped_reason", "Tipo o motivo de movimiento no reconocido")
            continue
        try:
            qty_dec = parse_decimal(r["Cantidad"])
        except ValueError:
            quarantine(n, "invalid_number", "Cantidad no válida")
            continue
        if qty_dec != qty_dec.to_integral_value():
            quarantine(n, "non_integer_quantity", "Cantidad no entera")
            continue
        qty = int(qty_dec)
        if qty == 0:
            quarantine(n, "zero_quantity", "Cantidad cero")
            continue
        if (reason in POSITIVE_REASONS and qty < 0) or (reason in NEGATIVE_REASONS and qty > 0):
            quarantine(n, "sign_mismatch", "El signo de la cantidad no corresponde al motivo")
            continue
        expiry_iso, valid = _parse_expiry(r["Caducidad"])
        out.movements.append(Movement(
            row=n, when=when, raw_date=r["Fecha"], sku=key, product_name=r["Producto"], warehouse=r["Almacén"] or None,
            batch=r["Lote"] or None, expiry_iso=expiry_iso, expiry_raw=r["Caducidad"], expiry_valid=valid, reason=reason,
            quantity=qty, has_note=bool(r["Notas"].strip()), reference=r["Referencia"] or None,
        ))
        out.ok_rows += 1
    return out
