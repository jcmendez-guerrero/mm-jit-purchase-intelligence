"""MMI-7 T019: activating or rolling back a seed dataset needs a recent second factor, and the reason reaches the forecast service."""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from routes.api import get_inventory_client, get_procurement_client
from routes.policies import get_forecast_client
from tests_support import headers_for

BUYER = ["viewer", "buyer"]
DATASET = "5ba24d0e-5860-4dc0-baf2-caf0cb702742"


def call(method, path, headers, fc, **kw):
    from main import app

    app.dependency_overrides[get_forecast_client] = lambda: fc
    app.dependency_overrides[get_procurement_client] = lambda: AsyncMock()
    app.dependency_overrides[get_inventory_client] = lambda: AsyncMock()
    try:
        return TestClient(app).request(method, path, headers=headers, **kw)
    finally:
        app.dependency_overrides.clear()


def test_activation_and_rollback_are_refused_without_a_recent_second_factor_and_forward_nothing(role_store):
    for method, path in (("POST", f"/api/imports/{DATASET}/activate"), ("POST", "/api/imports/rollback")):
        fc = AsyncMock()
        res = call(method, path, headers_for("b", BUYER, mfa_age_seconds=1200), fc, json={"reason_code": "test"})
        assert res.status_code == 403 and res.json() == {"detail": "auth_mfa_stale"}
        fc.forward.assert_not_called()


def test_with_a_fresh_second_factor_the_reason_is_forwarded(role_store):
    fc = AsyncMock()
    fc.forward.return_value = {"status": "active"}
    body = {"reason_code": "only_person", "reason_detail": "Tienda con una sola persona", "acknowledge_duplicate": False}
    assert call("POST", f"/api/imports/{DATASET}/activate", headers_for("b", BUYER, mfa_age_seconds=30), fc, json={**body, "something_else": 1}).status_code == 200
    assert fc.forward.call_args.kwargs["json"] == body                                      # only the known fields go on
    fc.forward.reset_mock()
    assert call("POST", "/api/imports/rollback", headers_for("b", BUYER, mfa_age_seconds=30), fc, json={"reason_code": "wrong_figures", "reason_detail": "Cifras erróneas", "x": 1}).status_code == 200
    assert fc.forward.call_args.args[:2] == ("POST", "/imports/rollback") and fc.forward.call_args.kwargs["json"] == {"reason_code": "wrong_figures", "reason_detail": "Cifras erróneas"}
    fc.forward.reset_mock()
    assert call("POST", "/api/imports/rollback", headers_for("b", BUYER, mfa_age_seconds=30), fc, json={}).status_code == 200
    assert fc.forward.call_args.kwargs["json"] == {}                                        # a missing reason is for the forecast service to refuse


def test_a_viewer_is_still_refused_before_the_second_factor_matters(role_store):
    fc = AsyncMock()
    assert call("POST", "/api/imports/rollback", headers_for("v", ["viewer"], mfa_age_seconds=30), fc, json={"reason_code": "test"}).status_code == 403
    fc.forward.assert_not_called()
