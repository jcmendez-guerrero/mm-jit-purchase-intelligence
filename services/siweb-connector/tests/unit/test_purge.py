"""T136: expired raw payloads are removed, unexpired ones kept."""

from datetime import UTC, datetime, timedelta

from db.tables import raw_payload_index, sync_runs
from sqlalchemy import insert, select
from storage.purge import purge_expired
from sync.raw_store import write_raw

NOW = datetime(2026, 12, 1, tzinfo=UTC)


def seed(engine, store, run_id, age_days, retention=90):
    fetched = NOW - timedelta(days=age_days)
    with engine.begin() as c:
        c.execute(insert(sync_runs).values(id=run_id, kind="movements", status="committed", started_at=fetched))
        raw = write_raw(store, "movements", run_id, {"records": [{"id": 1, "notes": "texto"}]}, fetched, retention)
        c.execute(insert(raw_payload_index).values(blob_uri=raw.uri, run_id=run_id, sha256=raw.sha256, fetched_at=fetched, expires_at=raw.expires_at))
    return raw.uri


def test_expired_removed_unexpired_kept(engine, store):
    old = seed(engine, store, "r-old", age_days=91)
    edge = seed(engine, store, "r-edge", age_days=89)
    new = seed(engine, store, "r-new", age_days=1)
    assert purge_expired(engine, store, NOW) == 1
    assert not store.exists(old) and store.exists(edge) and store.exists(new)
    with engine.connect() as c:
        assert {r.blob_uri for r in c.execute(select(raw_payload_index)).all()} == {edge, new}


def test_configurable_retention_and_idempotent(engine, store):
    short = seed(engine, store, "r-short", age_days=10, retention=7)
    assert purge_expired(engine, store, NOW) == 1 and not store.exists(short)
    assert purge_expired(engine, store, NOW) == 0


def test_missing_blob_does_not_block_index_cleanup(engine, store):
    uri = seed(engine, store, "r-gone", age_days=200)
    store.delete(uri)
    assert purge_expired(engine, store, NOW) == 1
