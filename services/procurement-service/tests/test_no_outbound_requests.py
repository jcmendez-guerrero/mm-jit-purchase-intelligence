"""T023 (FR-011, SC-004): generating, editing, scenarios, promotion, submission, approval and export open no connection and send no request (no supplier order, no ERP call)."""

from __future__ import annotations

from conftest import NOW
from proposal_support import generate, h
from scen import Blob, base, suppliers
from scenarios import store as sc
from scenarios.engine import ScenarioParams


def test_the_whole_proposal_path_makes_no_outbound_request(api, outbound):
    c, _ = api
    pid = generate(c)
    line = c.get(f"/proposals/{pid}", headers=h("viewer")).json()["lines"][0]
    assert c.patch(f"/proposals/{pid}/lines/{line['id']}", json={"qty": line["qty"] + 6}, headers=h("buyer2", **{"If-Match": "1"})).status_code == 200
    assert c.post(f"/proposals/{pid}/submit", headers=h("buyer")).status_code == 200
    assert c.post(f"/proposals/{pid}/approve", headers=h("approver")).status_code == 200
    assert c.get(f"/proposals/{pid}/export?format=csv", headers=h("buyer")).status_code == 200
    assert c.get(f"/proposals/{pid}/export?format=xlsx", headers=h("admin")).status_code == 200
    assert outbound == []


def test_the_scenario_path_makes_no_outbound_request(conn, tmp_path, outbound):
    sa, sb = suppliers(conn)
    out = sc.create(conn, Blob(tmp_path), "Sin A", ScenarioParams(disabled_suppliers=(sa,)), base(sa, sb), "buyer-1", "k-out-00001", NOW)
    sc.export(conn, out["id"], "csv")
    sc.promote(conn, out["id"], base(sa, sb), "buyer-2", "2026-W46", NOW)
    assert outbound == []


def test_the_guard_itself_records_an_attempt(outbound):
    import httpx
    import pytest

    with pytest.raises(httpx.ConnectError):
        httpx.Client().get("https://example.invalid/x")
    assert outbound and outbound[0].startswith("http:GET")
