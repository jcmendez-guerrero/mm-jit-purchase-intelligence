"""T115 + T103: the downloadable Spanish template and formula-safe output.

Any text cell that a spreadsheet could read as a formula (leading ``=``, ``+``, ``-``, ``@``, tab or carriage return) is prefixed with an
apostrophe so it stays inert; numbers are written as numbers. Used for the template and for the quarantine report.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from i18n import t
from openpyxl import Workbook

DANGEROUS = ("=", "+", "-", "@", "\t", "\r")
COLUMNS = ("sku", "day", "quantity", "warehouse", "kind", "provenance", "origin")


def neutralise(value: Any) -> Any:
    """Numbers stay numbers; text that could execute is made inert."""
    if isinstance(value, bool) or value is None or isinstance(value, int | float):
        return value
    text = str(value)
    return "'" + text if text.startswith(DANGEROUS) else text


def headers() -> list[str]:
    return [t(f"template.col.{c}") for c in COLUMNS]


def example_rows() -> list[list[Any]]:
    """Made-up values only (fictional SKUs EJ-0001 and EJ-0002, 2026 dates)."""
    return [["EJ-0001", "2026-01-05", 2, "", t("kind.estimated"), "Hoja sintética A", t("origin.synthetic")],
            ["EJ-0002", "2026-01-12", 1, "", t("kind.manual_forecast"), "Hoja sintética A", t("origin.synthetic")]]


def template_csv() -> bytes:
    out = io.StringIO()
    w = csv.writer(out, delimiter=";", lineterminator="\n")
    w.writerow(headers())
    for r in example_rows():
        w.writerow([neutralise(c) if c != "" else "" for c in r])
    return ("﻿" + out.getvalue()).encode("utf-8")


def template_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = t("template.sheet")
    ws.append(headers())
    for r in example_rows():
        ws.append([neutralise(c) if c != "" else None for c in r])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def quarantine_csv(rows: list[tuple[int, str]]) -> bytes:
    """(row number, reason text) -> CSV the buyer can open safely."""
    out = io.StringIO()
    w = csv.writer(out, delimiter=";", lineterminator="\n")
    w.writerow([t("quarantine.row"), t("quarantine.reason")])
    for n, reason in rows:
        w.writerow([n, neutralise(reason)])
    return ("﻿" + out.getvalue()).encode("utf-8")


def quarantine_xlsx(rows: list[tuple[int, str]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = t("quarantine.sheet")
    ws.append([t("quarantine.row"), t("quarantine.reason")])
    for n, reason in rows:
        ws.append([n, neutralise(reason)])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
