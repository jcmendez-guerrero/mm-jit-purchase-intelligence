"""T156 (BFF part): every mutating route is closed to anonymous callers, to a missing or wrong CSRF token, and to a viewer.

The matrix is built from the application's own routes, so a new mutating endpoint is covered the day it is added; a route
that deliberately stays open must be added to OPEN below, with a reason.
"""

import re

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from tests_support import headers_for

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
OPEN = {("POST", "/api/auth/dev-login"): "development only, disabled in production (test_dev_login_disabled)"}


def flatten(routes, prefix=""):
    """Every APIRoute with its full path. FastAPI wraps included routers, so look inside them."""
    for r in routes:
        if isinstance(r, APIRoute):
            yield prefix + r.path, r
        elif hasattr(r, "original_router"):
            yield from flatten(r.original_router.routes, prefix + r.include_context.prefix)


def routes():
    from main import app

    return [(m, path, r) for path, r in flatten(app.routes) if path.startswith("/api") for m in r.methods & MUTATING if (m, path) not in OPEN]


def concrete(path):
    return re.sub(r"\{[^}]+\}", "5ba24d0e-5860-4dc0-baf2-caf0cb702742", path)


def uses_fresh_mfa(route):
    def walk(dep):
        for d in dep.dependencies:
            if getattr(d.call, "__qualname__", "").startswith("require_fresh_mfa"):
                return True
            if walk(d):
                return True
        return False

    return walk(route.dependant)


def send(method, path, headers=None):
    from main import app

    return TestClient(app).request(method, concrete(path), headers=headers, json={})


def test_there_are_mutating_routes_to_check(role_store):
    assert len(routes()) >= 25


def test_anonymous_callers_are_refused_everywhere(role_store):
    open_ = [(m, p) for m, p, _ in routes() if send(m, p).status_code != 401]
    assert not open_, f"reachable without a session: {open_}"


def test_a_session_without_the_csrf_token_is_refused_everywhere(role_store):
    h = headers_for("admin-1", ["viewer", "admin", "buyer", "approver"])
    no_csrf = {"Cookie": h["Cookie"]}
    wrong = {**no_csrf, "X-CSRF-Token": "not-the-token"}
    bad = [(m, p) for m, p, _ in routes() for hh in (no_csrf, wrong) if (res := send(m, p, hh)).status_code != 403 or res.json().get("detail") != "auth_csrf_invalid"]
    assert not bad, f"accepted without a valid CSRF token: {bad}"


def test_a_viewer_cannot_use_any_mutating_route(role_store):
    h = headers_for("viewer-1", ["viewer"])
    allowed = [(m, p) for m, p, _ in routes() if send(m, p, h).status_code != 403 and p != "/api/auth/logout"]
    assert not allowed, f"a viewer got through: {allowed}"


def test_routes_that_need_fresh_multi_factor_refuse_a_stale_sign_in(role_store):
    fresh = [(m, p, r) for m, p, r in routes() if uses_fresh_mfa(r)]
    assert len(fresh) >= 2                                              # proposal approval and the supplier-cost release at least
    h = headers_for("admin-1", ["viewer", "admin", "buyer", "approver"], mfa_age_seconds=3600)
    wrong = [(m, p) for m, p, _ in fresh if (res := send(m, p, h)).status_code != 403 or res.json().get("detail") != "auth_mfa_stale"]
    assert not wrong, f"stale multi-factor accepted: {wrong}"
