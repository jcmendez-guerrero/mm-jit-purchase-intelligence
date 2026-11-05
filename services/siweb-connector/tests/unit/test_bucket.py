from datetime import UTC, datetime

from ratelimit.bucket import NightWindow, TokenBucket


def test_bucket_allows_burst_up_to_capacity_then_denies_and_refills():
    now = [0.0]
    b = TokenBucket(per_hour=3600, clock=lambda: now[0])
    assert all(b.try_acquire() for _ in range(3600))
    assert not b.try_acquire() and b.denied == 1
    now[0] += 2  # 1 token per second
    assert b.try_acquire() and b.try_acquire() and not b.try_acquire()
    assert b.used == 3602


def test_default_budget_is_500_per_hour():
    assert TokenBucket().per_hour == 500


def test_night_window_uses_madrid_local_time():
    w = NightWindow()
    assert w.is_open(datetime(2026, 11, 4, 2, 0, tzinfo=UTC))   # 03:00 CET
    assert not w.is_open(datetime(2026, 11, 4, 13, 0, tzinfo=UTC))
    assert w.is_open(datetime(2026, 11, 4, 0, 30, tzinfo=UTC))      # 01:30 CET
    assert not w.is_open(datetime(2026, 11, 4, 23, 30, tzinfo=UTC))  # 00:30 CET, before the window
