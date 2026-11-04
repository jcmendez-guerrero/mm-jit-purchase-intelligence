import json
import uuid

import pytest
from db.tables import metadata
from mmi_common.bus import InMemoryBus, new_envelope
from projections.blob import LocalBlobReader
from sqlalchemy import create_engine, event


@pytest.fixture
def engine():
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
