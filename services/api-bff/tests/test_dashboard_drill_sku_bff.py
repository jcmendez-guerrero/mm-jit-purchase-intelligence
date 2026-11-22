"""Feature 014 (T026, US3): the gateway checks the shape of the new drill-down kinds and the SKU route and forwards; the rules stay in inventory."""

import json
from pathlib import Path

import jsonschema
from test_dashboard_orchestration import call, inventory
from tests_support import headers_for

V2 = json.loads((Path(__file__).resolve().parents[3] / "packages" / "contracts" / "dto" / "dashboard_drilldown.v2.schema.json").read_text(encoding="utf-8"))


def test_the_drilldown_the_browser_receives_has_no_internal_id_and_matches_the_v2_contract(role_store):
    page = {"kind": "demand", "truncated": False, "total": 1, "offset": 0, "sum": "3.00", "rows": [{"variant_id": 7, "sku": "SYN-007", "name": "Sintético", "figure": "3.00"}]}
    res = call("/api/dashboard/drilldown?kind=demand", headers_for("v", ["viewer"]), inventory(**{"/dashboard/drilldown": page}))
    assert res.status_code == 200 and "variant_id" not in res.text
    jsonschema.validate(res.json(), V2, cls=jsonschema.Draft202012Validator)


def test_the_new_drilldown_kinds_and_their_parameters_are_forwarded(role_store):
    inv = inventory(**{"/dashboard/drilldown": {"rows": [], "total": 0}})
    res = call("/api/dashboard/drilldown?kind=demand&date_from=2026-09-11&date_to=2026-11-09", headers_for("v", ["viewer"]), inv)
    assert res.status_code == 200 and inv.forward.call_args.kwargs["params"] == {"kind": "demand", "date_from": "2026-09-11", "date_to": "2026-11-09"}
    res = call("/api/dashboard/drilldown?kind=expiry_band&band=d0_30", headers_for("v", ["viewer"]), inv)
    assert res.status_code == 200 and inv.forward.call_args.kwargs["params"] == {"kind": "expiry_band", "band": "d0_30"}
    for kind in ("forecast", "capital"):
        assert call(f"/api/dashboard/drilldown?kind={kind}", headers_for("v", ["viewer"]), inv).status_code == 200


def test_a_bad_kind_band_or_date_is_refused_before_inventory_is_called(role_store):
    inv = inventory()
    for bad in ("kind=budget", "kind=expiry_band&band=soon", "kind=demand&date_from=yesterday", "kind=demand&date_to=2026-13-40"):
        assert call("/api/dashboard/drilldown?" + bad, headers_for("v", ["viewer"]), inv).status_code == 422, bad
    inv.forward.assert_not_called()


def test_the_sku_page_is_forwarded_for_the_signed_in_user_and_a_bad_sku_is_refused(role_store):
    inv = inventory(**{"/dashboard/skus/SYN-001": {"sku": "SYN-001"}})
    res = call("/api/dashboard/skus/SYN-001", headers_for("v", ["viewer"]), inv)
    assert res.status_code == 200 and res.json() == {"sku": "SYN-001"}
    assert inv.forward.call_args.args[:2] == ("GET", "/dashboard/skus/SYN-001") and inv.forward.call_args.kwargs["user_id"] == "v"
    inv.reset_mock()
    for bad in ("a%20b", "x%3Bdrop"):
        assert call(f"/api/dashboard/skus/{bad}", headers_for("v", ["viewer"]), inv).status_code == 422, bad
    inv.forward.assert_not_called()
    assert call("/api/dashboard/skus/SYN-001", {}, inv).status_code == 401


def test_the_charts_request_is_forwarded_with_its_filters_for_the_signed_in_user(role_store):
    inv = inventory(**{"/dashboard/charts": {"charts": []}})
    res = call("/api/dashboard/charts?keys=expiry_bands,coverage_buckets&supplier_id=sup-a&date_from=2026-09-11&warehouse_id=2", headers_for("v", ["viewer"]), inv)
    assert res.status_code == 200 and res.json() == {"charts": []}
    assert inv.forward.call_args.args[:2] == ("GET", "/dashboard/charts") and inv.forward.call_args.kwargs["user_id"] == "v"
    assert inv.forward.call_args.kwargs["params"] == {"keys": "expiry_bands,coverage_buckets", "date_from": "2026-09-11", "warehouse_id": 2, "supplier_id": "sup-a"}
    assert call("/api/dashboard/charts", headers_for("v", ["viewer"]), inv).status_code == 200


def test_a_bad_chart_request_is_refused_before_inventory_is_called(role_store):
    inv = inventory()
    for bad in ("keys=Expiry;drop", "keys=", "category=Z", "supplier_id=a%20b", "date_to=soon", "warehouse_id=-1"):
        assert call("/api/dashboard/charts?" + bad, headers_for("v", ["viewer"]), inv).status_code == 422, bad
    inv.forward.assert_not_called()
    assert call("/api/dashboard/charts", {}, inv).status_code == 401
