"""Shared helpers for the demand pipeline."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from mmi_common.time import ASSUMED_LOCAL_TZ

DEFAULT_CUTOVER = date(2026, 9, 19)


@dataclass(frozen=True)
class Mov:
    """The slice of a stored movement the pipeline needs."""

    external_id: int
    variant_id: int
    warehouse_id: int
    day: date | None  # business day in Europe/Madrid; None when the timestamp is unusable
    reason: str
    quantity: int  # signed: sales negative, receipts positive
    quarantined: bool


def local_day(utc_dt: datetime | None) -> date | None:
    if utc_dt is None:
        return None
    aware = utc_dt if utc_dt.tzinfo else utc_dt.replace(tzinfo=UTC)
    return aware.astimezone(ZoneInfo(ASSUMED_LOCAL_TZ)).date()


def lineage(ids: Iterable[int]) -> str:
    return hashlib.sha256(",".join(str(i) for i in sorted(ids)).encode()).hexdigest()[:16]
