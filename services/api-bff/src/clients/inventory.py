"""Client for inventory-service."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

from .base import DownstreamClient


class InventoryClient(DownstreamClient):
    def __init__(self, base_url: str | None = None):
        url = base_url or os.environ.get("MMI_INVENTORY_URL", "http://inventory-service:8000")
        super().__init__(url, "api://mmi-inventory-service")

    async def get_risks(self, warehouse_id: int | None = None, roles: list[str] | None = None) -> list[dict[str, Any]]:
        params = {"warehouse_id": warehouse_id} if warehouse_id is not None else None
        res = await self.get("/risk", params=params, roles=roles)
        res.raise_for_status()
        return res.json()

    async def get_sku_detail(self, sku: str, roles: list[str] | None = None) -> dict[str, Any]:
        res = await self.get(f"/skus/{quote(sku, safe='')}", roles=roles)
        res.raise_for_status()
        return res.json()

    async def internal_ids(self, sku: str, roles: list[str] | None = None) -> dict[str, Any]:
        """The catalogue owner turns a SKU into the ids the services use between themselves (FR-008a); nothing is cached or computed here."""
        res = await self.get(f"/skus/{quote(sku, safe='')}/variant", roles=roles)
        res.raise_for_status()
        return res.json()

    async def internal_id(self, sku: str, roles: list[str] | None = None) -> int:
        return int((await self.internal_ids(sku, roles))["id"])

    async def get_review_items(self, roles: list[str] | None = None) -> dict[str, Any]:
        res = await self.get("/review", roles=roles)
        res.raise_for_status()
        return res.json()

    async def decide_review(self, ids: list[int], decision: str, user_id: str, roles: list[str] | None = None) -> dict[str, Any]:
        res = await self.post("/review/decisions", json={"ids": ids, "decision": decision}, user_id=user_id, roles=roles)
        res.raise_for_status()
        return res.json()

    async def get_service_levels(self, roles: list[str] | None = None) -> dict[str, Any]:
        res = await self.get("/service-levels", roles=roles)
        res.raise_for_status()
        return res.json()

