"""Fresh, isolated role store per test (an in-memory SQLite stands in for the ``bff`` PostgreSQL schema)."""

import os

import pytest
from db.engine import make_engine
from db.roles import RoleStore
from db.tables import metadata
from mmi_common import pg_testing
from routes import admin_roles

DEMO_USERS = {
    "buyer-1": ["viewer", "buyer"],
    "approver-1": ["viewer", "approver"],
    "approver-2": ["viewer", "approver"],
    "admin-1": ["viewer", "admin"],
}


@pytest.fixture(scope="session", autouse=True)
def _drop_pg_schema():
    yield
    pg_testing.drop_schema()


@pytest.fixture(autouse=True)
def role_store(monkeypatch):
    monkeypatch.delenv("MMI_DATABASE_URL", raising=False)
    monkeypatch.delenv("MMI_ENABLE_DEV_LOGIN", raising=False)
    url = os.environ.get("MMI_TEST_DATABASE_URL")
    engine = pg_testing.pg_engine(url, metadata) if url else make_engine("sqlite://")        # a real PostgreSQL when asked (feature 011, T086)
    if url:                                                    # the seeding helpers are refused outside SQLite on purpose; this schema is a throw-away test one
        monkeypatch.setattr(RoleStore, "_sqlite_only", lambda self: None)
    store = RoleStore(engine)
    store.replace_all(DEMO_USERS)
    admin_roles.set_store(store)
    yield store
    admin_roles.set_store(None)
    if url:
        pg_testing.clean(engine, metadata)
