"""The business day of the pharmacy: the date in Madrid (feature 014, FR-022). Demand rows are keyed by it, so the UTC date would read the first hours of each Madrid day, and every
day around the two clock changes, as the day before. One helper for the whole service; nothing else may ask for the UTC date as "today"."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from mmi_common.time import ASSUMED_LOCAL_TZ

LOCAL_TZ = ZoneInfo(ASSUMED_LOCAL_TZ)


def business_today(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(LOCAL_TZ).date()
