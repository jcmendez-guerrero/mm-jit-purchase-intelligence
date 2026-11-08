"""Persistence of the loader's own state in a private, ignored folder (never a database, never committed).

Holds: the SKU map, the parsed inventory and movements of earlier loads (so a later movements-only load can rebuild the whole
dataset), the values last written for protected fields, open/closed differences and the latest load results. Free text
(descriptions, notes) is never part of the parsed form; only a ``has_note`` flag is.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from .parse_inventory import InventoryItem
from .parse_movements import Movement

MAX_RUNS = 30


def _dec(v: Decimal | None) -> str | None:
    return None if v is None else str(v)


def item_to_json(i: InventoryItem) -> dict[str, Any]:
    d = asdict(i)
    for k in ("price", "cost", "tax_rate", "pvp_gross"):
        d[k] = _dec(getattr(i, k))
    d["lots"] = [[b, q] for b, q in i.lots]
    return d


def item_from_json(d: dict[str, Any]) -> InventoryItem:
    d = dict(d)
    for k in ("price", "cost", "tax_rate", "pvp_gross"):
        d[k] = None if d[k] is None else Decimal(d[k])
    d["lots"] = [(b, int(q)) for b, q in d["lots"]]
    return InventoryItem(**d)


def movement_to_json(m: Movement) -> dict[str, Any]:
    d = asdict(m)
    d["when"] = m.when.isoformat()
    return d


def movement_from_json(d: dict[str, Any]) -> Movement:
    d = dict(d)
    d["when"] = datetime.fromisoformat(d["when"])
    return Movement(**d)


class LoaderStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _path(self, name: str) -> Path:
        return self.root / name

    def _read(self, name: str, default: Any) -> Any:
        p = self._path(name)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default

    def _write(self, name: str, data: Any) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        p = self._path(name)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        tmp.replace(p)

    # --- parsed data
    def inventory(self) -> dict[str, InventoryItem]:
        return {k: item_from_json(v) for k, v in self._read("inventory.parsed.json", {}).items()}

    def save_inventory(self, items: dict[str, InventoryItem]) -> None:
        self._write("inventory.parsed.json", {k: item_to_json(v) for k, v in items.items()})

    def movements(self) -> list[Movement]:
        return [movement_from_json(d) for d in self._read("movements.parsed.json", [])]

    def save_movements(self, moves: list[Movement]) -> None:
        self._write("movements.parsed.json", [movement_to_json(m) for m in moves])

    # --- bookkeeping
    def last(self) -> dict[str, Any]:
        return self._read("last-load.json", {"item_hashes": {}, "last_written": {}, "accepted": [], "differences": [], "runs": []})

    def save_last(self, data: dict[str, Any]) -> None:
        data["runs"] = data["runs"][-MAX_RUNS:]
        self._write("last-load.json", data)

    def wipe(self) -> None:
        if self.root.exists():
            for child in self.root.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
