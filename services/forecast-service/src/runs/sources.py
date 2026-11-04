"""Series sources: HTTP (inventory-service export) and a local writer for blobs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx


class InventoryHttpSource:
    """Reads the series export with a service token (managed identity in Azure; a dev-issued token locally)."""

    def __init__(self, base_url: str, token: str, client: httpx.Client | None = None) -> None:
        self._base, self._token, self._client = base_url.rstrip("/"), token, client or httpx.Client(timeout=120)

    def fetch(self) -> dict[str, Any]:
        r = self._client.get(f"{self._base}/export/series", headers={"Authorization": f"Bearer {self._token}"})
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    def __repr__(self) -> str:
        return "InventoryHttpSource(token=***)"


class LocalBlobWriter:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def put(self, name: str, data: bytes) -> str:
        path = (self.root / name).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("blob name escapes the store")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path.as_uri()
