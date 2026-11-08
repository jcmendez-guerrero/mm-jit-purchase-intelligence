"""T110: row validation. Every row ends up accepted or in quarantine with a stable reason code; nothing is dropped silently.

Whole-file refusals (mixed synthetic/real origin) raise instead of quarantining. Quantities are exact decimals. Free-text columns were
already dropped by the mapping, so notes and tax identifiers never reach this point or the database.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from seeds.storage import SeedFileError

KINDS = {"observado_externo": "observed_external", "estimado": "estimated", "prevision_manual": "manual_forecast",
         "observed_external": "observed_external", "estimated": "estimated", "manual_forecast": "manual_forecast"}
ORIGINS = {"sintetico": "synthetic", "synthetic": "synthetic", "real": "real"}
EARLIEST = date(2015, 1, 1)
MAX_AHEAD_DAYS = 548
MADRID = ZoneInfo("Europe/Madrid")
_DMY = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})(?:[ T](\d{1,2}):(\d{2}))?$")
_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{1,2}):(\d{2})(?::\d{2})?)?$")


@dataclass(frozen=True)
class Accepted:
    row_no: int
    variant_id: int
    day: date
    quantity: Decimal
    kind: str
    provenance: str
    warehouse: str | None


@dataclass(frozen=True)
class Quarantined:
    row_no: int
    reason_key: str
    params: dict[str, Any]
    raw_hash: str


@dataclass
class Validated:
    origin: str
    accepted: list[Accepted] = field(default_factory=list)
    quarantined: list[Quarantined] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.accepted) + len(self.quarantined)


def _o(text: str) -> str:
    """Case-insensitive, accent-insensitive key for kind and origin values."""
    return "".join(c for c in unicodedata.normalize("NFD", text.strip().lower()) if unicodedata.category(c) != "Mn")


def _hash(row: dict[str, str]) -> str:
    """A fingerprint of the mapped row for tracing: never the row itself."""
    return hashlib.sha256(json.dumps(sorted(row.items()), ensure_ascii=False).encode()).hexdigest()


def _is_ambiguous_local(d: date, hour: int, minute: int) -> bool:
    """Local time that happens twice (the autumn clock change) cannot be placed on the timeline without a UTC offset."""
    local = datetime(d.year, d.month, d.day, hour, minute, tzinfo=MADRID)
    return local.replace(fold=0).utcoffset() != local.replace(fold=1).utcoffset()


def _refuser(result: Validated, n: int, row: dict[str, str]) -> Callable[..., None]:
    def refuse(key: str, **params: Any) -> None:
        result.quarantined.append(Quarantined(n, key, params, _hash(row)))

    return refuse


def parse_day(text: str) -> tuple[date, bool]:
    """Returns (day, ambiguous_local_time). Raises ValueError for anything that is not a real calendar date."""
    t = text.strip()
    m = _ISO.match(t)
    if m:
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
        hh, mm = (int(m[4]), int(m[5])) if m[4] else (None, None)
    else:
        m = _DMY.match(t)
        if not m:
            raise ValueError(text)
        d, mo, y = int(m[1]), int(m[2]), int(m[3])
        hh, mm = (int(m[4]), int(m[5])) if m[4] else (None, None)
    day = date(y, mo, d)                                              # raises ValueError for 31/02 and similar
    return day, hh is not None and mm is not None and _is_ambiguous_local(day, hh, mm)


def parse_quantity(text: str) -> Decimal:
    t = text.strip().replace(" ", "")
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", t):
        t = t.replace(".", "")                                         # 1.234,5 -> 1234,5
    t = t.replace(",", ".")
    d = Decimal(t)
    if not d.is_finite():
        raise InvalidOperation
    return d


def validate_rows(rows: list[dict[str, str]], known_variants: Collection[int], today: date | None = None) -> Validated:
    today = today or datetime.now(UTC).date()
    latest = today + timedelta(days=MAX_AHEAD_DAYS)
    origins = {ORIGINS.get(_o(r.get("origin", ""))) for r in rows if r.get("origin", "").strip()}
    origins.discard(None)
    if len(origins) > 1:
        raise SeedFileError("import_mixed_origin")
    known = set(known_variants)
    result = Validated(origin=next(iter(origins), "synthetic"))
    seen: set[tuple[int, date, str]] = set()
    for n, row in enumerate(rows, start=2):                           # row 1 is the header
        refuse = _refuser(result, n, row)
        if not row.get("origin", "").strip() or _o(row["origin"]) not in ORIGINS:
            refuse("import_missing_column", field="origin")
            continue
        vtext = row.get("variant_id", "").strip()
        if not re.fullmatch(r"\d+", vtext) or int(vtext) < 1:
            refuse("import_unknown_variant", value_present=bool(vtext))
            continue
        variant = int(vtext)
        if variant not in known:
            refuse("import_unknown_variant", variant_id=variant)
            continue
        kind = KINDS.get(_o(row.get("kind", "")))
        if kind is None:
            refuse("import_unknown_kind")
            continue
        provenance = row.get("provenance", "").strip()
        if not provenance:
            refuse("import_missing_provenance")
            continue
        try:
            day, ambiguous = parse_day(row.get("day", ""))
        except ValueError:
            refuse("import_invalid_date")
            continue
        if ambiguous:
            refuse("import_ambiguous_time")
            continue
        if not (EARLIEST <= day <= latest):
            refuse("import_date_out_of_range", day=day.isoformat())
            continue
        try:
            qty = parse_quantity(row.get("quantity", ""))
        except (InvalidOperation, ValueError):
            refuse("import_invalid_quantity")
            continue
        if qty < 0:
            refuse("import_negative_quantity")
            continue
        key = (variant, day, kind)
        if key in seen:
            refuse("import_duplicate_row", variant_id=variant, day=day.isoformat())
            continue
        seen.add(key)
        result.accepted.append(Accepted(n, variant, day, qty, kind, provenance[:200], (row.get("warehouse", "").strip() or None)))
    if result.total != len(rows):                                      # nothing is dropped silently
        raise RuntimeError("row accounting mismatch")
    return result

