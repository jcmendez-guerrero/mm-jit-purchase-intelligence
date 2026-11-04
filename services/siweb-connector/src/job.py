"""Connector job entrypoint (T045): one invocation = one sync window, run by an ACA Job on a night schedule.

    python -m job [movements|warehouses|products|variants|all]

Configuration comes from the environment (see infra/compose.yaml): MMI_SIWEB_BASE_URL, MMI_DATABASE_URL,
MMI_BLOB_ROOT (local) or MMI_BLOB_ACCOUNT_URL + MMI_BLOB_CONTAINER (Azure), MMI_SIWEB_REQUESTS_PER_HOUR,
and the token via MMI_KEYVAULT_URL/MMI_SIWEB_SECRET_NAME or MMI_SIWEB_TOKEN for local runs.
Exit code 0 = committed or partial (resumes next window), 1 = failed (alerts fire from the run row).
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from allowlist.allowlist import Allowlist
from client.reader import AuthExpiredError, ReaderClient
from client.token import provider_from_env
from mmi_common.logging import configure_logging
from ratelimit.bucket import NightWindow, TokenBucket
from sqlalchemy import create_engine
from storage.blob import AzureBlobStore, BlobStore, LocalBlobStore
from sync.runner import MovementSync
from sync.snapshot import SnapshotSync

log = logging.getLogger("siweb-connector.job")
KINDS = ("warehouses", "products", "variants", "movements")


def build_store() -> BlobStore:
    if root := os.environ.get("MMI_BLOB_ROOT"):
        return LocalBlobStore(Path(root))
    return AzureBlobStore(os.environ["MMI_BLOB_ACCOUNT_URL"], os.environ.get("MMI_BLOB_CONTAINER", "raw"))


def run(kinds: list[str], enforce_window: bool = True) -> int:
    base = os.environ["MMI_SIWEB_BASE_URL"].rstrip("/")
    host = urlsplit(base)
    if enforce_window and not NightWindow().is_open(datetime.now(UTC)) and not os.environ.get("MMI_IGNORE_NIGHT_WINDOW"):
        log.info("outside the night window; nothing to do")
        return 0
    allowlist = Allowlist(host.hostname or "", allow_http=host.scheme == "http" and bool(os.environ.get("MMI_ALLOW_HTTP")))
    reader = ReaderClient(
        http=httpx.Client(timeout=30), base_url=base, allowlist=allowlist,
        bucket=TokenBucket(per_hour=int(os.environ.get("MMI_SIWEB_REQUESTS_PER_HOUR", "500"))), tokens=provider_from_env())
    engine, store = create_engine(os.environ["MMI_DATABASE_URL"]), build_store()
    code = 0
    for kind in kinds:
        try:
            result = MovementSync(reader, engine, store).run() if kind == "movements" else SnapshotSync(reader, engine, store, kind).run()
            log.info("sync %s: %s fetched=%s stored=%s errors=%s reconciled=%s requests=%s", kind, result.status,
                     result.fetched, result.stored, result.errors, result.reconciled, result.requests_used)
            if result.status == "committed":
                log.info("SYNC_OK kind=%s", kind)
            elif result.status == "partial":
                log.warning("QUOTA_DENIED kind=%s requests=%s", kind, result.requests_used)
        except AuthExpiredError:
            log.error("SYNC_FAILED kind=%s reason=token_rejected", kind)
            return 1
    if allowlist.refusals:
        log.error("ALLOWLIST_REFUSED count=%s", len(allowlist.refusals))
        code = 1
    return code


def main(argv: list[str]) -> int:
    configure_logging()
    arg = argv[1] if len(argv) > 1 else "all"
    if arg != "all" and arg not in KINDS:
        print(f"usage: python -m job [{'|'.join(KINDS)}|all]", file=sys.stderr)
        return 2
    return run(list(KINDS) if arg == "all" else [arg])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
