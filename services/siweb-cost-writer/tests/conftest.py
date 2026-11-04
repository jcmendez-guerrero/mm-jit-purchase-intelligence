import pytest
from db.tables import metadata
from fastapi.testclient import TestClient
from siweb_mock.app import create_app
from siweb_mock.state import TOKEN, MockConfig
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from writer.allowlist import WriterAllowlist
from writer.client import SiwebWriterClient, StaticToken


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def _c(dbapi_conn, _):
        dbapi_conn.isolation_level = None

    @event.listens_for(eng, "begin")
    def _b(conn):
        conn.exec_driver_sql("BEGIN")

    metadata.create_all(eng)
    return eng


class Blobs:
    def __init__(self, tmp):
        self.tmp = tmp

    def put(self, name, data):
        p = self.tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p.as_uri()


@pytest.fixture
def blobs(tmp_path):
    return Blobs(tmp_path)


@pytest.fixture
def mock_siweb():
    app = create_app(config=MockConfig())
    http = TestClient(app, base_url="http://mock.test")
    return app, http


@pytest.fixture
def siweb(mock_siweb):
    _, http = mock_siweb
    return SiwebWriterClient(http, "http://mock.test", WriterAllowlist("mock.test", allow_http=True), StaticToken(TOKEN))


class FakeProcurement:
    def __init__(self):
        self.released = {}

    def release(self, request_id, **kw):
        self.released[request_id] = {"id": request_id, "status": "approved_by_buyer", "idempotency_key": "k", "reviewed_by": "buyer-1", **kw}

    def get_released(self, request_id):
        return self.released.get(request_id)


@pytest.fixture
def procurement():
    return FakeProcurement()


def pair_with_cost(app):
    for pid, rows in app.state.mock.suppliers.items():
        for r in rows:
            if r["purchase_cost_cents"] is not None and r["is_preferred"]:
                return pid, r
    raise AssertionError("no suitable synthetic pair")


def pair_without_cost(app):
    for pid, rows in app.state.mock.suppliers.items():
        for r in rows:
            if r["purchase_cost_cents"] is None:
                return pid, r
    pid, r = pair_with_cost(app)
    r["purchase_cost_cents"] = None
    return pid, r
