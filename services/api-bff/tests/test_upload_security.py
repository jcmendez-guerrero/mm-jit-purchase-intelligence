"""T097 (BFF side): role, CSRF, size caps and type allow-list are enforced before anything is forwarded."""

import io
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from routes.api import get_inventory_client, get_procurement_client
from routes.policies import get_forecast_client
from tests_support import headers_for

BUYER = ["viewer", "buyer"]
CSV = b"ID de variante Siweb;Fecha;Cantidad\n9001;2026-01-05;2\n"


def call(method, path, headers, fc=None, **kw):
    from main import app

    app.dependency_overrides[get_forecast_client] = lambda: fc or AsyncMock()
    app.dependency_overrides[get_procurement_client] = lambda: AsyncMock()
    app.dependency_overrides[get_inventory_client] = lambda: AsyncMock()
    try:
        return TestClient(app).request(method, path, headers=headers, **kw)
    finally:
        app.dependency_overrides.clear()


def files(name="datos.csv", data=CSV):
    return {"file": (name, io.BytesIO(data), "text/csv")}


def forwarder(payload=None):
    fc = AsyncMock()
    res = MagicMock()
    res.json.return_value = payload or {"id": "d1"}
    fc.forward_raw.return_value = res
    return fc


def test_only_buyers_and_admins_can_upload_and_the_refusal_forwards_nothing(role_store):
    for roles in (["viewer"], ["viewer", "approver"]):
        fc = forwarder()
        assert call("POST", "/api/imports", headers_for("u", roles), fc, files=files()).status_code == 403
        fc.forward_raw.assert_not_called()
    assert call("POST", "/api/imports", headers_for("b", BUYER), forwarder(), files=files()).status_code == 201
    assert call("POST", "/api/imports", headers_for("a", ["viewer", "admin"]), forwarder(), files=files()).status_code == 201


def test_a_state_changing_import_request_without_the_csrf_token_is_refused(role_store):
    h = headers_for("b", BUYER)
    h.pop("X-CSRF-Token")
    fc = forwarder()
    res = call("POST", "/api/imports", h, fc, files=files())
    assert res.status_code == 403 and res.json() == {"detail": "auth_csrf_invalid"}
    fc.forward_raw.assert_not_called()


def test_the_extension_allow_list_is_enforced_before_forwarding(role_store):
    for name in ("datos.xlsm", "datos.pdf", "datos.exe", "datos"):
        fc = forwarder()
        res = call("POST", "/api/imports", headers_for("b", BUYER), fc, files=files(name))
        assert res.status_code == 415 and res.json() == {"detail": "import_type_not_allowed"}, name
        fc.forward_raw.assert_not_called()


def test_an_oversized_file_is_refused_by_the_declared_and_by_the_actual_size(role_store, monkeypatch):
    monkeypatch.setenv("MMI_UPLOAD_MAX_BYTES", "1000")
    fc = forwarder()
    big = b"x" * 5000
    res = call("POST", "/api/imports", {**headers_for("b", BUYER), "Content-Length": str(10 * 1024 * 1024)}, fc, files=files(data=big))
    assert res.status_code == 413 and res.json() == {"detail": "import_file_too_large"}
    res2 = call("POST", "/api/imports", headers_for("b", BUYER), fc, files=files(data=big))
    assert res2.status_code == 413
    fc.forward_raw.assert_not_called()


def test_a_valid_file_is_forwarded_with_the_user_and_the_original_bytes(role_store):
    fc = forwarder({"id": "d1", "status": "uploaded"})
    res = call("POST", "/api/imports", headers_for("buyer-1", BUYER), fc, files=files(), data={"name": "Hoja"})
    assert res.json() == {"id": "d1", "status": "uploaded"}
    args, kw = fc.forward_raw.call_args
    assert args == ("POST", "/imports") and kw["user_id"] == "buyer-1" and kw["files"]["file"][1] == CSV and kw["data"] == {"name": "Hoja"}


def test_lifecycle_actions_need_buyer_or_admin_and_reads_do_not(role_store):
    for method, path in (("POST", "/api/imports/d1/validate"), ("POST", "/api/imports/d1/dry-run"), ("POST", "/api/imports/d1/activate"), ("POST", "/api/imports/rollback"),
                         ("POST", "/api/imports/d1/reject"), ("POST", "/api/imports/mappings")):
        fc = AsyncMock()
        assert call(method, path, headers_for("v", ["viewer"]), fc, json={}).status_code == 403, path
        assert not fc.forward.called
    fc = AsyncMock()
    fc.forward.return_value = {"datasets": []}
    assert call("GET", "/api/imports", headers_for("v", ["viewer"]), fc).json() == {"datasets": []}


def test_downloads_pass_through_with_their_content_type(role_store):
    fc = AsyncMock()
    res = MagicMock()
    res.content, res.headers = b"a;b\n", {"content-type": "text/csv; charset=utf-8", "content-disposition": 'attachment; filename="plantilla.csv"'}
    fc.forward_raw.return_value = res
    out = call("GET", "/api/imports/template?format=csv", headers_for("v", ["viewer"]), fc)
    assert out.content == b"a;b\n" and out.headers["content-type"].startswith("text/csv") and "plantilla.csv" in out.headers["content-disposition"]
