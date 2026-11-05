"""Tokens a worker uses to call another service. Local: the dev issuer. Azure: its managed identity. Never stored, never logged."""

from __future__ import annotations

import os
import time

import httpx

_cache: dict[str, tuple[str, float]] = {}


def service_token(audience: str, subject: str, roles: list[str] | None = None, ttl_s: float = 240.0) -> str:
    """A bearer token for ``audience`` (for example ``api://mmi-inventory-service``), cached for a few minutes."""
    key = f"{audience}|{subject}|{','.join(sorted(roles or []))}"
    hit = _cache.get(key)
    if hit and hit[1] > time.monotonic():
        return hit[0]
    if issuer := os.environ.get("MMI_DEV_ISSUER_URL"):
        if os.environ.get("MMI_ENV") != "dev":
            raise RuntimeError("the dev issuer is only allowed with MMI_ENV=dev")
        r = httpx.post(f"{issuer.rstrip('/')}/token", json={"subject": subject, "audience": audience, "roles": roles or []}, timeout=5)
        r.raise_for_status()
        token = str(r.json()["access_token"])
    else:
        from azure.identity import DefaultAzureCredential  # type: ignore[import-not-found]

        token = str(DefaultAzureCredential().get_token(f"{audience}/.default").token)
    _cache[key] = (token, time.monotonic() + ttl_s)
    return token
