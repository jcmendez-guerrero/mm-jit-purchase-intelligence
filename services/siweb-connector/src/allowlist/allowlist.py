"""Closed outbound allowlist for the Siweb reader (constitution Principle I).

Enforced before any request is built. Only GET on the paths below, only to the single approved host,
over HTTPS (HTTP only when explicitly enabled for the local mock). Everything else raises
``AllowlistViolation``; callers log it as a security event and count it.
Source of truth: specs/001-mmi-purchase-intelligence/contracts/siweb-allowlist.md (reader section).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit

API_PREFIX = "/api/public"

_ID = r"[0-9]+"
READER_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(f"^{API_PREFIX}{p}$")
    for p in (
        r"/inventory/warehouses",
        r"/inventory/products",
        rf"/inventory/products/{_ID}",
        rf"/inventory/products/{_ID}/suppliers",
        r"/inventory/variants",
        rf"/inventory/variants/{_ID}",
        rf"/inventory/variants/{_ID}/stock",
        rf"/inventory/variants/{_ID}/lots",
        r"/inventory/movements",
        rf"/inventory/variants/{_ID}/movements",
        r"/purchases",
        rf"/purchases/{_ID}",
    )
)


class AllowlistViolation(Exception):
    def __init__(self, reason: str, method: str, url: str) -> None:
        super().__init__(f"{reason}: {method} {_safe(url)}")
        self.reason, self.method, self.url = reason, method, _safe(url)


def _safe(url: str) -> str:
    """Never echo query strings or credentials into logs."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.hostname or ''}{parts.path}"


@dataclass
class Allowlist:
    host: str
    allow_http: bool = False
    refusals: list[tuple[str, str, str]] = field(default_factory=list)  # (reason, method, safe url) for metrics

    def check(self, method: str, url: str) -> None:
        try:
            self._check(method, url)
        except AllowlistViolation as exc:
            self.refusals.append((exc.reason, exc.method, exc.url))
            raise

    def _check(self, method: str, url: str) -> None:
        if method.upper() != "GET":
            raise AllowlistViolation("method_not_allowed", method, url)
        parts = urlsplit(url)
        if parts.scheme != "https" and not (self.allow_http and parts.scheme == "http"):
            raise AllowlistViolation("scheme_not_allowed", method, url)
        if parts.username or parts.password or "@" in parts.netloc:
            raise AllowlistViolation("credentials_in_url", method, url)
        if (parts.hostname or "").lower() != self.host.lower():
            raise AllowlistViolation("host_not_allowed", method, url)
        path = parts.path
        decoded = unquote(path)
        if decoded != path or ".." in decoded or "//" in decoded or "\\" in decoded:
            raise AllowlistViolation("path_not_normalised", method, url)
        if not any(p.match(path) for p in READER_PATTERNS):
            raise AllowlistViolation("path_not_allowed", method, url)
