"""T121 (forecast side) + T129: the previous run is scored against real demand once a week of it exists."""

from datetime import date, timedelta
from decimal import Decimal

from conftest import export_series
from db.tables import forecast_accuracy, forecast_runs, forecast_values
from runs.accuracy import latest_accuracy
from runs.runner import RunConfig, run_forecast
from sqlalchemy import func, select
from tests_helpers import FakeSource, NullWriter

START = date(2026, 6, 1)


def series(variant, demand, censored=None, abc="B"):
    s = export_series(variant, demand, "smooth")
    s["start_day"] = START.isoformat()
    s["censored"] = censored if censored is not None else [False] * len(demand)
    s["segment"]["abc"] = abc
    return s


def export(n, tail, censor_tail_day=None):
    """Variants 1 (group B) and 2 (group A). ``tail`` is the daily demand of variant 1 after day 120; variant 2 may have a stocked-out day in that window."""
    base = [2] * 120
    s1 = series(1, base + [tail] * (n - 120), abc="B")
    s2d = [1] * n
    c2 = [False] * n
    if censor_tail_day is not None:
        c2[120 + censor_tail_day] = True
    s2 = series(2, s2d, c2, abc="A")
    return {"through_day": (START + timedelta(days=n - 1)).isoformat(), "count": 2, "series": [s1, s2]}


def acc_now(engine):
    with engine.begin() as c:
        return latest_accuracy(c)


def forecast_mean(engine, run_id, variant):
    with engine.connect() as c:
        return c.execute(select(forecast_values.c.mean).where(forecast_values.c.run_id == run_id, forecast_values.c.variant_id == variant, forecast_values.c.horizon_days == 7)).scalar()


def test_the_previous_run_is_scored_against_the_next_seven_days_of_real_demand(engine, tmp_path):
    first = run_forecast(engine, FakeSource(export(120, 0)), NullWriter(tmp_path), RunConfig())
    assert acc_now(engine)["metrics"] == {}                                      # nothing to compare with yet
    run_forecast(engine, FakeSource(export(130, 4)), NullWriter(tmp_path), RunConfig())
    f = forecast_mean(engine, first.run_id, 1)
    assert f is not None
    acc = acc_now(engine)
    assert acc["run_id"] == first.run_id and acc["window_days"] == 7
    actual = 4 * 7
    expected_wape = abs(actual - f) / actual
    m = acc["metrics"]["B"]
    assert Decimal(m["wape"]) == Decimal(str(round(expected_wape, 4))) and Decimal(m["bias"]) == Decimal(str(round((f - actual) / actual, 4)))


def test_a_variant_with_a_stocked_out_day_is_not_scored_but_counts_in_the_stockout_share(engine, tmp_path):
    run_forecast(engine, FakeSource(export(120, 0)), NullWriter(tmp_path), RunConfig())
    run_forecast(engine, FakeSource(export(130, 4, censor_tail_day=2)), NullWriter(tmp_path), RunConfig())
    m = acc_now(engine)["metrics"]
    assert Decimal(m["all"]["stockout_rate"]) == Decimal("0.5")                                    # one of the two evaluated variants
    assert "wape" not in m["A"] and Decimal(m["A"]["stockout_rate"]) == Decimal("1.0") and "wape" in m["B"]


def test_scoring_waits_until_a_full_week_exists_and_never_repeats(engine, tmp_path):
    run_forecast(engine, FakeSource(export(120, 0)), NullWriter(tmp_path), RunConfig())
    run_forecast(engine, FakeSource(export(125, 4)), NullWriter(tmp_path), RunConfig())             # only 5 days: no accuracy yet
    with engine.connect() as c:
        assert c.execute(select(func.count()).select_from(forecast_accuracy)).scalar() == 0
    run_forecast(engine, FakeSource(export(132, 4)), NullWriter(tmp_path), RunConfig())             # now 7 days after the second run: it is scored
    run_forecast(engine, FakeSource(export(134, 4)), NullWriter(tmp_path), RunConfig())             # the third run has no full week yet; the second is not scored twice
    with engine.connect() as c:
        runs = c.execute(select(func.count(func.distinct(forecast_accuracy.c.run_id)))).scalar()
        rows = c.execute(select(func.count()).select_from(forecast_accuracy)).scalar()
        total = c.execute(select(func.count()).select_from(forecast_runs)).scalar()
    assert runs == 1 and total == 4 and rows > 0


def test_the_http_endpoints_serve_accuracy_and_the_run_list(engine, tmp_path):
    from api import build_router, get_engine
    from fastapi.testclient import TestClient
    from mmi_common.auth import Principal
    from mmi_common.service import create_service_app

    class V:
        def validate(self, token, required_roles=()):
            return Principal("u", frozenset({"viewer"}), None)

    run_forecast(engine, FakeSource(export(120, 0)), NullWriter(tmp_path), RunConfig())
    run_forecast(engine, FakeSource(export(130, 4)), NullWriter(tmp_path), RunConfig())
    app = create_service_app("forecast-service", validator=V())
    app.include_router(build_router(app))
    app.dependency_overrides[get_engine] = lambda: engine
    c = TestClient(app)
    h = {"Authorization": "Bearer x"}
    assert "B" in c.get("/accuracy", headers=h).json()["metrics"]
    runs = c.get("/runs", headers=h).json()["runs"]
    assert len(runs) == 2 and runs[0]["status"] == "completed" and c.get("/accuracy").status_code == 401
