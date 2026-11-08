"""Client for the local export loader (compose override only). The BFF calls it as its own service identity, never as the user."""

from __future__ import annotations

import os
from typing import Any

import httpx

from .base import DownstreamClient, get_downstream_token


class LoaderClient(DownstreamClient):
    def __init__(self, base_url: str | None = None):
        super().__init__(base_url or os.environ.get("MMI_LOCAL_LOADER_URL", "http://local-loader:8091"), "api://mmi-local-loader")

    def _headers(self, user_id: str | None = None, roles: list[str] | None = None) -> dict[str, str]:
        # audience-scoped service identity (FR-039): the loader accepts only svc-api-bff or its own command
        return {"Authorization": f"Bearer {get_downstream_token(self.audience, ['bff'], subject='svc-api-bff')}"}

    async def health(self) -> bool:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=3.0) as client:
            return (await client.get("/healthz")).status_code == 200

    async def request(self, method: str, path: str, *, params: dict[str, Any] | None = None, files: Any = None) -> tuple[int, Any]:
        """Status and JSON body; a loader refusal is returned, not raised, so its stable code can be shown."""
        async with httpx.AsyncClient(base_url=self.base_url, timeout=300.0) as client:
            res = await client.request(method, path, params=params, files=files, headers=self._headers())
        return res.status_code, (res.json() if res.content else {})
