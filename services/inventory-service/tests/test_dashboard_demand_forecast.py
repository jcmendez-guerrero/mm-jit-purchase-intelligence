"""T021 (inventory part): the demand and forecast indicators, from the synthetic reference dataset (TOTALS.md).

Demand = real ERP sales in the period, censored rows left out and counted. Forecast = the forecast-eligible variants' next 28 days, with the variants that have none counted apart.
"""

from dashboard.kpis import Filters, demand_summary, forecast_summary
from reference_dataset import TODAY, seed_reference


class Means:
    def __init__(self, m):
        self.m = m

    def daily_means(self):
        return self.m


class Bands(Means):
    def __init__(self, b):
        super().__init__({v: x[0] for v, x in b.items()})
        self.b = b

    def daily_bands(self):
        return self.b


def demand(engine, f=None, days=60):
    with engine.connect() as c:
        return demand_summary(c, TODAY, days, f or Filters())


def forecast(engine, source, f=None):
    with engine.connect() as c:
        return forecast_summary(c, TODAY, f or Filters(), source)


def test_demand_counts_real_sales_in_the_period_and_leaves_censored_rows_out(engine):
    seed_reference(engine)
    d = demand(engine)
    # SYN-001 sold 3 a day for 60 days = 180; SYN-002 sold 1 a day for 60 days but today's row is censored = 59
    assert d["units"] == 239 and d["daily_average"] == "3.98" and d["censored_rows"] == 1 and d["variants_with_demand"] == 2 and d["days"] == 60 and d["state"] == "ok"


def test_demand_follows_the_filters(engine):
    seed_reference(engine)
    assert demand(engine, Filters(category="A"))["units"] == 180
    assert demand(engine, Filters(supplier_id="sup-b"))["units"] == 59
    assert demand(engine, Filters(warehouse_id=1))["units"] == 239


def test_demand_with_nothing_to_count_says_so_instead_of_zero(engine):
    seed_reference(engine)
    d = demand(engine, Filters(warehouse_id=2))
    assert d["state"] == "no_data" and d["units"] is None and d["daily_average"] is None
    assert demand(engine, days=7)["units"] == 7 * 3 + 7 * 1 - 1          # the censored row of today is left out here too


def test_the_forecast_adds_the_next_28_days_of_the_eligible_variants_and_counts_those_without_one(engine):
    seed_reference(engine)
    f = forecast(engine, Means({1: 2.0, 2: 0.5, 5: 1.0}))
    assert f["state"] == "ok" and f["units"] == "98.00" and f["upper"] == "98.00"          # 3.5 a day x 28
    assert f["variants"] == 3 and f["incomplete"] == 2 and f["days"] == 28 and f["reason"] is None


def test_the_forecast_reports_its_upper_band_and_the_estimates_it_rests_on(engine):
    seed_reference(engine)
    f = forecast(engine, Bands({1: (2.0, 3.0, False), 2: (0.5, 1.0, True)}))
    assert f["units"] == "70.00" and f["upper"] == "112.00" and f["seed_assisted"] == 1


def test_without_a_forecast_or_with_a_warehouse_the_indicator_says_why(engine):
    seed_reference(engine)
    none = forecast(engine, None)
    assert none["state"] == "no_data" and none["units"] is None and none["reason"] == "no_forecast"
    wh = forecast(engine, Means({1: 2.0}), Filters(warehouse_id=1))
    assert wh["state"] == "no_data" and wh["units"] is None and wh["reason"] == "company_wide_only"
