"""T062/T064: suppliers and the supplier names of the inventory export reach procurement through its internal API, in a safe order."""

from __future__ import annotations

import json

import httpx
import pytest
from export_loader import cli
from export_loader.parse_inventory import parse_inventory
from export_loader.parse_suppliers import parse_suppliers
from export_loader.service import LoaderService
from export_loader.to_procurement import build_link_rows, build_supplier_rows, http_push_links, http_push_suppliers
from export_loader.validate_file import Limits, LoaderFileError
from generator.exports import write_exports

LIMITS = Limits()


@pytest.fixture
def files(tmp_path):
    d = tmp_path / "f"
    write_exports(d, seed=42)
    return d


def sup_bytes(files):
    return (files / "proveedores.csv").read_bytes()


def test_supplier_rows_carry_only_what_procurement_accepts(files):
    rows = build_supplier_rows(parse_suppliers(sup_bytes(files), "p.csv", LIMITS))
    assert rows and all(set(r) == {"external_contact_id", "name", "fiscal_type", "country", "currency", "payment_terms_days", "terms_unparsed", "has_note"} for r in rows)
    assert all(isinstance(r["external_contact_id"], int) for r in rows)


def test_link_rows_come_only_from_physical_rows_that_name_a_supplier(files):
    inv = parse_inventory((files / "inventario.csv").read_bytes(), "i.csv", LIMITS)
    rows = build_link_rows(inv.items)
    named = [i for i in inv.items.values() if i.kind == "physical" and i.supplier_name]
    assert len(rows) == len(named) > 0 and all(set(r) == {"sku", "supplier_name"} for r in rows)


def test_loading_suppliers_reports_what_procurement_created_and_found(tmp_path, files):
    sent = []

    def push(rows, run_id):
        sent.append((rows, run_id))
        return {"created": len(rows) - 2, "existing": 2}

    svc = LoaderService(tmp_path / "s", lambda b: None, push_suppliers=push)
    r = svc.load("suppliers", "proveedores.csv", sup_bytes(files))
    assert (r["kind"], r["updated"], r["services"]) == ("suppliers", 0, 0)
    assert r["loaded"] + r["unchanged"] + r["quarantined"] + r["excluded"] == r["rows"] and r["unchanged"] == 2 and r["excluded"] == 3
    assert sent[0][1] == r["run_id"]


def test_without_a_target_every_parsed_supplier_counts_as_loaded(tmp_path, files):
    r = LoaderService(tmp_path / "s", lambda b: None).load("suppliers", "proveedores.csv", sup_bytes(files))
    assert r["unchanged"] == 0 and r["loaded"] == r["rows"] - r["excluded"] - r["quarantined"]


def test_check_changes_nothing_and_needs_no_target(tmp_path, files):
    calls = []
    svc = LoaderService(tmp_path / "s", lambda b: None, push_suppliers=lambda rows, run: calls.append(1) or {"created": 0, "existing": 0})
    r = svc.check("suppliers", "proveedores.csv", sup_bytes(files))
    assert r["rows"] > 0 and calls == [] and svc.runs() == []


def test_an_unreachable_platform_is_reported(tmp_path, files):
    def boom(rows, run):
        raise httpx.ConnectError("down")

    with pytest.raises(LoaderFileError) as exc:
        LoaderService(tmp_path / "s", lambda b: None, push_suppliers=boom).load("suppliers", "proveedores.csv", sup_bytes(files))
    assert exc.value.code == "local_load_platform_unreachable"


def test_the_inventory_load_links_after_the_costs_have_been_refreshed(tmp_path, files):
    order = []
    svc = LoaderService(tmp_path / "s", lambda b: order.append("mock"), push_costs=lambda rows, run: order.append("costs"),
                        push_links=lambda rows: order.append(f"links:{len(rows)}") or {"linked": len(rows)})
    svc.load("inventory", "i.csv", (files / "inventario.csv").read_bytes(), acknowledge_interpretation=True)
    assert order[0] == "mock" and order[1] == "costs" and order[2].startswith("links:") and int(order[2].split(":")[1]) > 0


def test_no_link_call_when_the_export_names_no_supplier(tmp_path, files):
    import csv
    import io

    text = (files / "inventario.csv").read_bytes().decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text, newline="")))
    for r in rows:
        r["Proveedor"] = ""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    calls = []
    svc = LoaderService(tmp_path / "s", lambda b: None, push_links=lambda rows: calls.append(1) or {})
    svc.load("inventory", "i.csv", buf.getvalue().encode(), acknowledge_interpretation=True)
    assert calls == []


def test_a_failing_link_push_is_reported(tmp_path, files):
    def boom(rows):
        raise httpx.ConnectError("down")

    with pytest.raises(LoaderFileError) as exc:
        LoaderService(tmp_path / "s", lambda b: None, push_links=boom).load("inventory", "i.csv", (files / "inventario.csv").read_bytes(), acknowledge_interpretation=True)
    assert exc.value.code == "local_load_platform_unreachable"


def test_http_pushes_send_the_loader_token_to_the_internal_routes(monkeypatch):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((str(request.url), request.headers["authorization"], json.loads(request.content)))
        return httpx.Response(200, json={"created": 1, "existing": 0, "linked": 1})

    monkeypatch.setattr("export_loader.to_procurement.loader_token", lambda audience: f"tok-{audience}")
    t = httpx.MockTransport(handler)
    assert http_push_suppliers("http://procurement-service:8000", transport=t)([{"external_contact_id": 1}], "run-1")["created"] == 1
    assert http_push_links("http://procurement-service:8000", transport=t)([{"sku": "A", "supplier_name": "B"}])["linked"] == 1
    assert seen[0][0].endswith("/internal/suppliers/import") and seen[0][1] == "Bearer tok-api://mmi-procurement-service" and seen[0][2]["load_run_id"] == "run-1"
    assert seen[1][0].endswith("/internal/links/auto") and seen[1][2] == {"rows": [{"sku": "A", "supplier_name": "B"}]}


def test_the_command_loads_suppliers_first(tmp_path, files, capsys):
    order = []
    svc_push = lambda b: order.append("mock")  # noqa: E731
    assert cli.main(["load", "--dir", str(files), "--accept-interpretation", "--no-sync"], push=svc_push, state_dir=tmp_path / "state") == 0
    out = capsys.readouterr().out
    assert out.index("suppliers:") < out.index("inventory:") < out.index("movements:")


def test_pushes_refuse_non_local_targets():
    from export_loader.guards import GuardError

    with pytest.raises(GuardError):
        http_push_suppliers("https://procurement.example.com")
    with pytest.raises(GuardError):
        http_push_links("https://procurement.example.com")
