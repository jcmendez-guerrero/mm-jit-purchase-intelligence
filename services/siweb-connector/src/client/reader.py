"""Typed Siweb reader client: allowlist, rate budget, retries, three pagination shapes.

Order of checks for every call: allowlist (before the request is built) -> rate budget -> send.
Redirects are never followed automatically; a redirect is re-checked against the allowlist.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import httpx
from allowlist.allowlist import API_PREFIX, Allowlist
from ratelimit.bucket import TokenBucket

from client.token import TokenProvider

MAX_PAGE = 200
RETRY_STATUSES = {429, 500, 502, 503, 504}


class AuthExpiredError(Exception):
    """401: the token is invalid or expired; the run stops and alerts."""


class BudgetExhaustedError(Exception):
    """The request budget is spent; the run checkpoints and resumes in the next window."""


class SiwebError(Exception):
    def __init__(self, status: int, path: str) -> None:
        super().__init__(f"Siweb returned {status} for {path}")
        self.status, self.path = status, path


@dataclass
class ReaderClient:
    http: httpx.Client
    base_url: str  # scheme://host, no path
    allowlist: Allowlist
    bucket: TokenBucket
    tokens: TokenProvider
    sleep: Callable[[float], None] = time.sleep
    max_retries: int = 4
    backoff_base: float = 2.0
    wait_for_budget: bool = False
    requests_made: int = 0
    retries: int = 0
    log: list[dict[str, Any]] = field(default_factory=list)  # method/path/status only: no tokens, no payload

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = urljoin(self.base_url, path)
        self.allowlist.check("GET", url)  # raises before anything is built
        attempt = 0
        while True:
            self._take_budget()
            resp = self._send(url, params)
            if resp.is_redirect:
                self.allowlist.check("GET", urljoin(url, resp.headers.get("location", "")))
                raise SiwebError(resp.status_code, path)  # allowed targets are not expected; fail visibly
            if resp.status_code == 401:
                invalidate = getattr(self.tokens, "invalidate", None)
                if invalidate and attempt == 0:
                    invalidate()
                    attempt += 1
                    continue
                raise AuthExpiredError(path)
            if resp.status_code in RETRY_STATUSES and attempt < self.max_retries:
                self.retries += 1
                self.sleep(self._delay(resp, attempt))
                attempt += 1
                continue
            if resp.status_code >= 400:
                raise SiwebError(resp.status_code, path)
            return resp.json()  # type: ignore[no-any-return]

    def _send(self, url: str, params: dict[str, Any] | None) -> httpx.Response:
        self.requests_made += 1
        resp = self.http.get(
            url, params=params, follow_redirects=False,
            headers={"Authorization": f"Bearer {self.tokens.get_token()}", "Accept": "application/json"},
        )
        self.log.append({"method": "GET", "path": httpx.URL(url).path, "status": resp.status_code})
        return resp

    def _take_budget(self) -> None:
        while not self.bucket.try_acquire():
            if not self.wait_for_budget:
                raise BudgetExhaustedError("hourly request budget spent")
            self.sleep(self.bucket.seconds_until_available())

    def _delay(self, resp: httpx.Response, attempt: int) -> float:
        retry_after = resp.headers.get("retry-after")  # the real API documents none (V3); honour it if present
        if retry_after and retry_after.isdigit():
            return float(min(int(retry_after), 300))
        return min(self.backoff_base ** attempt, 60.0)

    # --- pagination -------------------------------------------------------------------------
    def pages(self, path: str, params: dict[str, Any] | None = None, limit: int = MAX_PAGE,
              start_page: int = 1) -> Iterator[tuple[int, dict[str, Any], list[dict[str, Any]]]]:
        """Yield (page, body, rows). Handles the three shapes: ``pagination{pages}``, ``totalPages``, ``total``."""
        limit = min(limit, MAX_PAGE)
        page = start_page
        while True:
            body = self.get(path, {**(params or {}), "page": page, "limit": limit})
            rows = body.get("data") or []
            yield page, body, rows
            if not rows or page >= total_pages(body, limit):
                return
            page += 1


def total_pages(body: dict[str, Any], limit: int) -> int:
    if isinstance(body.get("pagination"), dict):
        return int(body["pagination"].get("pages") or 1)
    if "totalPages" in body:
        return int(body["totalPages"])
    if "total" in body:
        return max(1, -(-int(body["total"]) // limit))
    return 1


def siweb_total(body: dict[str, Any]) -> int | None:
    """The row count Siweb reports, used for reconciliation."""
    if isinstance(body.get("pagination"), dict):
        return int(body["pagination"].get("total", 0))
    if "total" in body:
        return int(body["total"])
    return None


__all__ = ["API_PREFIX", "AuthExpiredError", "BudgetExhaustedError", "ReaderClient", "SiwebError", "siweb_total", "total_pages"]
