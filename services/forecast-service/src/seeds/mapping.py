"""T109: header mapping. A header is matched to a canonical field by its normalised name; the buyer can correct it and save the mapping."""

from __future__ import annotations

import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Any

from audit import append as audit
from db.tables import seed_mappings
from sqlalchemy import insert, select
from sqlalchemy.engine import Connection

CANONICAL = ("variant_id", "sku", "day", "quantity", "warehouse", "kind", "provenance", "origin")
REQUIRED = ("variant_id", "day", "quantity", "kind", "provenance", "origin")
SYNONYMS: dict[str, tuple[str, ...]] = {
    "variant_id": ("id de variante siweb", "id variante", "variante", "variant_id", "variant id"),
    "sku": ("sku", "referencia"),
    "day": ("fecha", "dia", "day", "date"),
    "quantity": ("cantidad", "unidades", "quantity", "qty"),
    "warehouse": ("almacen", "warehouse"),
    "kind": ("tipo de dato", "tipo", "kind"),
    "provenance": ("origen", "fuente", "provenance"),
    "origin": ("sintetico/real", "sintetico real", "origin"),
}


class MappingError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.strip().lower()) if unicodedata.category(c) != "Mn")


def suggest(headers: list[str]) -> dict[str, str]:
    """header -> canonical field for every header that is recognised; unknown headers (notes, tax ids, ...) are simply not mapped and never stored."""
    out: dict[str, str] = {}
    taken: set[str] = set()
    for h in headers:
        n = _norm(h)
        for field, names in SYNONYMS.items():
            if field not in taken and n in names:
                out[h] = field
                taken.add(field)
                break
    return out


def missing_required(column_map: dict[str, str]) -> list[str]:
    have = set(column_map.values())
    return [f for f in REQUIRED if f not in have]


def validate_map(column_map: dict[str, str]) -> None:
    fields = list(column_map.values())
    if any(f not in CANONICAL for f in fields) or len(set(fields)) != len(fields):
        raise MappingError("request_invalid")


def apply(column_map: dict[str, str], rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keeps only mapped columns: free-text notes and anything unmapped are dropped here, before validation or storage."""
    return [{field: row.get(h, "") for h, field in column_map.items()} for row in rows]


def save_mapping(conn: Connection, name: str, column_map: dict[str, str], actor: str, now: datetime | None = None) -> str:
    validate_map(column_map)
    name = name.strip()
    if not name or len(name) > 120:
        raise MappingError("request_invalid")
    now = now or datetime.now(UTC)
    existing = conn.execute(select(seed_mappings.c.id).where(seed_mappings.c.name == name)).first()
    if existing is not None:
        raise MappingError("import_mapping_name_taken")
    mid = str(uuid.uuid4())
    conn.execute(insert(seed_mappings).values(id=mid, name=name, column_map=column_map, created_by=actor, created_at=now))
    audit(conn, actor, "seed_mapping.saved", "seed_mapping", mid, after={"name": name, "fields": sorted(column_map.values())}, now=now)
    return mid


def list_mappings(conn: Connection) -> list[dict[str, Any]]:
    return [{"id": r.id, "name": r.name, "column_map": r.column_map, "created_by": r.created_by}
            for r in conn.execute(select(seed_mappings).order_by(seed_mappings.c.name)).all()]
