"""Cost-writer job entrypoint: drains the costwriter-in queue once, then exits (scale to zero).

Environment: MMI_DATABASE_URL, MMI_SIWEB_BASE_URL (+ MMI_ALLOW_HTTP for the local mock), MMI_PROCUREMENT_URL, MMI_PROCUREMENT_TOKEN,
MMI_BLOB_ROOT, and the writer's own Siweb token via MMI_KEYVAULT_URL/MMI_SIWEB_WRITER_SECRET or MMI_SIWEB_WRITER_TOKEN (local).
The writer identity is separate from the reader's: it alone can read this secret.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from mmi_common.logging import configure_logging
from sqlalchemy import create_engine
from writer.allowlist import WriterAllowlist
from writer.client import SiwebWriterClient, StaticToken
from writer.flow import WriteProcessor
from writer.procurement import HttpProcurementApi

log = logging.getLogger("cost-writer.job")


class FileBlobs:
    def __init__(self, root: Path) -> None:
        self.root = root

    def put(self, name: str, data: bytes) -> str:
        p = (self.root / name).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("blob name escapes the store")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p.as_uri()


def writer_token() -> str:
    if token := os.environ.get("MMI_SIWEB_WRITER_TOKEN"):
        return token
    from azure.identity import DefaultAzureCredential  # type: ignore[import-not-found]
    from azure.keyvault.secrets import SecretClient  # type: ignore[import-not-found]

    client = SecretClient(vault_url=os.environ["MMI_KEYVAULT_URL"], credential=DefaultAzureCredential())
    return client.get_secret(os.environ["MMI_SIWEB_WRITER_SECRET"]).value or ""


def build_processor(http: httpx.Client | None = None) -> tuple[WriteProcessor, WriterAllowlist]:
    base = os.environ["MMI_SIWEB_BASE_URL"].rstrip("/")
    parts = urlsplit(base)
    allowlist = WriterAllowlist(parts.hostname or "", allow_http=parts.scheme == "http" and bool(os.environ.get("MMI_ALLOW_HTTP")))
    siweb = SiwebWriterClient(http or httpx.Client(timeout=30), base, allowlist, StaticToken(writer_token()))
    procurement = HttpProcurementApi(os.environ["MMI_PROCUREMENT_URL"], os.environ["MMI_PROCUREMENT_TOKEN"])
    engine = create_engine(os.environ["MMI_DATABASE_URL"])
    blobs = FileBlobs(Path(os.environ.get("MMI_BLOB_ROOT", "/tmp/mmi-costwrite")))  # noqa: S108 - local default only
    return WriteProcessor(engine, siweb, procurement, blobs), allowlist


def main() -> int:
    configure_logging()
    try:
        processor, allowlist = build_processor()
        from azure.identity import DefaultAzureCredential  # type: ignore[import-not-found]
        from azure.storage.queue import QueueServiceClient  # type: ignore[import-not-found]
        from db.tables import outbox
        from mmi_common.bus import StorageQueueBus
        from mmi_common.outbox import relay_once
        from writer.consumer import Blobs, consume
        from writer.flow import SUBSCRIPTIONS

        service = QueueServiceClient(os.environ["MMI_QUEUE_URL"], credential=DefaultAzureCredential())
        bus = StorageQueueBus(service)
        stats = consume(processor.engine, bus, Blobs(), processor)
        with processor.engine.begin() as conn:      # announce outcomes (retries, successes, failures) to procurement-service
            relay_once(conn, outbox, bus, SUBSCRIPTIONS)
    except Exception:
        log.exception("WRITER_FAILED")
        return 1
    log.info("writer run finished: %s", stats)
    if allowlist.refusals:
        log.error("ALLOWLIST_REFUSED count=%s", len(allowlist.refusals))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
