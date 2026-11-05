import random
from decimal import Decimal

import pytest
from db.tables import metadata
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def _c(dbapi_conn, _):
        dbapi_conn.isolation_level = None

    @event.listens_for(eng, "begin")
    def _b(conn):
        conn.exec_driver_sql("BEGIN")

    metadata.create_all(eng)
    return eng


def weekly_series(rng, weeks, weekly_mean, shift_after=None, shift_factor=1.0):
    """Daily demand: Poisson-ish via sums of Bernoulli draws; optional level shift near the end."""
    out = []
    for w in range(weeks):
        mean = weekly_mean * (shift_factor if shift_after is not None and w >= shift_after else 1.0)
        p = min(mean / 7, 0.95)
        out += [1 if rng.random() < p else 0 for _ in range(7)]
    return out


def export_series(variant_id, demand, pattern="smooth", eligible=True, reasons=(), price="10", level="0.95", critical=False):
    return {"variant_id": variant_id, "product_id": variant_id, "price": price, "start_day": "2026-01-01", "demand": list(demand),
            "censored": [False] * len(demand), "service_level": level, "clinical_critical": critical,
            "segment": {"abc": "B", "xyz": "Y", "pattern": pattern, "forecast_eligible": eligible, "reasons": list(reasons)}}


@pytest.fixture
def make_export():
    def _make(seed=1, n_smooth=3):
        rng = random.Random(seed)  # noqa: S311 - deterministic test data
        series = [export_series(i, weekly_series(rng, 30, 5), "smooth") for i in range(1, n_smooth + 1)]
        series.append(export_series(100, weekly_series(rng, 6, 3), "new", False, ["new"]))
        series.append(export_series(101, weekly_series(rng, 30, 0.3), "intermittent", False, ["too_sparse"], critical=True))
        return {"through_day": "2026-10-31", "count": len(series), "series": series}

    return _make


class Fixed:
    """Test policy with a fixed rate."""

    def __init__(self, name, rate):
        self.name, self.version, self._rate = name, "t", rate

    def rate(self, history):
        return self._rate


D = Decimal
