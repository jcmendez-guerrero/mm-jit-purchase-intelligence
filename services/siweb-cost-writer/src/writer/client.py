"""Siweb client of the cost writer. Allowlist first, then one bounded request. No redirects are followed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urljoin

import httpx

from writer.allowlist import WriterAllowlist


class TokenProvider(Protocol):
    def get_token(self) -> str: ...


class StaticToken:
    def __init__(self, token: str) -> None:
        self._t = token

    def get_token(self) -> str:
        return self._t

    def __repr__(self) -> str:
        return "StaticToken(***)"


class TransientError(Exception):
    """Retry later: 429, 5xx, timeouts, connection errors."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class PermanentError(Exception):
    """Do not retry: the ERP refused the request (4xx) or the response is unusable."""

    def __init__(self, detail: str, status: int | None = None) -> None:
        super().__init__(detail)
        self.detail, self.status = detail, status


@dataclass
class SiwebWriterClient:
    http: httpx.Client
    base_url: str
    allowlist: WriterAllowlist
    tokens: TokenProvider
    requests_made: int = 0

    def _send(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = urljoin(self.base_url, path)
        self.allowlist.check(method, url)
        self.requests_made += 1
        try:
            resp = self.http.request(method, url, json=body, follow_redirects=False,
                                     headers={"Authorization": f"Bearer {self.tokens.get_token()}", "Accept": "application/json"})
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise TransientError(type(exc).__name__) from exc
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransientError(f"HTTP {resp.status_code}")
        if resp.is_redirect:
            self.allowlist.check(method, urljoin(url, resp.headers.get("location", "")))   # refused unless it stays on the allowed path
            raise PermanentError("unexpected redirect", resp.status_code)
        if resp.status_code >= 400:
            raise PermanentError(f"HTTP {resp.status_code}", resp.status_code)
        try:
            return resp.json()  # type: ignore[no-any-return]
        except ValueError as exc:
            raise PermanentError("response is not JSON", resp.status_code) from exc

    def get_supplier(self, product_id: int, contact_id: int) -> dict[str, Any] | None:
        data = self._send("GET", f"/api/public/inventory/products/{product_id}/suppliers").get("data") or []
        return next((r for r in data if r.get("contact_id") == contact_id), None)

    def put_supplier(self, product_id: int, contact_id: int, body: dict[str, Any]) -> dict[str, Any]:
        return self._send("PUT", f"/api/public/inventory/products/{product_id}/suppliers/{contact_id}", body)
