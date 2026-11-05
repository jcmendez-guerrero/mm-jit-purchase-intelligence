"""Client for procurement-service."""

from __future__ import annotations

import os
from typing import Any

from .base import DownstreamClient


class ProcurementClient(DownstreamClient):
    def __init__(self, base_url: str | None = None):
        url = base_url or os.environ.get("MMI_PROCUREMENT_URL", "http://procurement-service:8000")
        super().__init__(url, "api://mmi-procurement-service")

    async def get_suppliers(self, roles: list[str] | None = None) -> list[dict[str, Any]]:
        res = await self.get("/suppliers", roles=roles)
        res.raise_for_status()
        return res.json()

    async def put_supplier_terms(self, supplier_id: str, terms: dict[str, Any], user_id: str, roles: list[str] | None = None) -> dict[str, Any]:
        res = await self.put(f"/suppliers/{supplier_id}/terms", json=terms, user_id=user_id, roles=roles)
        res.raise_for_status()
        return res.json()

    async def get_costs(self, roles: list[str] | None = None) -> list[dict[str, Any]]:
        res = await self.get("/costs", roles=roles)
        res.raise_for_status()
        return res.json()

    async def import_costs(self, payload: dict[str, Any], user_id: str, roles: list[str] | None = None) -> dict[str, Any]:
        res = await self.post("/costs/import", json=payload, user_id=user_id, roles=roles)
        res.raise_for_status()
        return res.json()

    async def get_cost_writes(self, roles: list[str] | None = None) -> list[dict[str, Any]]:
        res = await self.get("/cost-writes", roles=roles)
        res.raise_for_status()
        return res.json()

    async def approve_cost_write(self, write_id: str, user_id: str, roles: list[str] | None = None) -> dict[str, Any]:
        res = await self.post(f"/cost-writes/{write_id}/approve", json={}, user_id=user_id, roles=roles)
        res.raise_for_status()
        return res.json()

    async def get_proposals(self, roles: list[str] | None = None) -> list[dict[str, Any]]:
        res = await self.get("/proposals", roles=roles)
        res.raise_for_status()
        return res.json()

    async def get_proposal(self, proposal_id: str, roles: list[str] | None = None) -> dict[str, Any]:
        res = await self.get(f"/proposals/{proposal_id}", roles=roles)
        res.raise_for_status()
        return res.json()

    async def edit_proposal_line(self, proposal_id: str, line_id: str, payload: dict[str, Any], user_id: str, roles: list[str] | None = None) -> dict[str, Any]:
        res = await self.put(f"/proposals/{proposal_id}/lines/{line_id}", json=payload, user_id=user_id, roles=roles)
        res.raise_for_status()
        return res.json()

    async def submit_proposal(self, proposal_id: str, user_id: str, roles: list[str] | None = None) -> dict[str, Any]:
        res = await self.post(f"/proposals/{proposal_id}/submit", json={}, user_id=user_id, roles=roles)
        res.raise_for_status()
        return res.json()

    async def approve_proposal(self, proposal_id: str, user_id: str, roles: list[str] | None = None) -> dict[str, Any]:
        res = await self.post(f"/proposals/{proposal_id}/approve", json={}, user_id=user_id, roles=roles)
        res.raise_for_status()
        return res.json()

    async def confirm_order(self, proposal_id: str, supplier_id: str, payload: dict[str, Any], user_id: str, roles: list[str] | None = None) -> dict[str, Any]:
        res = await self.post(f"/proposals/{proposal_id}/orders/{supplier_id}/confirm", json=payload, user_id=user_id, roles=roles)
        res.raise_for_status()
        return res.json()

    async def export_proposal(self, proposal_id: str, fmt: str, supplier_id: str | None = None, roles: list[str] | None = None) -> bytes:
        params: dict[str, Any] = {"format": fmt}
        if supplier_id:
            params["supplier_id"] = supplier_id
        res = await self.get(f"/proposals/{proposal_id}/export", params=params, roles=roles)
        res.raise_for_status()
        return res.content
