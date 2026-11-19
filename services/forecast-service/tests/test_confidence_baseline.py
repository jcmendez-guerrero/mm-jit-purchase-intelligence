"""T091 (feature 018, FR-018, FR-012): a product whose method does not beat the baseline drops one confidence level; eligibility does not change."""

from datetime import UTC, datetime

import pytest
from db.tables import forecast_explanations, product_backtest
from policies.estimators import BASELINE
from policies.fallback import NAME as FALLBACK
from runs.confidence import Confidence, with_baseline
from runs.eligibility import Decision
from runs.explanation import explain
from runs.runner import run_forecast
from sqlalchemy import insert, select
from tests_helpers import FakeSource, NullWriter

VERSIONS = {"minmax_poisson": "v1", "croston": "v1", BASELINE: "v1", FALLBACK: "v1"}


@pytest.mark.parametrize("level,expected", [("alta", "media"), ("media", "baja"), ("baja", "baja")])
def test_not_beating_the_baseline_drops_one_level_and_names_the_reason(level, expected):
    c = with_baseline(Confidence(level, ["short_history"]), False)
    assert c.level == expected and c.reasons == ["short_history", "no_supera_baseline"]


@pytest.mark.parametrize("beats", [True, None])
def test_beating_it_or_having_no_backtest_changes_nothing(beats):
    c = Confidence("alta", [])
    assert with_baseline(c, beats) == c


def _series():
    return {"variant_id": 1, "sku": "EJ-1", "start_day": "2026-01-01", "demand": [2] * 120, "censored": [False] * 120,
            "segment": {"abc": "A", "xyz": "X", "pattern": "smooth", "forecast_eligible": True, "reasons": [], "config_version_id": "c"}}


def test_the_explanation_shows_the_lower_level_and_the_reason_but_stays_eligible():
    base = explain(_series(), Decision("minmax_poisson", True, ()), "minmax_poisson", 12.0, {}, VERSIONS, None)
    worse = explain(_series(), Decision("minmax_poisson", True, ()), "minmax_poisson", 12.0, {}, VERSIONS, None, beats_baseline=False)
    assert (base["confidence"], base["eligibility"]) == ("alta", "eligible")
    assert (worse["confidence"], worse["eligibility"], worse["expected"]) == ("media", "eligible", 12.0)
    assert worse["confidence_reason_codes"] == ["no_supera_baseline"]


def _explained(engine, make_export, tmp_path, beats):
    export = make_export(seed=3)
    first = export["series"][0]
    if beats is not None:
        with engine.begin() as c:
            c.execute(insert(product_backtest).values(backtest_run_id="b1", variant_id=first["variant_id"], sku=first.get("sku"), periods=5, beats_baseline=beats,
                                                      model_version="m", created_at=datetime(2026, 11, 1, tzinfo=UTC)))
    run_forecast(engine, FakeSource(export), NullWriter(tmp_path))
    with engine.connect() as c:
        return {r.variant_id: r for r in c.execute(select(forecast_explanations)).all()}, first["variant_id"]


def test_without_a_backtest_no_product_gets_the_reason(engine, make_export, tmp_path):
    rows, _ = _explained(engine, make_export, tmp_path, None)
    assert rows and all("no_supera_baseline" not in r.confidence_reason_codes for r in rows.values())


def test_a_run_reads_the_latest_backtest_and_changes_only_that_products_confidence(engine, make_export, tmp_path):
    rows, vid = _explained(engine, make_export, tmp_path, False)
    assert "no_supera_baseline" in rows[vid].confidence_reason_codes
    assert all("no_supera_baseline" not in r.confidence_reason_codes for k, r in rows.items() if k != vid)


def test_a_label_that_drops_to_baja_only_because_of_the_baseline_still_publishes_its_figure(engine, make_export, tmp_path):
    """T097 (FR-013 and FR-018): the min/max fallback follows the quality of the data (`assess`); the baseline finding only lowers the label and adds the warning."""
    from db.tables import forecast_values

    export = make_export(seed=3)
    first = export["series"][0]
    first["segment"]["xyz"] = "Z"                                        # one quality flag: media before the baseline finding
    with engine.begin() as c:
        c.execute(insert(product_backtest).values(backtest_run_id="b1", variant_id=first["variant_id"], periods=5, beats_baseline=False, model_version="m",
                                                  created_at=datetime(2026, 11, 1, tzinfo=UTC)))
    run_forecast(engine, FakeSource(export), NullWriter(tmp_path))
    with engine.connect() as c:
        explained = c.execute(select(forecast_explanations).where(forecast_explanations.c.variant_id == first["variant_id"])).one()
        values = c.execute(select(forecast_values).where(forecast_values.c.variant_id == first["variant_id"])).all()
    assert explained.confidence == "baja" and "no_supera_baseline" in explained.confidence_reason_codes and explained.eligibility == "eligible"
    assert values and all(v.eligible and v.policy_used != FALLBACK and v.mean is not None for v in values)       # a figure, not min/max


def test_a_later_backtest_that_beats_the_baseline_removes_the_flag(engine, make_export, tmp_path):
    export = make_export(seed=3)
    vid = export["series"][0]["variant_id"]
    with engine.begin() as c:
        for run_id, beats, day in (("b1", False, 1), ("b2", True, 2)):
            c.execute(insert(product_backtest).values(backtest_run_id=run_id, variant_id=vid, periods=5, beats_baseline=beats, model_version="m",
                                                      created_at=datetime(2026, 11, day, tzinfo=UTC)))
    run_forecast(engine, FakeSource(export), NullWriter(tmp_path))
    with engine.connect() as c:
        row = c.execute(select(forecast_explanations).where(forecast_explanations.c.variant_id == vid)).one()
    assert "no_supera_baseline" not in row.confidence_reason_codes
