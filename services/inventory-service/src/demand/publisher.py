"""T056: publish inventory.snapshot.created.v1 and inventory.demand.updated.v1 through the outbox."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Protocol

from db.tables import outbox
from mmi_common.bus import new_envelope
from mmi_common.outbox import enqueue
from sqlalchemy.engine import Connection

SNAPSHOT_EVENT = "inventory.snapshot.created.v1"
DEMAND_EVENT = "inventory.demand.updated.v1"
SUBSCRIPTIONS = {SNAPSHOT_EVENT: ["forecast-in", "procurement-in"], DEMAND_EVENT: ["forecast-in"]}


class BlobWriter(Protocol):
    def put(self, name: str, data: bytes) -> str: ...


class LocalBlobWriter:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def put(self, name: str, data: bytes) -> str:
        path = (self.root / name).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("blob name escapes the store")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path.as_uri()


def _doc(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()


def publish_snapshot_created(conn: Connection, writer: BlobWriter, snapshot_date: date, variant_count: int, correlation_id: str) -> dict:
    data = _doc({"snapshot_date": snapshot_date.isoformat(), "variant_count": variant_count})
    uri = writer.put(f"events/snapshot/{snapshot_date.isoformat()}.json", data)
    env = new_envelope(SNAPSHOT_EVENT, snapshot_date.isoformat(), data, uri, correlation_id)
    enqueue(conn, outbox, env)
    return env


def publish_demand_updated(conn: Connection, writer: BlobWriter, through_day: date, series_count: int, correlation_id: str) -> dict:
    data = _doc({"through_day": through_day.isoformat(), "series_count": series_count})
    uri = writer.put(f"events/demand/{through_day.isoformat()}.json", data)
    env = new_envelope(DEMAND_EVENT, through_day.isoformat(), data, uri, correlation_id)
    enqueue(conn, outbox, env)
    return env
