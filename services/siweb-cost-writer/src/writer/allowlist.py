"""Closed outbound allowlist for the cost writer (constitution Principle I).

Exactly one write: PUT /api/public/inventory/products/{id}/suppliers/{contact_id}. The only read allowed is the supplier list of
a product, needed to read the record before changing it and to verify the result afterwards. Everything else is refused
before a request is built: other methods, other paths, other hosts, other schemes, redirects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit

API = "/api/public/inventory/products"
PUT_PATH = re.compile(rf"^{API}/[0-9]+/suppliers/[0-9]+$")
GET_PATH = re.compile(rf"^{API}/[0-9]+/suppliers$")


class AllowlistViolation(Exception):
    def __init__(self, reason: str, method: str, url: str) -> None:
        p = urlsplit(url)
        super().__init__(f"{reason}: {method} {p.scheme}://{p.hostname or ''}{p.path}")
        self.reason, self.method = reason, method


@dataclass
class WriterAllowlist:
    host: str
    allow_http: bool = False
    refusals: list[tuple[str, str]] = field(default_factory=list)

    def check(self, method: str, url: str) -> None:
        try:
            self._check(method.upper(), url)
        except AllowlistViolation as exc:
            self.refusals.append((exc.reason, exc.method))
            raise

    def _check(self, method: str, url: str) -> None:
        if method not in ("PUT", "GET"):
            raise AllowlistViolation("method_not_allowed", method, url)
        p = urlsplit(url)
        if p.scheme != "https" and not (self.allow_http and p.scheme == "http"):
            raise AllowlistViolation("scheme_not_allowed", method, url)
        if p.username or p.password or "@" in p.netloc:
            raise AllowlistViolation("credentials_in_url", method, url)
        if (p.hostname or "").lower() != self.host.lower():
            raise AllowlistViolation("host_not_allowed", method, url)
        if unquote(p.path) != p.path or ".." in p.path or "//" in p.path or "\\" in p.path:
            raise AllowlistViolation("path_not_normalised", method, url)
        if method == "PUT" and not PUT_PATH.match(p.path):
            raise AllowlistViolation("path_not_allowed", method, url)
        if method == "GET" and not GET_PATH.match(p.path):
            raise AllowlistViolation("path_not_allowed", method, url)
