import os
import uuid
from datetime import UTC, datetime

import pytest
from db.tables import metadata, product_refs, suppliers
from sqlalchemy import create_engine, event, insert, text
from sqlalchemy.pool import StaticPool

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


@pytest.fixture
def engine():
    url = os.environ.get("MMI_TEST_DATABASE_URL")
    if url:                                   # a real PostgreSQL: one throw-away schema per test (feature 011, T077)
        schema = f"t_{uuid.uuid4().hex[:12]}"
        admin = create_engine(url)
        with admin.begin() as c:
            c.execute(text(f'CREATE SCHEMA "{schema}"'))
        eng = create_engine(url, connect_args={"options": f"-c search_path={schema}"})
        metadata.create_all(eng)
        yield eng
        eng.dispose()
        with admin.begin() as c:
            c.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
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
