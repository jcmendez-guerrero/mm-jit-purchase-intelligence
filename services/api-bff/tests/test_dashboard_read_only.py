"""Feature 014 (T053, 006 FR-020, constitution I): the dashboard is read-only. Every dashboard route accepts GET only, and no dashboard code path can reach the ERP or write purchasing state."""

import re
from pathlib import Path

from fastapi.testclient import TestClient
from tests_support import headers_for

SRC = Path(__file__).resolve().parents[1] / "src" / "routes" / "dashboard.py"


HTTP = ("get", "post", "put", "patch", "delete")


def dashboard_operations():
    """(method, path) of every dashboard operation the gateway really exposes."""
    from main import app

    return [(method, path) for path, ops in app.openapi()["paths"].items() if path.startswith("/api/dashboard") for method in ops if method in HTTP]


def test_there_are_dashboard_routes_and_each_one_accepts_get_only():
    ops = dashboard_operations()
    assert len(ops) >= 8
    assert {m for m, _p in ops} == {"get"}, [o for o in ops if o[0] != "get"]


def test_a_write_verb_on_a_dashboard_route_is_refused(role_store):
    from main import app

    client = TestClient(app)
    headers = headers_for("buyer-1", ["buyer"])
    for path in ("/api/dashboard/overview", "/api/dashboard/export?kind=cards", "/api/dashboard/charts", "/api/dashboard/skus/SYN-001", "/api/dashboard/freshness"):
        for verb in ("post", "put", "patch", "delete"):
            assert getattr(client, verb)(path, headers=headers).status_code in (401, 403, 405), (verb, path)


def test_the_dashboard_routes_make_only_read_calls_and_never_name_the_erp_or_a_purchasing_write():
    code = SRC.read_text(encoding="utf-8")
    assert not re.search(r"forward\(\s*[\"'](POST|PUT|PATCH|DELETE)", code), "a dashboard route forwards a write"
    assert not re.search(r"\.(post|put|patch|delete)\(", code), "a dashboard route calls a write method"
    for forbidden in ("siweb", "cost-writer", "cost_writer", "confirm_order", "/orders", "/proposals/"):
        assert forbidden not in code.lower(), f"the dashboard routes mention {forbidden}"
    assert not re.search(r"\bapprove\b", code.lower()), "the dashboard routes mention approving"
