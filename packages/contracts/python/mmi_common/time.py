"""UTC time handling and correlation IDs.

Siweb timestamps carry no offset (open item V1). We store UTC plus the original string and
record the assumption; local business time is assumed to be Europe/Madrid until verified.
"""

from __future__ import annotations

import contextvars
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

ASSUMED_LOCAL_TZ = "Europe/Madrid"

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("correlation_id", default=None)


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_correlation_id() -> str:
    return str(uuid.uuid4())


def set_correlation_id(value: str | None = None) -> str:
    cid = value or new_correlation_id()
    _correlation_id.set(cid)
    return cid


def get_correlation_id() -> str | None:
    return _correlation_id.get()


@dataclass(frozen=True)
class ParsedTimestamp:
    utc: datetime
    raw: str
    assumed_tz: str | None  # None when the source carried an explicit offset
    ambiguous: bool  # local time falls in a DST overlap or gap


def parse_siweb_timestamp(raw: str, local_tz: str = ASSUMED_LOCAL_TZ) -> ParsedTimestamp:
    """Parse an ISO-8601 timestamp; offset-less values are interpreted in ``local_tz``."""
    text = raw.strip()
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        return ParsedTimestamp(parsed.astimezone(UTC), raw, None, False)
    zone = ZoneInfo(local_tz)
    first = parsed.replace(tzinfo=zone, fold=0)
    second = parsed.replace(tzinfo=zone, fold=1)
    off1, off2 = first.utcoffset(), second.utcoffset()
    ambiguous = off1 != off2  # overlap (fall back) or gap (spring forward)
    return ParsedTimestamp(first.astimezone(UTC), raw, local_tz, ambiguous)
