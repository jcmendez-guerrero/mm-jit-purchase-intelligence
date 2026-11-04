import pytest
from allowlist.allowlist import Allowlist
from client.reader import ReaderClient
from client.token import StaticTokenProvider
from fastapi.testclient import TestClient
from ratelimit.bucket import TokenBucket
from siweb_mock.app import create_app
from siweb_mock.state import TOKEN, MockConfig


@pytest.fixture
def make_reader():
    def _make(config: MockConfig | None = None, per_hour: int = 100_000, **kw):
        app = create_app(config=config)
        http = TestClient(app, base_url="http://mock.test")
        reader = ReaderClient(
            http=http, base_url="http://mock.test", allowlist=Allowlist("mock.test", allow_http=True),
            bucket=TokenBucket(per_hour=per_hour), tokens=StaticTokenProvider(TOKEN), sleep=lambda s: None, **kw,
        )
        return reader, app

    return _make


@pytest.fixture
def engine():
    from db.tables import metadata
    from sqlalchemy import create_engine, event

    eng = create_engine("sqlite://")

    @event.listens_for(eng, "connect")
    def _c(dbapi_conn, _):
        dbapi_conn.isolation_level = None

    @event.listens_for(eng, "begin")
    def _b(conn):
        conn.exec_driver_sql("BEGIN")

    metadata.create_all(eng)
    return eng


@pytest.fixture
def store(tmp_path):
    from storage.blob import LocalBlobStore

    return LocalBlobStore(tmp_path / "blobs")
