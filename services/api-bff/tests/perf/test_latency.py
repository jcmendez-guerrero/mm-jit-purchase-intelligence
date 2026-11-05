"""T144: Performance test: key API pages respond within target latency (< 500ms)."""

import time
from unittest.mock import AsyncMock

from auth.session import COOKIE_NAME, create_session, sign_session
from fastapi.testclient import TestClient
from main import app
from routes.api import get_inventory_client


def test_api_latency_under_target():
    client = TestClient(app)
    sess = create_session("buyer-1", "buyer@example.com", ["viewer", "buyer"])
    headers = {"Cookie": f"{COOKIE_NAME}={sign_session(sess)}", "X-CSRF-Token": sess.csrf_token}

    mock_inv = AsyncMock()
    mock_inv.get_risks.return_value = [{"variant_id": 1, "risk_type": "stockout", "explanation_key": "risk.stockout.imminent"}]
    mock_inv.get_variant_detail.return_value = {"variant": {"id": 1, "sku": "AMX-500"}}
    app.dependency_overrides[get_inventory_client] = lambda: mock_inv

    try:
        # Measure /api/me
        start = time.perf_counter()
        res_me = client.get("/api/me", headers=headers)
        me_time = time.perf_counter() - start
        assert res_me.status_code == 200
        assert me_time < 0.5, f"/api/me took {me_time:.3f}s"

        # Measure /api/dashboard/risk
        start = time.perf_counter()
        res_risk = client.get("/api/dashboard/risk", headers=headers)
        risk_time = time.perf_counter() - start
        assert res_risk.status_code == 200
        assert risk_time < 0.5, f"/api/dashboard/risk took {risk_time:.3f}s"
    finally:
        app.dependency_overrides.clear()
