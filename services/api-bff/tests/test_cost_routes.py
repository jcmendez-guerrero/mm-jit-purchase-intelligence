"""T064: cost-update routes - roles, fresh MFA for the release, admin-only override, identity forwarded."""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from routes.api import get_procurement_client
from tests_support import headers_for

BUYER = ["viewer", "buyer"]


def call(method, path, headers, mock, **kw):
    from main import app

    app.dependency_overrides[get_procurement_client] = lambda: mock
    try:
        return TestClient(app).request(method, path, headers=headers, **kw)
    finally:
        app.dependency_overrides.clear()


def test_only_a_buyer_enters_lot_costs_and_requests_updates(role_store):
    mock = AsyncMock()
    mock.add_lot_cost.return_value = {"id": "x"}
    body = {"variant_id": 1, "supplier_id": "s", "lot": "opening", "amount": "1", "includes_recargo": True, "source": "buyer_entry"}
    for roles in (["viewer"], ["viewer", "admin"], ["viewer", "approver"]):
        assert call("POST", "/api/lot-costs", headers_for("u", roles), mock, json=body).status_code == 403
        assert call("POST", "/api/cost-updates", headers_for("u", roles), mock, json={"product_id": 1, "supplier_id": "s"}).status_code == 403
    mock.add_lot_cost.assert_not_called()
    ok = call("POST", "/api/lot-costs", headers_for("buyer-1", BUYER), mock, json=body)
    assert ok.status_code == 201 and mock.add_lot_cost.call_args.kwargs["user_id"] == "buyer-1"


def test_release_needs_the_buyer_role_and_a_fresh_second_factor(role_store):
    mock = AsyncMock()
    mock.approve_cost_write.return_value = {"status": "approved_by_buyer"}
    assert call("POST", "/api/cost-writes/w1/approve", headers_for("a", ["viewer", "approver"], mfa_age_seconds=10), mock).json() == {"detail": "auth_forbidden_role"}
    stale = call("POST", "/api/cost-writes/w1/approve", headers_for("buyer-1", BUYER, mfa_age_seconds=1200), mock)
    assert stale.status_code == 403 and stale.json() == {"detail": "auth_mfa_stale"}
    mock.approve_cost_write.assert_not_called()
    ok = call("POST", "/api/cost-writes/w1/approve", headers_for("buyer-1", BUYER, mfa_age_seconds=10), mock)
    assert ok.status_code == 200 and mock.approve_cost_write.call_args.kwargs["user_id"] == "buyer-1"


def test_only_an_admin_can_override_and_the_value_and_reason_are_validated(role_store):
    mock = AsyncMock()
    mock.override_cost_write.return_value = {"status": "pending_review"}
    body = {"value": "8.50", "reason": "oferta del proveedor"}
    for roles in (BUYER, ["viewer", "approver"], ["viewer"]):
        assert call("POST", "/api/cost-writes/w1/override", headers_for("u", roles), mock, json=body).status_code == 403
    admin = headers_for("admin-1", ["viewer", "admin"])
    for bad in ({"value": "-1", "reason": "x"}, {"value": "abc", "reason": "x"}, {"value": "1", "reason": ""}, {"value": "1.23456", "reason": "x"}):
        assert call("POST", "/api/cost-writes/w1/override", admin, mock, json=bad).status_code == 422
    assert call("POST", "/api/cost-writes/w1/override", admin, mock, json=body).status_code == 200
    kw = mock.override_cost_write.call_args
    assert kw.kwargs["user_id"] == "admin-1" and kw.args[1] == body
