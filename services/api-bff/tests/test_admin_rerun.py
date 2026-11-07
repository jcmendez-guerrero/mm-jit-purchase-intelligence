"""T149: admin-only, idempotent re-runs, each audited with the actor."""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from routes.admin_roles import get_store
from routes.policies import get_forecast_client
from tests_support import admin_headers, headers_for


def post(path, headers, fc):
    from main import app

    app.dependency_overrides[get_forecast_client] = lambda: fc
    try:
        return TestClient(app).post(path, headers=headers)
    finally:
        app.dependency_overrides.clear()


def test_non_admins_are_refused_before_anything_is_called(role_store):
    fc = AsyncMock()
    for roles in (["viewer"], ["viewer", "buyer"], ["viewer", "approver"]):
        for path in ("/api/admin/rerun/forecast", "/api/admin/rerun/import/5ba24d0e-5860-4dc0-baf2-caf0cb702742", "/api/admin/rerun/mirror"):
            assert post(path, headers_for("u", roles), fc).status_code == 403
    fc.forward.assert_not_called()


def test_forecast_rerun_is_forwarded_as_the_admin_and_audited(role_store):
    fc = AsyncMock()
    fc.forward.return_value = {"run_id": "r1", "reused": True, "eligible": 3}
    res = post("/api/admin/rerun/forecast", admin_headers(), fc)
    assert res.status_code == 202 and res.json()["reused"] is True
    kw = fc.forward.call_args
    assert kw.args[:2] == ("POST", "/runs") and kw.kwargs["user_id"] == "admin-1"
    rows = [r for r in get_store().audit_view() if r["action"] == "admin.rerun"]
    assert len(rows) == 1 and rows[0]["actor"] == "admin-1" and rows[0]["target_user"] == "forecast"


def test_import_job_rerun_and_the_id_is_validated(role_store):
    fc = AsyncMock()
    fc.forward.return_value = {"job_id": "j2", "state": "queued", "reused": False}
    assert post("/api/admin/rerun/import/5ba24d0e-5860-4dc0-baf2-caf0cb702742", admin_headers(), fc).status_code == 202
    assert fc.forward.call_args.args[:2] == ("POST", "/imports/jobs/5ba24d0e-5860-4dc0-baf2-caf0cb702742/rerun")
    fc.reset_mock()
    assert post("/api/admin/rerun/import/..%2Fx%20y", admin_headers(), fc).status_code in (404, 422)
    fc.forward.assert_not_called()


def test_mirror_rerun_requeues_failed_rows_and_is_audited(role_store):
    res = post("/api/admin/rerun/mirror", admin_headers(), AsyncMock())
    assert res.status_code == 202 and "requeued" in res.json()
    assert any(r["action"] == "admin.rerun" and r["target_user"] == "mirror" for r in get_store().audit_view())
