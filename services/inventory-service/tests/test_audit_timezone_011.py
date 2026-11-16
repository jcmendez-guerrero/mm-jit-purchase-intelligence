"""Feature 011 (T083): the audit hash is the same whatever offset the database returns the stored instant in (PostgreSQL answers in the session time zone)."""

from datetime import UTC, datetime, timedelta, timezone

from audit import _body


def test_the_hashed_instant_is_always_utc():
    instant = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
    madrid = instant.astimezone(timezone(timedelta(hours=1)))
    assert madrid.isoformat() != instant.isoformat()
    assert _body(madrid, "a", "x.y", "e", "1", None, None)["ts"] == _body(instant, "a", "x.y", "e", "1", None, None)["ts"] == "2026-11-04T12:00:00+00:00"
    assert _body(instant.replace(tzinfo=None), "a", "x.y", "e", "1", None, None)["ts"] == "2026-11-04T12:00:00+00:00"        # a naive value is read as UTC
