"""T012: every route that changes suppliers, terms, overrides, links or bulk assignment refuses viewers (403) and anonymous callers (401).

The routes are discovered from the application, so a change route added later without a role check fails here (FR-027).
"""

from __future__ import annotations

import re

import pytest
from api import costs
from api.suppliers import build_router
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app

ROLES = {"viewer": {"viewer"}, "buyer": {"viewer", "buyer"}, "admin": {"viewer", "admin"}}
CHANGE = {"POST", "PUT", "PATCH", "DELETE"}
FAMILIES = ("/suppliers", "/product-suppliers", "/links")


class Validator:
    def validate(self, token, required_roles=()):
        roles = ROLES.get(token, set())
        if not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        return Principal(subject=f"user-{token}", roles=frozenset(roles), auth_time=None)


@pytest.fixture
def app(engine):
    application = create_service_app("procurement-service", validator=Validator())
    application.include_router(costs.build_router(application))
    application.include_router(build_router(application))
    application.dependency_overrides[costs.get_engine] = lambda: engine
    return application


def flat(routes):
    """FastAPI wraps included routers; walk into them so no route is missed."""
    for route in routes:
        if type(route).__name__ == "_IncludedRouter":
            yield from flat(route.original_router.routes)
        else:
            yield route


def change_routes(application):
    found = []
    for route in flat(application.routes):
        if isinstance(route, APIRoute) and route.path.startswith(FAMILIES):
            for method in sorted(route.methods & CHANGE):
                found.append((method, route.path))
    return found


def concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", path)


def test_the_scan_really_finds_the_change_routes(app):
    paths = {p for _, p in change_routes(app)}
    assert len(change_routes(app)) >= 12
    assert {"/suppliers", "/suppliers/{supplier_id}/terms", "/product-suppliers/{variant_id}/{supplier_id}/terms"} <= paths


def test_viewers_and_anonymous_callers_cannot_change_anything(app):
    client = TestClient(app)
    leaks = []
    for method, path in change_routes(app):
        url = concrete(path)
        viewer = client.request(method, url, json={}, headers={"Authorization": "Bearer viewer"}).status_code
        anonymous = client.request(method, url, json={}).status_code
        if viewer != 403 or anonymous != 401:
            leaks.append((method, path, viewer, anonymous))
    assert not leaks, f"change routes without a working role check (viewer, anonymous): {leaks}"
