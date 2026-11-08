"""Small, strict value parsers for the exports (Spanish number formats, yes/no flags). Money is always ``Decimal``."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from .formats import fold

NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
CENT = Decimal("0.01")


def parse_decimal(text: str) -> Decimal:
    """``19.78``, ``19,78`` and ``1.234,56`` are accepted; anything else raises ``ValueError``."""
    s = (text or "").strip().replace(" ", "").replace(" ", "").replace("€", "")  # noqa: RUF001 - a non-breaking space can come from pasted spreadsheets
    if not s:
        raise ValueError("empty number")
    if "," in s and "." in s:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        s = s.replace("." if dec == "," else ",", "").replace(dec, ".")
    elif "," in s:
        s = s.replace(",", ".") if s.count(",") == 1 else s.replace(",", "")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    if not NUMBER.match(s):
        raise ValueError("not a number")
    try:
        return Decimal(s)
    except InvalidOperation as exc:
        raise ValueError("not a number") from exc


def parse_int(text: str) -> int:
    d = parse_decimal(text)
    if d != d.to_integral_value():
        raise ValueError("not an integer")
    return int(d)


def parse_flag(text: str) -> bool | None:
    """``Sí``/``Si``/``Yes``/``1`` → True; ``No``/``0``/blank → False; anything else → None (unknown)."""
    f = fold(text)
    if f in {"si", "yes", "1", "true"}:
        return True
    if f in {"no", "0", "false", ""}:
        return False
    return None
