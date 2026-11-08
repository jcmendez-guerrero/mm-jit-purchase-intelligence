"""Read an export file into header-keyed rows after the file checks. Formulas are never evaluated, cells are text or numbers."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Any

from openpyxl import load_workbook

from .validate_file import Limits, LoaderFileError, check_headers, check_row_count, detect_format, normalise_headers


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise LoaderFileError("local_load_type_not_allowed", "unreadable text encoding")


def _delimiter(first_line: str) -> str:
    counts = {d: first_line.count(d) for d in (",", ";", "\t")}
    best = max(counts, key=lambda d: counts[d])
    return best if counts[best] else ","


def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    if isinstance(v, datetime):
        return v.strftime("%d/%m/%Y, %H:%M")
    if isinstance(v, date):
        return v.strftime("%d/%m/%Y")
    return str(v).strip()


def _csv_rows(data: bytes) -> list[list[str]]:
    text = _decode(data)
    first = text.split("\n", 1)[0]
    return [list(r) for r in csv.reader(io.StringIO(text, newline=""), delimiter=_delimiter(first))]


def _xlsx_rows(data: bytes) -> list[list[str]]:
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # unreadable workbook
        raise LoaderFileError("local_load_type_not_allowed", "unreadable workbook") from exc
    try:
        ws = wb[wb.sheetnames[0]]
        return [[_cell(c) for c in r] for r in ws.iter_rows(values_only=True)]
    finally:
        wb.close()


def read_table(kind: str, filename: str, data: bytes, limits: Limits) -> list[dict[str, str]]:
    """Header-keyed data rows (blank lines skipped). Raises ``LoaderFileError`` with a stable code on any file problem."""
    fmt = detect_format(filename, data, limits)
    raw = _csv_rows(data) if fmt == "csv" else _xlsx_rows(data)
    if not raw:
        raise LoaderFileError("local_load_signature_mismatch", "empty file")
    headers = normalise_headers(raw[0])
    while headers and headers[-1] == "":
        headers.pop()
    check_headers(kind, headers)
    rows = [r for r in raw[1:] if any(c.strip() for c in r)]
    check_row_count(len(rows), limits)
    return [{h: (r[i].strip() if i < len(r) else "") for i, h in enumerate(headers)} for r in rows]


def identify(filename: str, data: bytes, limits: Limits) -> str | None:
    """Which export this file is, from its header row (file names carry customer data and dates and are never relied on)."""
    from .formats import HEADERS

    try:
        fmt = detect_format(filename, data, limits)
        raw = _csv_rows(data) if fmt == "csv" else _xlsx_rows(data)
    except LoaderFileError:
        return None
    if not raw:
        return None
    headers = set(normalise_headers(raw[0]))
    for kind, want in HEADERS.items():
        if set(want) <= headers:
            return kind
    return None
