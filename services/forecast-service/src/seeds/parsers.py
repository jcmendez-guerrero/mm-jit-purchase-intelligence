"""T108: CSV and XLSX parsers with limits. Cells are text or numbers; formulas are never evaluated.

CSV: UTF-8 (with or without BOM) or Windows-1252, delimiter ``;``, ``,`` or tab detected from the header line. XLSX: the first sheet only,
read-only, cached values (``data_only``), so a formula cell yields its stored value or nothing, never a computed result.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from openpyxl import load_workbook
from upload_settings import ParseLimits

from seeds.storage import SeedFileError


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise SeedFileError("import_type_not_allowed", "unreadable text encoding")


def _delimiter(header: str) -> str:
    counts = {d: header.count(d) for d in (";", ",", "\t")}
    best = max(counts, key=lambda d: counts[d])
    return best if counts[best] else ";"


def parse_csv(data: bytes, limits: ParseLimits) -> tuple[list[str], list[dict[str, str]]]:
    text = _decode(data)
    first = text.split("\n", 1)[0]
    reader = csv.reader(io.StringIO(text), delimiter=_delimiter(first))
    rows = iter(reader)
    try:
        headers = [h.strip() for h in next(rows)]
    except StopIteration as exc:
        raise SeedFileError("import_missing_column", "empty file") from exc
    if len(headers) > limits.max_columns:
        raise SeedFileError("import_too_many_rows", "too many columns")
    out: list[dict[str, str]] = []
    for r in rows:
        if not any(c.strip() for c in r):
            continue                                               # a blank line is not data
        if len(out) >= limits.max_rows:
            raise SeedFileError("import_too_many_rows")
        out.append({h: (r[i].strip() if i < len(r) else "") for i, h in enumerate(headers)})
    return headers, out


def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    if hasattr(v, "isoformat"):
        return str(v.isoformat())[:10] if getattr(v, "hour", None) in (0, None) and getattr(v, "minute", 0) == 0 else str(v.isoformat())
    return str(v).strip()


def parse_xlsx(data: bytes, limits: ParseLimits) -> tuple[list[str], list[dict[str, str]]]:
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        raise SeedFileError("import_type_not_allowed", "unreadable workbook") from exc
    try:
        if len(wb.sheetnames) > limits.max_sheets:
            raise SeedFileError("import_too_many_rows", "too many sheets")
        ws = wb[wb.sheetnames[0]]
        it = ws.iter_rows(values_only=True)
        try:
            headers = [_cell(h) for h in next(it)]
        except StopIteration as exc:
            raise SeedFileError("import_missing_column", "empty sheet") from exc
        while headers and headers[-1] == "":
            headers.pop()
        if len(headers) > limits.max_columns:
            raise SeedFileError("import_too_many_rows", "too many columns")
        out: list[dict[str, str]] = []
        for r in it:
            cells = [_cell(c) for c in r[: len(headers)]]
            if not any(cells):
                continue
            if len(out) >= limits.max_rows:
                raise SeedFileError("import_too_many_rows")
            out.append({h: (cells[i] if i < len(cells) else "") for i, h in enumerate(headers)})
        return headers, out
    finally:
        wb.close()


def parse(fmt: str, data: bytes, limits: ParseLimits) -> tuple[list[str], list[dict[str, str]]]:
    return parse_csv(data, limits) if fmt == "csv" else parse_xlsx(data, limits)
