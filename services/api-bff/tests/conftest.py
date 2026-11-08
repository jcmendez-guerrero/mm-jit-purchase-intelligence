"""Fresh, isolated role store per test (an in-memory SQLite stands in for the ``bff`` PostgreSQL schema)."""

import pytest
from db.engine import make_engine
from db.roles import RoleStore
from routes import admin_roles

DEMO_USERS = {
    "buyer-1": ["viewer", "buyer"],
    "approver-1": ["viewer", "approver"],
    "approver-2": ["viewer", "approver"],
    "admin-1": ["viewer", "admin"],
}


@pytest.fixture(autouse=True)
def role_store(monkeypatch):
    monkeypatch.delenv("MMI_DATABASE_URL", raising=False)
    monkeypatch.delenv("MMI_ENABLE_DEV_LOGIN", raising=False)
    store = RoleStore(make_engine("sqlite://"))
    store.replace_all(DEMO_USERS)
    admin_roles.set_store(store)
    yield store
    admin_roles.set_store(None)
