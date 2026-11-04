"""Request budget for the shared Siweb limit: token bucket (default 500 req/h) plus a night window."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from datetime import time as dtime
from zoneinfo import ZoneInfo


@dataclass
class TokenBucket:
    per_hour: int = 500
    clock: Callable[[], float] = time.monotonic
    _tokens: float = field(init=False)
    _last: float = field(init=False)
    used: int = 0
    denied: int = 0

    def __post_init__(self) -> None:
        self._tokens = float(self.per_hour)
        self._last = self.clock()

    def _refill(self) -> None:
        now = self.clock()
        self._tokens = min(float(self.per_hour), self._tokens + (now - self._last) * self.per_hour / 3600)
        self._last = now

    def try_acquire(self) -> bool:
        self._refill()
        if self._tokens >= 1:
            self._tokens -= 1
            self.used += 1
            return True
        self.denied += 1
        return False

    def seconds_until_available(self) -> float:
        self._refill()
        return 0.0 if self._tokens >= 1 else (1 - self._tokens) * 3600 / self.per_hour


@dataclass(frozen=True)
class NightWindow:
    """Heavy jobs run only inside this local-time window (default 01:00-06:00 Europe/Madrid)."""

    start: dtime = dtime(1, 0)
    end: dtime = dtime(6, 0)
    tz: str = "Europe/Madrid"

    def is_open(self, now: datetime) -> bool:
        local = now.astimezone(ZoneInfo(self.tz)).time()
        if self.start <= self.end:
            return self.start <= local < self.end
        return local >= self.start or local < self.end
