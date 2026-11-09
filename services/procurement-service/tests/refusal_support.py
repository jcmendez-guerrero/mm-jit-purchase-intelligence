"""Fixtures shared by the refusal, abuse, privacy and latency tests: a file database in WAL mode, the terms and supplier routes on it, one supplier.

Import them with ``from refusal_support import app, client, engine, h, sid  # noqa: F401, F811``. They replace the shared in-memory ``engine`` of
conftest.py only in the modules that import them.
"""

from __future__ import annotations

import pytest
from api import costs
from api.suppliers import build_router
from conftest import NOW
from db.tables import audit_events, metadata
from fastapi.testclient import TestClient
from mmi_common.service import create_service_app
from sqlalchemy import create_engine, event, select
from suppliers.service import SupplierInput, create_supplier
from test_terms_roles import Validator


@pytest.fixture
def engine(tmp_path):
    """A file database in WAL mode, so the refusal's own transaction runs beside the request's, as two connections do on PostgreSQL.

    (The shared in-memory engine of the other tests is a single connection and cannot hold two transactions at once.)
    """
    eng = create_engine(f"sqlite:///{tmp_path / 'refusals.db'}", connect_args={"timeout": 15})

    @event.listens_for(eng, "connect")
    def _connect(dbapi_conn, _):
        dbapi_conn.isolation_level = None
        dbapi_conn.execute("PRAGMA journal_mode=WAL")

    @event.listens_for(eng, "begin")
    def _begin(conn):
        conn.exec_driver_sql("BEGIN")

    metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def app(engine):
    application = create_service_app("procurement-service", validator=Validator())
    application.include_router(costs.build_router(application))
    application.include_router(build_router(application))
    application.dependency_overrides[costs.get_engine] = lambda: engine
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def sid(engine):
    with engine.begin() as c:
        return create_supplier(c, SupplierInput(name="Proveedor Sintetico", fiscal_type="national", country="ES", currency="EUR"), "buyer-1", now=NOW).id


def h(role="buyer", **extra):
    return {"Authorization": f"Bearer {role}", **extra}


def refusals(engine):
    with engine.begin() as c:
        rows = [r for r in c.execute(select(audit_events).order_by(audit_events.c.id)).all() if r.action.endswith(".refused")]
        return [(r.actor, r.action, r.entity, r.entity_id, r.after, r.before) for r in rows]
