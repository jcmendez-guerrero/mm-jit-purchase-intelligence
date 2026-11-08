"""T097: after an inventory load the loader refreshes the export costs in procurement (FR-037)."""

from __future__ import annotations

import json

import httpx
import pytest
from export_loader.push_costs import build_cost_rows, http_push_costs
from export_loader.service import LoaderService
from export_loader.validate_file import LoaderFileError
from generator.exports import write_exports


@pytest.fixture
def files(tmp_path):
    write_exports(tmp_path / "f", seed=42)
    return tmp_path / "f"


def load(svc, files):
    return svc.load("inventory", "inventario.csv", (files / "inventario.csv").read_bytes(), acknowledge_interpretation=True)


def test_rows_are_strings_for_physical_products_only(files, tmp_path):
    pushes: list[dict] = []
    seen: list[tuple[list, str]] = []
    svc = LoaderService(tmp_path / "s", pushes.append, push_costs=lambda rows, run: seen.append((rows, run)))
    result = load(svc, files)
    rows, run = seen[0]
    assert run == result["run_id"] and rows
    assert all(set(r) == {"sku", "export_cost", "pvp_gross", "tax_rate", "tax_included", "currency"} for r in rows)
    assert all(r["export_cost"] is None or isinstance(r["export_cost"], str) for r in rows)
    assert len(rows) == len({v["sku"] for v in pushes[-1]["variants"] if not v.get("is_service")})


def test_gross_price_follows_the_tax_flag():
    from decimal import Decimal

    from export_loader.parse_inventory import InventoryItem

    item = InventoryItem(sku="A", name="n", category="c", brand="b", supplier_name="", kind="physical", uom="u", uom_category="count",
                         price=Decimal("10.00"), cost=Decimal("4.00"), tax_kind="IVA21", tax_rate=Decimal("21"), tax_included=False,
                         pvp_gross=Decimal("12.10"), currency="EUR", status="active")
    row = build_cost_rows({"a": item})[0]
    assert row == {"sku": "A", "export_cost": "4.00", "pvp_gross": "12.10", "tax_rate": "21", "tax_included": False, "currency": "EUR"}


def test_a_failing_push_is_reported_not_swallowed(files, tmp_path):
    def boom(rows, run):
        raise httpx.ConnectError("down")

    svc = LoaderService(tmp_path / "s", lambda b: None, push_costs=boom)
    with pytest.raises(LoaderFileError) as exc:
        load(svc, files)
    assert exc.value.code == "local_load_platform_unreachable"


def test_without_a_target_nothing_is_pushed(files, tmp_path):
    assert load(LoaderService(tmp_path / "s", lambda b: None), files)["rows"] > 0


def test_http_push_sends_the_loader_token_and_the_body(monkeypatch):
    sent = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.update(url=str(request.url), auth=request.headers["authorization"], body=json.loads(request.content))
        return httpx.Response(200, json={"upserted": 1})

    monkeypatch.setattr("export_loader.push_costs.loader_token", lambda audience: f"tok-for-{audience}")
    push = http_push_costs("http://procurement-service:8000", transport=httpx.MockTransport(handler))
    push([{"sku": "A", "export_cost": "1.00"}], "run-1")
    assert sent["url"] == "http://procurement-service:8000/internal/export-costs" and sent["auth"] == "Bearer tok-for-api://mmi-procurement-service"
    assert sent["body"] == {"load_run_id": "run-1", "rows": [{"sku": "A", "export_cost": "1.00"}]}


def test_http_push_refuses_non_local_targets():
    from export_loader.guards import GuardError

    with pytest.raises(GuardError):
        http_push_costs("https://procurement.example.com")


def test_amounts_with_more_than_four_decimals_are_rounded_to_what_procurement_stores():
    from decimal import Decimal

    from export_loader.parse_inventory import InventoryItem

    item = InventoryItem(sku="A", name="n", category="c", brand="b", supplier_name="", kind="physical", uom="u", uom_category="count", price=Decimal("1"),
                         cost=Decimal("3.333333"), tax_kind="IVA", tax_rate=Decimal("10.12345"), tax_included=False, pvp_gross=Decimal("1.10"), currency="EUR", status="active")
    row = build_cost_rows({"a": item})[0]
    assert row["export_cost"] == "3.3333" and row["tax_rate"] == "10.1235" and row["pvp_gross"] == "1.10"


def test_a_refusal_from_the_platform_is_explained_without_echoing_any_value(tmp_path, files):
    def refuse(rows, run):
        req = httpx.Request("POST", "http://procurement-service:8000/internal/export-costs")
        body = {"detail": [{"type": "string_pattern_mismatch", "loc": ["body", "rows", 3, "export_cost"], "msg": "no", "input": "SECRETO-123"}]}
        raise httpx.HTTPStatusError("x", request=req, response=httpx.Response(422, request=req, json=body))

    with pytest.raises(LoaderFileError) as exc:
        LoaderService(tmp_path / "s", lambda b: None, push_costs=refuse).load("inventory", "i.csv", (files / "inventario.csv").read_bytes(), acknowledge_interpretation=True)
    text = str(exc.value)
    assert "422" in text and "export_cost" in text and "string_pattern_mismatch" in text and "SECRETO-123" not in text
