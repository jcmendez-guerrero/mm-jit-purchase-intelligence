"""T079: supplier price-list import from a fixed template (CSV or Excel). All or nothing.

Template columns (exact, Spanish headers are the UI's concern; the file uses these keys):
    variant_id, cost, includes_recargo, pack_size, lead_time_days, min_order_qty
Every problem is reported with its row and column; if there is any, nothing is stored (nothing is dropped silently).
Excel macro workbooks and oversized files are refused. Rows are validated against known variants and, for net costs,
the product's VAT rate.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.engine import Connection

from costs.directory import ProductRef, SqlProductDirectory
from costs.recargo import RecargoTable, UnknownVatError, gross_from_net, net_from_gross
from costs.rules import CostRules
from costs.store import NewCost, add_version

TEMPLATE = ("variant_id", "cost", "includes_recargo", "pack_size", "lead_time_days", "min_order_qty")
MAX_BYTES = 2_000_000
MAX_ROWS = 5000
YES, NO = {"si", "sí", "s", "yes", "y", "true", "1"}, {"no", "n", "false", "0"}


@dataclass(frozen=True)
class RowError:
    row: int          # 1-based file row, header = 1
    column: str
    code: str


@dataclass
class ParsedRow:
    row: int
    variant_id: int
    product_id: int
    cost_with_recargo: Decimal
    cost_net: Decimal | None
    recargo_rate: Decimal | None
    entered_includes_recargo: bool
    vat_rate: Decimal | None
    pack_size: int | None
    lead_time_days: int | None
    min_order_qty: int | None


@dataclass
class ImportResult:
    rows: list[ParsedRow] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)
    applied: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


class ImportFileError(Exception):
    """The file itself is unusable (type, size, header)."""


def read_rows(data: bytes, filename: str) -> list[dict[str, Any]]:
    if len(data) > MAX_BYTES:
        raise ImportFileError("file_too_large")
    name = filename.lower()
    if name.endswith(".xlsm") or name.endswith(".xlsb"):
        raise ImportFileError("macro_workbook_refused")
    if name.endswith(".xlsx"):
        return _read_xlsx(data)
    if name.endswith(".csv"):
        return _read_csv(data)
    raise ImportFileError("unsupported_file_type")


def _check_header(header: list[str]) -> None:
    if tuple(h.strip().lower() for h in header[:len(TEMPLATE)]) != TEMPLATE or len(header) != len(TEMPLATE):
        raise ImportFileError("template_mismatch")


def _read_csv(data: bytes) -> list[dict[str, Any]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportFileError("not_utf8") from exc
    first = text.splitlines()[0] if text.strip() else ""
    delimiter = ";" if first.count(";") >= first.count(",") and ";" in first else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        raise ImportFileError("empty_file")
    _check_header(rows[0])
    if len(rows) - 1 > MAX_ROWS:
        raise ImportFileError("too_many_rows")
    return [dict(zip(TEMPLATE, [c.strip() for c in r], strict=False)) | {"_row": i + 2} for i, r in enumerate(rows[1:])]


def _read_xlsx(data: bytes) -> list[dict[str, Any]]:
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        raise ImportFileError("unreadable_workbook") from exc
    sheet = wb.worksheets[0]
    rows = [[("" if c is None else str(c).strip()) for c in r] for r in sheet.iter_rows(values_only=True)]
    rows = [r for r in rows if any(r)]
    if not rows:
        raise ImportFileError("empty_file")
    _check_header(rows[0])
    if len(rows) - 1 > MAX_ROWS:
        raise ImportFileError("too_many_rows")
    return [dict(zip(TEMPLATE, r, strict=False)) | {"_row": i + 2} for i, r in enumerate(rows[1:])]


def parse_decimal(text: str) -> Decimal:
    """Accepts 1.25, 1,25 and 1.234,56 (Spanish thousands). Rejects anything else."""
    t = text.strip().replace(" ", "")
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    else:
        t = t.replace(",", ".")
    try:
        d = Decimal(t)
    except InvalidOperation as exc:
        raise ValueError from exc
    if not d.is_finite():
        raise ValueError
    return d


def _int(text: str, minimum: int) -> int | None:
    if text == "":
        return None
    v = int(text)
    if v < minimum:
        raise ValueError
    return v


def validate(rows: list[dict[str, Any]], directory: SqlProductDirectory, table: RecargoTable) -> ImportResult:
    res = ImportResult()
    seen: dict[int, int] = {}
    for raw in rows:
        n = raw["_row"]
        errs: list[RowError] = []
        ref: ProductRef | None = None
        try:
            vid = int(raw["variant_id"])
            if vid < 1:
                raise ValueError
            if vid in seen:
                errs.append(RowError(n, "variant_id", f"duplicate_of_row_{seen[vid]}"))
            seen.setdefault(vid, n)  # later rows point at the first occurrence
            ref = directory.by_variant(vid)
            if ref is None:
                errs.append(RowError(n, "variant_id", "unknown_variant"))
        except ValueError:
            errs.append(RowError(n, "variant_id", "not_an_integer"))
            vid = 0
        cost = None
        try:
            cost = parse_decimal(raw["cost"])
            if cost < 0:
                errs.append(RowError(n, "cost", "negative"))
        except ValueError:
            errs.append(RowError(n, "cost", "not_a_number"))
        flag = raw["includes_recargo"].strip().lower()
        includes = True if flag in YES else False if flag in NO else None
        if includes is None:
            errs.append(RowError(n, "includes_recargo", "must_be_si_or_no"))
        opts: dict[str, int | None] = {}
        for col, minimum in (("pack_size", 1), ("lead_time_days", 0), ("min_order_qty", 0)):
            try:
                opts[col] = _int(raw[col], minimum)
            except ValueError:
                errs.append(RowError(n, col, "invalid_integer"))
        net = rate = vat = None
        gross = cost
        if cost is not None and includes is not None and ref is not None and cost >= 0:
            vat = ref.vat_rate
            try:
                pct = table.rate_for(vat)
                rate = pct / 100
                if includes:
                    net = net_from_gross(cost, pct)
                else:
                    net, gross = cost, gross_from_net(cost, pct)
            except UnknownVatError:
                if not includes:
                    errs.append(RowError(n, "includes_recargo", "vat_unknown_for_net_cost"))
        res.errors += errs
        if not errs and cost is not None and includes is not None and ref is not None and gross is not None:
            res.rows.append(ParsedRow(n, vid, ref.product_id, gross, net, rate, includes, vat, opts["pack_size"], opts["lead_time_days"], opts["min_order_qty"]))
    return res


def apply(conn: Connection, result: ImportResult, supplier_id: str, actor: str, rules: CostRules, now: datetime | None = None) -> int:
    """Stores a version per row, but only when the whole file validated. Returns the number stored."""
    if result.errors:
        return 0
    now = now or datetime.now(UTC)
    for r in result.rows:
        add_version(conn, NewCost(
            product_id=r.product_id, supplier_id=supplier_id, variant_id=r.variant_id, cost_with_recargo=r.cost_with_recargo, source="csv_price_list",
            actor=actor, cost_net=r.cost_net, recargo_rate=r.recargo_rate, entered_includes_recargo=r.entered_includes_recargo, vat_rate_used=r.vat_rate,
            pack_size=r.pack_size, lead_time_days=r.lead_time_days, min_order_qty=r.min_order_qty), rules, now)
    result.applied = len(result.rows)
    return result.applied
