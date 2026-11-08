"""T035: the internal role endpoint accepts only the BFF identity, validates its input, audits changes and ignores stale revisions."""

from api import costs, proposals
from audit.chain import verify_chain
from conftest import NOW
from db.tables import audit_events, user_roles
from fastapi.testclient import TestClient
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app
from sqlalchemy import select
from users.directory import set_roles

ROLES = {"bff": {"bff"}, "approver": {"viewer", "approver"}, "admin": {"viewer", "admin"}}


class Validator:
    def validate(self, token, required_roles=()):
        roles = ROLES.get(token)
        if roles is None or not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        return Principal(f"svc-{token}", frozenset(roles), None)


def make(engine):
    app = create_service_app("procurement-service", validator=Validator())
    app.include_router(costs.build_router(app))
    app.include_router(proposals.build_router(app))
    app.dependency_overrides[costs.get_engine] = lambda: engine
    return TestClient(app)


def put(c, token, user, body):
    return c.put(f"/internal/users/{user}/roles", json=body, headers={"Authorization": f"Bearer {token}"})


def test_only_the_bff_identity_may_mirror_roles(engine):
    c = make(engine)
    for token in ("approver", "admin"):
        assert put(c, token, "u1", {"roles": ["viewer"], "revision": 1}).status_code == 403
    assert c.put("/internal/users/u1/roles", json={"roles": ["viewer"]}).status_code == 401
    assert put(c, "bff", "u1", {"roles": ["viewer", "buyer"], "revision": 1}).json() == {"user_id": "u1", "roles": ["buyer", "viewer"], "active": True, "applied": True}


def test_a_stale_revision_is_ignored_and_a_newer_one_wins(engine):
    c = make(engine)
    assert put(c, "bff", "u1", {"roles": ["viewer", "approver"], "revision": 3}).json()["applied"] is True
    assert put(c, "bff", "u1", {"roles": ["viewer"], "revision": 2}).json()["applied"] is False        # a retried older change
    assert put(c, "bff", "u1", {"roles": ["viewer"], "revision": 3}).json()["applied"] is False        # a duplicate
    with engine.connect() as conn:
        assert "approver" in conn.execute(select(user_roles.c.roles).where(user_roles.c.user_id == "u1")).scalar()
    assert put(c, "bff", "u1", {"roles": ["viewer"], "revision": 4}).json()["applied"] is True


def test_invalid_input_is_refused_with_codes(engine):
    c = make(engine)
    assert put(c, "bff", "u1", {"roles": ["superuser"], "revision": 1}).json()["detail"] == "unknown_role"
    assert put(c, "bff", "u1", {"roles": ["viewer"] * 20}).status_code == 422
    assert put(c, "bff", "u1", {"roles": ["viewer"], "revision": -1}).status_code == 422
    assert put(c, "bff", "bad id with spaces", {"roles": ["viewer"]}).status_code in (404, 422)
    assert put(c, "bff", "x" * 130, {"roles": ["viewer"]}).json()["detail"] == "invalid_user_id"


def test_every_applied_change_is_audited_with_its_revision(engine):
    c = make(engine)
    put(c, "bff", "u1", {"roles": ["viewer"], "revision": 1})
    put(c, "bff", "u1", {"roles": ["viewer", "buyer"], "revision": 2})
    with engine.begin() as conn:
        events = conn.execute(select(audit_events).where(audit_events.c.action == "user.roles_set")).all()
        assert [e.after["revision"] for e in events] == [1, 2] and verify_chain(conn).ok


def test_legacy_callers_without_a_revision_still_apply(conn):
    assert set_roles(conn, "u2", ["viewer"], "bff", now=NOW) is True
    assert set_roles(conn, "u2", ["viewer", "buyer"], "bff", now=NOW) is True
