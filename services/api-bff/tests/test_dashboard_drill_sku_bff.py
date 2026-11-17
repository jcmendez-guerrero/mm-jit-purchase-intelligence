"""Feature 014 (T026, US3): the gateway checks the shape of the new drill-down kinds and the SKU route and forwards; the rules stay in inventory."""

from test_dashboard_orchestration import call, inventory
from tests_support import headers_for


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
