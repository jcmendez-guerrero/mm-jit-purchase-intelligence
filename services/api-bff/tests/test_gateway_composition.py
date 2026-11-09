"""T046 (ADR-023): the gateway composes domain results and applies no business rules of its own."""

from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from routes.api import get_inventory_client, get_procurement_client
from routes.policies import get_forecast_client
from tests_support import headers_for

ROUTES = Path(__file__).resolve().parents[1] / "src" / "routes"
# admin_status.py only reads a configured budget estimate from the environment; it computes nothing.
NO_ARITHMETIC_EXEMPT = {"admin_status.py"}
SENTINELS = {"inventory_value": "99999.99", "trend": [{"day": "2026-01-01", "units": "7777"}]}


def contains(obj, needle) -> bool:
    if obj == needle:
        return True
    if isinstance(obj, dict):
        return any(contains(v, needle) for v in obj.values())
    if isinstance(obj, list):
        return any(contains(v, needle) for v in obj)
    return False


def test_routes_do_no_money_arithmetic():
    for f in sorted(ROUTES.glob("*.py")):
        if f.name in NO_ARITHMETIC_EXEMPT:
            continue
        text = f.read_text(encoding="utf-8")
        for token in ("Decimal", "float(", "round("):
            assert token not in text, f"{f.name} uses {token}: business arithmetic belongs to the domain service"


def test_overview_returns_domain_values_verbatim_and_each_domain_sees_only_its_own_paths(role_store):
    from main import app

    inv, proc, fc = AsyncMock(), AsyncMock(), AsyncMock()
    proc.forward.return_value = []
    fc.forward.return_value = {"metrics": {}}

    async def inventory_forward(method, path, **kw):
        return {"/dashboard/summary": {"inventory_value": SENTINELS["inventory_value"]},
                "/dashboard/demand-trend": {"series": SENTINELS["trend"]}}.get(path, {})

    inv.forward.side_effect = inventory_forward
    app.dependency_overrides[get_inventory_client] = lambda: inv
    app.dependency_overrides[get_procurement_client] = lambda: proc
    app.dependency_overrides[get_forecast_client] = lambda: fc
    try:
        res = TestClient(app).get("/api/dashboard/overview", headers=headers_for("v", ["viewer"]))
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    body = res.json()
    assert contains(body, SENTINELS["inventory_value"]) and contains(body, SENTINELS["trend"][0]["units"])
    inventory_paths = [c.args[1] for c in inv.forward.call_args_list]
    assert "/dashboard/summary" in inventory_paths
    assert not any(c.args[1].startswith("/dashboard") for c in proc.forward.call_args_list)
