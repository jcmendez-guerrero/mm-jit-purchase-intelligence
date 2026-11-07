"""T177 (FR-005, FR-008, T122): the trend response keeps actual ERP demand and the forecast apart; the forecast never changes the actual series."""

from datetime import timedelta
from decimal import Decimal

from conftest import auth
from dashboard.kpis import Filters, demand_trend, forecast_series
from test_aggregates import TODAY, seed

D = Decimal


class Bands:
    """A forecast source: per eligible variant (daily mean, daily upper bound, rests on imported estimates)."""

    def __init__(self, bands):
        self.bands = bands

    def daily_means(self):
        return {v: b[0] for v, b in self.bands.items()}

    def daily_bands(self):
        return self.bands


def series(engine, source=None, f=None, days=28):
    with engine.connect() as c:
        return forecast_series(c, TODAY, f or Filters(), source, days)


def test_without_a_forecast_the_series_is_empty_and_says_why(engine):
    seed(engine)
    out = series(engine)
    assert out == {"points": [], "variants": 0, "seed_assisted": 0, "reason": "no_forecast"}


def test_the_forecast_is_the_sum_over_eligible_variants_in_scope_for_the_coming_days(engine):
    seed(engine)
    out = series(engine, Bands({1: (2.0, 3.0, False), 2: (1.0, 1.5, True), 99: (50.0, 60.0, False)}))      # 99 is not in the database: out of scope
    assert out["variants"] == 2 and out["seed_assisted"] == 1 and out["reason"] is None
    pts = out["points"]
    assert len(pts) == 28 and pts[0]["day"] == (TODAY + timedelta(days=1)).isoformat() and pts[-1]["day"] == (TODAY + timedelta(days=28)).isoformat()
    assert all(p["mean"] == "3.00" and p["upper"] == "4.50" and p["kind"] == "forecast" for p in pts)


def test_the_upper_bound_never_falls_below_the_mean(engine):
    seed(engine)
    out = series(engine, Bands({1: (2.0, 1.0, False)}))                    # a bad band from upstream is lifted to the mean, not shown inverted
    assert out["points"][0]["upper"] == out["points"][0]["mean"] == "2.00"


def test_category_and_family_filters_narrow_the_forecast_like_the_actual_series(engine):
    seed(engine)
    src = Bands({1: (2.0, 3.0, False), 2: (1.0, 1.5, False), 3: (4.0, 5.0, False)})
    assert series(engine, src, Filters(category="A"))["variants"] == 1
    assert series(engine, src, Filters(category="B"))["variants"] == 2


def test_a_warehouse_filter_omits_the_forecast_because_it_is_company_wide(engine):
    seed(engine)
    out = series(engine, Bands({1: (2.0, 3.0, False)}), Filters(warehouse_id=1))
    assert out["points"] == [] and out["reason"] == "company_wide_only"


def test_the_forecast_never_changes_the_actual_series(engine):
    seed(engine)
    with engine.connect() as c:
        before = demand_trend(c, TODAY, 30, Filters())
    series(engine, Bands({1: (2.0, 3.0, False)}))
    with engine.connect() as c:
        after = demand_trend(c, TODAY, 30, Filters())
    assert before == after and all(p["kind"] == "actual_erp" for p in after)


def test_the_route_returns_both_series_apart(client, engine):
    seed(engine)
    body = client.get("/dashboard/demand-trend?days=7", headers=auth()).json()
    assert set(body) >= {"series", "estimated", "estimated_basis"} and body["estimated"] == []
    assert body["estimated_basis"]["reason"] == "no_forecast"


def test_the_http_source_reads_the_mean_the_upper_bound_and_the_seed_flag_for_eligible_variants_only():
    import httpx
    from dashboard.forecast_source import HttpForecastMeans

    body = {"variants": {
        "1": {"eligible": True, "reasons": [], "horizons": {"28": {"mean": 56.0, "quantiles": {"0.95": 84.0}}}},
        "2": {"eligible": True, "reasons": ["seed_used"], "horizons": {"28": {"mean": 28.0, "quantiles": {}}}},
        "3": {"eligible": False, "reasons": ["new"], "horizons": {"28": {"mean": None, "quantiles": {"min": 1, "max": 2}}}}}}
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=body)))
    src = HttpForecastMeans("http://forecast", "t", client)
    assert src.daily_bands() == {1: (2.0, 3.0, False), 2: (1.0, None, True)}
    assert src.daily_means() == {1: 2.0, 2: 1.0}
    none = HttpForecastMeans("http://forecast", "t", httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(404))))
    assert none.daily_bands() == {} and none.daily_means() == {}
