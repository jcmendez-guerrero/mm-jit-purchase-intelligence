"""Base HTTP client for BFF downstream service communication."""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Any

import httpx
from auth.identity import current_identity

logger = logging.getLogger("mmi.api_bff.clients")

# In-memory cache for service tokens: {cache_key: (token, expiry_timestamp)}
_token_cache: dict[str, tuple[str, float]] = {}


def get_downstream_token(audience: str, roles: list[str] | None = None, subject: str | None = None, auth_time: datetime | None = None) -> str:
    """Obtain a Bearer token for a downstream service.

    On behalf of the authenticated user when there is one (subject = user id, the user's effective roles only, the user's real
    second-factor time); otherwise as the BFF service identity with exactly the roles asked for. Locally the dev issuer signs
    it; in Azure the same shape comes from the identity provider's on-behalf-of flow. There is no fabricated fallback token.
    """
    if explicit_token := os.environ.get("MMI_TEST_SERVICE_TOKEN"):
        return explicit_token

    identity = current_identity.get()
    on_behalf_of = subject is None and identity is not None
    if on_behalf_of and identity is not None:
        subject, auth_time = identity.user_id, identity.mfa_datetime
    subject = subject or "svc-api-bff"
    roles_list = sorted(set(roles)) if roles else (["viewer"] if on_behalf_of else [])
    auth_epoch = int(auth_time.timestamp()) if auth_time else None
    cache_key = f"{audience}|{subject}|{','.join(roles_list)}|{auth_epoch}"
    now = time.monotonic()

    cached = _token_cache.get(cache_key)
    if cached and cached[1] > now:
        return cached[0]

    dev_issuer = os.environ.get("MMI_DEV_ISSUER_URL")
    if not dev_issuer:
        raise RuntimeError("no identity issuer configured for downstream calls")
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(f"{dev_issuer.rstrip('/')}/token", json={
                "subject": subject, "audience": audience, "roles": roles_list, "user": on_behalf_of, "auth_time": auth_epoch})
    except Exception as exc:
        raise RuntimeError("identity issuer unreachable") from exc
    if resp.status_code != 200:
        logger.warning("identity issuer refused the token request: status %s", resp.status_code)
        raise RuntimeError("identity issuer refused the token request")
    token = resp.json()["access_token"]
    _token_cache[cache_key] = (token, now + 300)               # short, because a user's roles and second factor can change
    return str(token)


class DownstreamClient:
    def __init__(self, base_url: str, audience: str):
        self.base_url = base_url.rstrip("/")
        self.audience = audience

    def _headers(self, user_id: str | None = None, roles: list[str] | None = None) -> dict[str, str]:
        token = get_downstream_token(self.audience, roles)
        identity = current_identity.get()
        return {
            "Authorization": f"Bearer {token}",
            "X-User-ID": identity.user_id if identity else (user_id or "bff"),     # informational; the token is what services trust
        }

    async def get(self, path: str, params: dict[str, Any] | None = None, user_id: str | None = None, roles: list[str] | None = None) -> httpx.Response:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            return await client.get(path, params=params, headers=self._headers(user_id, roles))

    async def post(self, path: str, json: Any = None, user_id: str | None = None, roles: list[str] | None = None,
                   extra_headers: dict[str, str] | None = None) -> httpx.Response:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            return await client.post(path, json=json, headers={**self._headers(user_id, roles), **(extra_headers or {})})

    async def put(self, path: str, json: Any = None, user_id: str | None = None, roles: list[str] | None = None,
                  extra_headers: dict[str, str] | None = None) -> httpx.Response:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            return await client.put(path, json=json, headers={**self._headers(user_id, roles), **(extra_headers or {})})

    async def patch(self, path: str, json: Any = None, user_id: str | None = None, roles: list[str] | None = None,
                    extra_headers: dict[str, str] | None = None) -> httpx.Response:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            return await client.patch(path, json=json, headers={**self._headers(user_id, roles), **(extra_headers or {})})

    async def forward(self, method: str, path: str, *, json: Any = None, params: dict[str, Any] | None = None, user_id: str | None = None,
                      roles: list[str] | None = None, if_match: str | None = None) -> Any:
        """Calls the downstream service as the signed-in user and returns its JSON; a refusal raises HTTPStatusError (turned into a stable code by main)."""
        headers = {**self._headers(user_id, roles), **({"If-Match": if_match} if if_match else {})}
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            res = await client.request(method, path, json=json, params=params, headers=headers)
        res.raise_for_status()
        return res.json() if res.content else {}
