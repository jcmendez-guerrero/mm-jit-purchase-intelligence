"""T062: suppliers and supplier names reach procurement through its own internal API (never its database), with the loader's service identity.

Only what the platform keeps is sent: the ERP contact number, name, fiscal type, country, currency, payment days, and flags. Tax ids, bank
data, contacts, addresses and notes were dropped at parse time.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

from . import guards
from .auth import loader_token
from .parse_inventory import InventoryItem
from .parse_suppliers import SupplierParse

AUDIENCE = "api://mmi-procurement-service"
PushSuppliers = Callable[[list[dict[str, Any]], str], dict[str, int]]
PushLinks = Callable[[list[dict[str, str]]], dict[str, int]]
CHUNK = 2000


def build_supplier_rows(parse: SupplierParse) -> list[dict[str, Any]]:
    return [{"external_contact_id": s.external_id, "name": s.name, "fiscal_type": s.fiscal_type, "country": s.country, "currency": s.currency,
             "payment_terms_days": s.payment_terms_days, "terms_unparsed": s.terms_unparsed, "has_note": s.has_note} for s in parse.suppliers]


def build_link_rows(items: dict[str, InventoryItem]) -> list[dict[str, str]]:
    return [{"sku": i.sku, "supplier_name": i.supplier_name} for i in items.values() if i.kind == "physical" and i.supplier_name.strip()]


def _post(url: str, path: str, body: dict[str, Any], transport: httpx.BaseTransport | None) -> dict[str, int]:
    with httpx.Client(transport=transport, timeout=120) as client:
        r = client.post(f"{url}{path}", json=body, headers={"Authorization": f"Bearer {loader_token(AUDIENCE)}"})
        r.raise_for_status()
        return {k: int(v) for k, v in r.json().items()}


def http_push_suppliers(procurement_url: str, transport: httpx.BaseTransport | None = None) -> PushSuppliers:
    url = guards.check_local_url(procurement_url).rstrip("/")

    def push(rows: list[dict[str, Any]], run_id: str) -> dict[str, int]:
        total: dict[str, int] = {}
        for start in range(0, max(len(rows), 1), CHUNK):
            for k, v in _post(url, "/internal/suppliers/import", {"load_run_id": run_id, "rows": rows[start:start + CHUNK]}, transport).items():
                total[k] = total.get(k, 0) + v
        return total

    return push


def http_push_links(procurement_url: str, transport: httpx.BaseTransport | None = None) -> PushLinks:
    url = guards.check_local_url(procurement_url).rstrip("/")

    def push(rows: list[dict[str, str]]) -> dict[str, int]:
        total: dict[str, int] = {}
        for start in range(0, max(len(rows), 1), CHUNK):
            for k, v in _post(url, "/internal/links/auto", {"rows": rows[start:start + CHUNK]}, transport).items():
                total[k] = total.get(k, 0) + v
        return total

    return push
