"""MMI-7 T012: a viewer is refused on every changing import action, nothing is forwarded, and each refusal is recorded."""

import io
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from routes import rbac
from routes.api import get_inventory_client, get_procurement_client
from routes.policies import get_forecast_client
from tests_support import headers_for

DATASET = "5ba24d0e-5860-4dc0-baf2-caf0cb702742"
ACTIONS = [
    ("POST", "/api/imports", {"files": {"file": ("datos.csv", io.BytesIO(b"SKU;Fecha\n"), "text/csv")}}),
    ("POST", "/api/imports/mappings", {"json": {"name": "x", "column_map": {"Fecha": "day"}}}),
    ("POST", f"/api/imports/{DATASET}/validate", {"json": {"column_map": {"Fecha": "day"}}}),
    ("POST", f"/api/imports/{DATASET}/dry-run", {}),
    ("POST", f"/api/imports/{DATASET}/activate", {"json": {}}),
    ("POST", f"/api/imports/{DATASET}/reject", {}),
    ("POST", "/api/imports/rollback", {"json": {"reason_code": "test"}}),
]


def call(method, path, headers, fc, **kw):
    from main import app

    app.dependency_overrides[get_forecast_client] = lambda: fc
    app.dependency_overrides[get_procurement_client] = lambda: AsyncMock()
    app.dependency_overrides[get_inventory_client] = lambda: AsyncMock()
    try:
        return TestClient(app).request(method, path, headers=headers, **kw)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("method,path,kw", ACTIONS, ids=[a[1].replace(DATASET, "{id}") for a in ACTIONS])
def test_a_viewer_is_refused_forwards_nothing_and_the_refusal_is_recorded(role_store, method, path, kw):
    rbac.clear_refusal_log()
    fc = AsyncMock()
    res = call(method, path, headers_for("viewer-1", ["viewer"], mfa_age_seconds=10), fc, **kw)
    assert res.status_code == 403 and res.json() == {"detail": "auth_forbidden_role"}
    fc.forward.assert_not_called()
    fc.forward_raw.assert_not_called()
    assert [(e["user_id"], e["path"], e["reason"]) for e in rbac._refusal_log] == [("viewer-1", path, "forbidden_missing_role")]


def test_a_buyer_reaches_the_forecast_service_on_the_same_actions(role_store):
    fc = AsyncMock()
    fc.forward.return_value = {"ok": True}
    res = call("POST", f"/api/imports/{DATASET}/dry-run", headers_for("buyer-1", ["viewer", "buyer"], mfa_age_seconds=10), fc, json={})
    assert res.status_code == 200 and fc.forward.call_count == 1
