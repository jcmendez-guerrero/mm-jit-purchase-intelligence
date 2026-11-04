import json
import uuid

import pytest
from db.tables import metadata
from mmi_common.bus import InMemoryBus, new_envelope
from projections.blob import LocalBlobReader
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})  # shared with the API thread

    @event.listens_for(eng, "connect")
    def _c(dbapi_conn, _):
        dbapi_conn.isolation_level = None

    @event.listens_for(eng, "begin")
    def _b(conn):
        conn.exec_driver_sql("BEGIN")

    metadata.create_all(eng)
    return eng


@pytest.fixture
def bus():
    return InMemoryBus()


@pytest.fixture
def publish(bus, tmp_path):
    """Write a payload like the connector would and announce it on the bus; returns the envelope."""

    def _publish(kind, records, reconciled=True, quarantined=None, tamper=False):
        run_id = str(uuid.uuid4())
        doc = {"run_id": run_id, "kind": kind, "reconciled": reconciled, "counts_stored": len(records),
               "records": records, "quarantined": {str(k): v for k, v in (quarantined or {}).items()}}
        data = json.dumps(doc).encode()
        path = tmp_path / f"{run_id}.json"
        path.write_bytes(data)
        env = new_envelope("siweb.sync.completed.v1", run_id, data, path.as_uri(), str(uuid.uuid4()))
        if tamper:
            path.write_bytes(data + b" ")
        bus.send("inventory-sync-completed", env)
        return env

    return _publish


@pytest.fixture
def blobs():
    return LocalBlobReader()


class _Validator:
    def validate(self, token, required_roles=()):
        from mmi_common.auth import AuthError, Principal

        roles = {"viewer", "buyer"} if token == "buyer" else {"viewer"}  # noqa: S105 - test token name, not a secret
        if not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        return Principal(subject=f"user-{token}", roles=frozenset(roles), auth_time=None)


@pytest.fixture
def client(engine):
    from api import routes
    from fastapi.testclient import TestClient
    from mmi_common.service import create_service_app

    app = create_service_app("inventory-service", validator=_Validator())
    app.include_router(routes.build_router(app))
    app.dependency_overrides[routes.get_engine] = lambda: engine
    return TestClient(app)


def auth(role="viewer"):
    return {"Authorization": f"Bearer {role}"}
