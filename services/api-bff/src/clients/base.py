"""Base HTTP client for BFF downstream service communication."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger("mmi.api_bff.clients")

# In-memory cache for service tokens: {cache_key: (token, expiry_timestamp)}
_token_cache: dict[str, tuple[str, float]] = {}


def get_downstream_token(audience: str, roles: list[str] | None = None) -> str:
    """Obtain a Bearer token for downstream services.

    In local Compose, requests a signed JWT from dev-issuer (/token).
    Falls back to role-based string for standalone unit tests.
    """
    if explicit_token := os.environ.get("MMI_TEST_SERVICE_TOKEN"):
        return explicit_token

    roles_list = sorted(roles) if roles else ["viewer", "buyer", "approver", "admin"]
    cache_key = f"{audience}:{','.join(roles_list)}"
    now = time.monotonic()

    cached = _token_cache.get(cache_key)
    if cached and cached[1] > now:
        return cached[0]

    dev_issuer = os.environ.get("MMI_DEV_ISSUER_URL")
    if dev_issuer:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(
                    f"{dev_issuer.rstrip('/')}/token",
                    json={
                        "subject": "svc-api-bff",
                        "audience": audience,
                        "roles": roles_list,
                    },
                )
                if resp.status_code == 200:
                    token = resp.json()["access_token"]
                    # Cache for 10 minutes
                    _token_cache[cache_key] = (token, now + 600)
                    return token
                else:
                    logger.warning("dev-issuer returned status %s: %s", resp.status_code, resp.text)
        except Exception as exc:
            logger.warning("Failed to connect to dev-issuer at %s: %s", dev_issuer, exc)

    # Fallback for standalone test suites without dev-issuer container
    return roles_list[0] if roles_list else "buyer"


class DownstreamClient:
    def __init__(self, base_url: str, audience: str):
        self.base_url = base_url.rstrip("/")
        self.audience = audience

    def _headers(self, user_id: str | None = None, roles: list[str] | None = None) -> dict[str, str]:
        token = get_downstream_token(self.audience, roles)
        return {
            "Authorization": f"Bearer {token}",
            "X-User-ID": user_id or "bff",
        }

    async def get(self, path: str, params: dict[str, Any] | None = None, user_id: str | None = None, roles: list[str] | None = None) -> httpx.Response:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            return await client.get(path, params=params, headers=self._headers(user_id, roles))

    async def post(self, path: str, json: Any = None, user_id: str | None = None, roles: list[str] | None = None) -> httpx.Response:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            return await client.post(path, json=json, headers=self._headers(user_id, roles))

    async def put(self, path: str, json: Any = None, user_id: str | None = None, roles: list[str] | None = None) -> httpx.Response:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            return await client.put(path, json=json, headers=self._headers(user_id, roles))
