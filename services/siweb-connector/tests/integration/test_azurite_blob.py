"""T153: the Azure blob store used for raw payloads, against Azurite. Needs Docker and RUN_AZURITE=1."""

from datetime import UTC, datetime, timedelta

import pytest
from azurite_fixture import available, azurite
from db.tables import raw_payload_index, sync_runs
from storage.blob import AzureBlobStore
from storage.purge import purge_expired

pytestmark = pytest.mark.skipif(not available(), reason="needs Docker and RUN_AZURITE=1")


@pytest.fixture(scope="module")
def store():
    with azurite() as conn:
        yield AzureBlobStore.from_connection_string(conn, "raw")


def test_put_get_exists_delete_roundtrip(store):
    exp = datetime(2027, 1, 1, tzinfo=UTC)
    uri = store.put("raw/movements/2026/11/05/run-1.json", b'{"a":1}', exp)
    assert store.exists(uri) and store.get(uri) == b'{"a":1}'
    store.delete(uri)
    assert not store.exists(uri)
    store.delete(uri)                                           # deleting a missing blob is not an error


def test_the_purge_job_removes_expired_blobs_and_keeps_current_ones(store, engine):
    from sqlalchemy import insert

    now = datetime(2026, 12, 1, tzinfo=UTC)
    uris = {}
    for rid, age in (("old", 100), ("new", 5)):
        fetched = now - timedelta(days=age)
        uris[rid] = store.put(f"raw/x/{rid}.json", b"{}", fetched + timedelta(days=90))
        with engine.begin() as c:
            c.execute(insert(sync_runs).values(id=rid, kind="x", status="committed", started_at=fetched))
            c.execute(insert(raw_payload_index).values(blob_uri=uris[rid], run_id=rid, sha256="0" * 64, fetched_at=fetched, expires_at=fetched + timedelta(days=90)))
    assert purge_expired(engine, store, now) == 1
    assert not store.exists(uris["old"]) and store.exists(uris["new"])
