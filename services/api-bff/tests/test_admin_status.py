"""T148: the admin status gathers freshness, import jobs, model runs, policy history and mirror lag; one failing source degrades alone."""

from unittest.mock import AsyncMock

import httpx
from fastapi.testclient import TestClient
from routes.api import get_inventory_client, get_procurement_client
from routes.policies import get_forecast_client
from tests_support import admin_headers, headers_for


def clients(inv=None, fc=None, proc=None):
    i, f, p = AsyncMock(), AsyncMock(), AsyncMock()
    i.forward.return_value = inv if inv is not None else {"stock_snapshots": {"latest_day": "2026-11-03", "rows": 4}, "movements": {"rows": 9, "quarantined": 1, "latest_at": "2026-11-03T09:00:00+00:00"},
                                                          "aggregates": {"refreshed_at": "2026-11-03T10:00:00+00:00"}}

    async def fwd(method, path, **kw):
        if path == "/imports/jobs":
            return {"jobs": [{"id": "j1", "state": "failed", "error_key": "import_failed"}], "background_over_rows": 10000}
        if path == "/runs":
            return {"runs": [{"id": "r1", "status": "completed", "through_day": "2026-11-02"}]}
        raise AssertionError(path)

    f.forward.side_effect = fc if fc is not None else fwd
    p.forward.return_value = proc if proc is not None else [{"id": "o1", "status": "approved", "variant_id": 9001}]
    return i, f, p


def get(headers, i, f, p):
    from main import app

    app.dependency_overrides.update({get_inventory_client: lambda: i, get_forecast_client: lambda: f, get_procurement_client: lambda: p})
    try:
        return TestClient(app).get("/api/admin/status", headers=headers)
    finally:
        app.dependency_overrides.clear()


def test_admin_sees_every_section(role_store):
    res = get(admin_headers(), *clients())
    assert res.status_code == 200
    body = res.json()
    assert body["freshness"]["data"]["movements"]["quarantined"] == 1
    assert body["import_jobs"]["data"]["jobs"][0]["error_key"] == "import_failed"
    assert body["model_runs"]["data"]["runs"][0]["id"] == "r1"
    assert body["policy_history"]["data"][0]["id"] == "o1"
    assert body["role_mirror"]["data"] == {"pending": 0, "failed": 0, "sent": 5, "oldest_pending_seconds": 0, "items": []} or body["role_mirror"]["ok"] is True
    assert "cost" in body and body["cost"]["budget_eur"] == 120


def test_a_failing_source_degrades_alone(role_store):
    async def boom(method, path, **kw):
        raise httpx.ConnectError("down")

    res = get(admin_headers(), *clients(fc=boom))
    body = res.json()
    assert body["import_jobs"] == {"ok": False, "error": "downstream_unavailable"} and body["model_runs"]["ok"] is False
    assert body["freshness"]["ok"] is True and body["policy_history"]["ok"] is True


def test_only_admins_see_the_status(role_store):
    for roles in (["viewer"], ["viewer", "buyer"], ["viewer", "approver"]):
        i, f, p = clients()
        assert get(headers_for("u", roles), i, f, p).status_code == 403
        i.forward.assert_not_called()
