"""T148: forecast-service reacts to inventory.demand.updated.v1 by running a forecast on the latest series export.

An identical input is recognised by its hash and not repeated, so a redelivered or repeated trigger costs nothing.
inventory.snapshot.created.v1 shares the queue and is acknowledged without a run (the demand event follows it).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from db.tables import inbox
from mmi_common.dispatch import BlobReader, DispatchStats, Handler, consume_queue
from sqlalchemy.engine import Connection, Engine

from runs.runner import RunConfig, SeriesSource, run_forecast_conn

QUEUE = "forecast-in"
DEMAND = "inventory.demand.updated.v1"
SNAPSHOT = "inventory.snapshot.created.v1"
SEED = "forecast.seed.activated.v1"


@dataclass
class ForecastConsumer:
    engine: Engine
    source: SeriesSource
    writer: Any
    config: RunConfig | None = None
    runs_started: int = 0

    def handlers(self) -> dict[str, Handler]:
        def demand(conn: Connection, env: dict[str, Any], payload: bytes) -> None:
            result = run_forecast_conn(conn, self.source, self.writer, self.config)       # same transaction as the inbox row
            self.runs_started += 0 if result.reused else 1

        def snapshot(conn: Connection, env: dict[str, Any], payload: bytes) -> None:
            return None

        return {DEMAND: demand, SNAPSHOT: snapshot, SEED: demand}            # an activation or rollback asks for a new, versioned run


def consume_once(engine: Engine, bus: Any, blobs: BlobReader, source: SeriesSource, writer: Any, queue: str = QUEUE,
                 config: RunConfig | None = None) -> DispatchStats:
    return consume_queue(engine, bus, blobs, queue, inbox, ForecastConsumer(engine, source, writer, config).handlers())
