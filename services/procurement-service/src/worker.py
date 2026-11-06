"""Procurement worker (T146/T148/T150): drains procurement-in, reconciles supplier receipts, relays the outbox.

    python -m worker          one pass (ACA job on a short cron, scale to zero)
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
from consumer import ReceiptSource, consume_once, sync_receipts
from costs.lot_lookup import HttpLotsSource, LotsSource
from db.tables import outbox
from mmi_common.busfactory import bus_from_env
from mmi_common.logging import configure_logging
from mmi_common.outbox import relay_once
from mmi_common.servicetoken import service_token
from mmi_common.workerloop import run as run_loop
from proposals.blob_store import FileWriter
from proposals.publisher import SUBSCRIPTIONS, BlobWriter
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

log = logging.getLogger("procurement.worker")


class HttpReceiptSource:
    def __init__(self, base_url: str, token: str | Callable[[], str], client: httpx.Client | None = None) -> None:
        self._base, self._token, self._client = base_url.rstrip("/"), token, client or httpx.Client(timeout=60)

    def fetch_after(self, after_id: int) -> list[dict[str, Any]]:
        token = self._token() if callable(self._token) else self._token
        r = self._client.get(f"{self._base}/receipts", params={"after_id": after_id, "limit": 1000}, headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        return r.json()["receipts"]  # type: ignore[no-any-return]

    def __repr__(self) -> str:
        return "HttpReceiptSource(token=***)"


class FileBlobs:
    def get(self, uri: str) -> bytes:
        from pathlib import Path

        return Path(uri.removeprefix("file://")).read_bytes()


def run_once(engine: Engine, bus, blobs, receipts: ReceiptSource | None, writer: BlobWriter | None = None, lots: LotsSource | None = None) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    stats = consume_once(engine, bus, blobs)
    receipt_stats: dict[str, int] = {}
    if receipts is not None:
        with engine.begin() as conn:
            receipt_stats = sync_receipts(conn, receipts, writer=writer, lots=lots)
    with engine.begin() as conn:
        sent = relay_once(conn, outbox, bus, SUBSCRIPTIONS)
    return {"applied": stats.applied, "duplicates": stats.duplicates, "rejected": stats.rejected, "failed": stats.failed, "relayed": sent, "receipts": receipt_stats}


def main() -> int:
    configure_logging()
    try:
        engine = create_engine(os.environ["MMI_DATABASE_URL"])
        token = os.environ.get("MMI_INVENTORY_TOKEN") or (lambda: service_token("api://mmi-inventory-service", "svc-procurement", ["viewer"]))
        url = os.environ.get("MMI_INVENTORY_URL")
        src = HttpReceiptSource(url, token) if url else None
        lots = HttpLotsSource(url, token) if url else None
        writer = FileWriter(Path(os.environ.get("MMI_BLOB_ROOT", "/tmp/mmi-procurement")))  # noqa: S108 - local default only
        result = run_once(engine, bus_from_env(), FileBlobs(), src, writer, lots)
    except Exception:
        log.exception("WORKER_FAILED")
        return 1
    log.info("procurement worker pass: %s", result)
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(run_loop(main))
