"""T047: supplier name matching. Names are compared ignoring case, accents, punctuation and spacing; nothing is ever merged here."""

from __future__ import annotations

import unicodedata
from typing import Any

from db.tables import suppliers
from sqlalchemy import select
from sqlalchemy.engine import Connection


def name_key(name: str) -> str:
    stripped = "".join(c for c in unicodedata.normalize("NFKD", name or "") if not unicodedata.combining(c))
    return " ".join("".join(ch for ch in stripped.lower() if ch not in ".,").split())


def find_by_name(conn: Connection, name: str, *, exclude_id: str | None = None, active_only: bool = True) -> list[str]:
    """Ids of suppliers whose name matches exactly once folded. Computed from the names themselves, so older rows without a key still match."""
    key = name_key(name)
    if not key:
        return []
    q = select(suppliers.c.id, suppliers.c.name, suppliers.c.status, suppliers.c.merged_into)
    out: list[str] = []
    for r in conn.execute(q).all():
        if r.merged_into is not None or (active_only and r.status != "active") or r.id == exclude_id:
            continue
        if name_key(r.name) == key:
            out.append(str(r.id))
    return out


def row_dict(row: Any) -> dict[str, Any]:
    return dict(row._mapping)
