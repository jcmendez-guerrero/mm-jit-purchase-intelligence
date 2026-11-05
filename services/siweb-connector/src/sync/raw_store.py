"""T041: write the raw payload to Blob after field stripping, with retention metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from mapping.normalise import strip_sensitive
from mmi_common.bus import sha256_hex
from storage.blob import BlobStore

DEFAULT_RETENTION_DAYS = 90


@dataclass(frozen=True)
class RawPayload:
    uri: str
    sha256: str
    data: bytes
    expires_at: datetime


def write_raw(store: BlobStore, kind: str, run_id: str, document: dict[str, Any], now: datetime,
              retention_days: int = DEFAULT_RETENTION_DAYS) -> RawPayload:
    """``supplier_cif`` and free-text notes are stripped (only ``has_note`` stays) before bytes are produced."""
    clean = strip_sensitive(document)
    data = json.dumps(clean, sort_keys=True, separators=(",", ":"), default=str).encode()
    expires_at = now + timedelta(days=retention_days)
    uri = store.put(f"raw/{kind}/{now:%Y/%m/%d}/{run_id}.json", data, expires_at)
    return RawPayload(uri, sha256_hex(data), data, expires_at)
