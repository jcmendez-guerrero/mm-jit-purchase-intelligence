import os
import uuid
from datetime import UTC, datetime

import pytest
from db.tables import metadata, product_refs, suppliers
from mmi_common import pg_testing
from sqlalchemy import create_engine, event, insert
from sqlalchemy.pool import StaticPool

pytest_plugins = ["proposal_support"]       # the proposal routes fixture (`api`) of the feature-011 guarantee tests

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="session", autouse=True)
def _drop_pg_schema():
    yield
    pg_testing.drop_schema()


@pytest.fixture
def engine():
    url = os.environ.get("MMI_TEST_DATABASE_URL")
    if url:                                   # a real PostgreSQL (feature 011, T077, T083, T090)
        eng = pg_testing.pg_engine(url, metadata)
        yield eng
        pg_testing.clean(eng, metadata)
        return
    eng = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def _c(dbapi_conn, _):
        dbapi_conn.isolation_level = None

    @event.listens_for(eng, "begin")
    def _b(conn):
        conn.exec_driver_sql("BEGIN")

    metadata.create_all(eng)
    yield eng


@pytest.fixture
def conn(engine):
    with engine.begin() as c:
        yield c


def add_supplier(c, contact_id=1, name="Proveedor Sintetico"):
    sid = str(uuid.uuid4())
    c.execute(insert(suppliers).values(id=sid, external_contact_id=contact_id, name=name))
    return sid


def add_product(c, variant_id, product_id, vat=None):
    c.execute(insert(product_refs).values(variant_id=variant_id, product_id=product_id, vat_rate=vat, vat_source="buyer" if vat is not None else None))


class _Validator:
    def validate(self, token, required_roles=()):
        from mmi_common.auth import AuthError, Principal

        roles = {"viewer", "buyer"} if token == "buyer" else {"viewer"}  # noqa: S105 - test token name, not a secret
        if not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        return Principal(subject=f"user-{token}", roles=frozenset(roles), auth_time=None)


@pytest.fixture
def client(engine):
    from api import costs
    from fastapi.testclient import TestClient
    from mmi_common.service import create_service_app

    app = create_service_app("procurement-service", validator=_Validator())
    app.include_router(costs.build_router(app))
    app.dependency_overrides[costs.get_engine] = lambda: engine
    return TestClient(app)


def auth(role="viewer"):
    return {"Authorization": f"Bearer {role}"}


@pytest.fixture
def outbound(monkeypatch):
    """T005 (FR-011, SC-004): any attempt to open a network connection or send an HTTP request is recorded and refused. Tests assert the list stays empty."""
    import socket

    import httpx

    attempts: list[str] = []

    def _connect(self, address, *a, **k):
        attempts.append(f"socket:{address}")
        raise OSError("network access is denied in this test")

    def _send(self, request, *a, **k):
        attempts.append(f"http:{request.method} {request.url}")
        raise httpx.ConnectError("network access is denied in this test")

    monkeypatch.setattr(socket.socket, "connect", _connect)
    async def _asend(self, request, *a, **k):
        return _send(self, request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _send)             # the real network transports; the in-process test client has its own and is unaffected
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _asend)
    return attempts
