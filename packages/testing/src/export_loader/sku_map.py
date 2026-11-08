"""T015: SKU → surrogate id map (research R1). Ids come from the reserved range and are never sent to the ERP.

The map is append-only and persisted in the loader state folder (ignored by version control). Matching ignores case and
surrounding spaces; the first spelling seen is kept for display.
"""

from __future__ import annotations

import json
from pathlib import Path

from .formats import SURROGATE_BASE


def _key(sku: str) -> str:
    return sku.strip().casefold()


class SkuMap:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._next = SURROGATE_BASE
        self._ids: dict[str, int] = {}
        self._display: dict[str, str] = {}
        self._warehouses: dict[str, int] = {}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._next = int(data["next"])
            self._warehouses = {k: int(v) for k, v in data.get("warehouses", {}).items()}
            for sku, ident in data["skus"].items():
                self._ids[_key(sku)] = int(ident)
                self._display[_key(sku)] = sku

    def __len__(self) -> int:
        return len(self._ids)

    def lookup(self, sku: str) -> int | None:
        return self._ids.get(_key(sku))

    def get_or_assign(self, sku: str) -> int:
        k = _key(sku)
        if k not in self._ids:
            self._ids[k] = self._next
            self._display[k] = sku.strip()
            self._next += 1
        return self._ids[k]

    def warehouse_id(self, name: str) -> int:
        """Stable small ids (1, 2, …) for warehouse names, so reloads never renumber them."""
        key = " ".join(name.split()).casefold()
        if key not in self._warehouses:
            self._warehouses[key] = len(self._warehouses) + 1
        return self._warehouses[key]

    def warehouse_names(self) -> dict[str, int]:
        return dict(self._warehouses)

    def sku_for(self, ident: int) -> str | None:
        for k, v in self._ids.items():
            if v == ident:
                return self._display[k]
        return None

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"next": self._next, "skus": {self._display[k]: v for k, v in self._ids.items()}, "warehouses": self._warehouses}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    def wipe(self) -> None:
        self.path.unlink(missing_ok=True)
        self._ids.clear()
        self._display.clear()
        self._warehouses.clear()
        self._next = SURROGATE_BASE
