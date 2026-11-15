"""T029: the explanation of one forecast - class, method and why, eligibility, censored days, provenance (feature 012, FR-008 to FR-010, FR-013)."""

from policies.estimators import BASELINE
from policies.fallback import NAME as FALLBACK
from runs.eligibility import Decision
from runs.explanation import explain

VERSIONS = {"minmax_poisson": "v1", "croston": "v1", BASELINE: "v1", FALLBACK: "v1"}


def series(pattern="smooth", n=60, censored_days=0, **extra):
    s = {"variant_id": 1, "sku": "EJ-1", "start_day": "2026-01-01", "demand": [2] * n, "censored": [False] * (n - censored_days) + [True] * censored_days,
         "segment": {"abc": "A", "xyz": "X", "pattern": pattern, "forecast_eligible": True, "reasons": [], "config_version_id": "defaults-abc"}}
    s.update(extra)
    return s


def run(s, decision, policy_used, mean=12.5, adopted=None, seed_used=False, seed_days=0):
    return explain(s, decision, policy_used, mean, adopted or {}, VERSIONS, "ds-1" if seed_used else None, seed_days)


def test_an_adopted_method_is_explained_with_its_versions_and_class():
    e = run(series(), Decision("minmax_poisson", True, ()), "minmax_poisson", adopted={"smooth": "minmax_poisson"})
    assert (e["abc"], e["xyz"], e["pattern"], e["intermittent"]) == ("A", "X", "smooth", False)
    assert (e["method"], e["method_reason_code"], e["model_version"]) == ("minmax_poisson", "backtest_adopted", "minmax_poisson@v1")
    assert (e["eligibility"], e["eligibility_reason_codes"], e["expected"]) == ("eligible", [], 12.5)
    assert e["config_version_id"] == "defaults-abc" and e["dataset_version_id"] is None and e["sku"] == "EJ-1"


def test_the_baseline_is_named_as_the_default_when_nothing_was_adopted():
    e = run(series(), Decision(BASELINE, True, ()), BASELINE, adopted={})
    assert e["method"] == BASELINE and e["method_reason_code"] == "baseline_default"


def test_a_method_that_could_not_run_falls_back_to_the_baseline_and_says_so():
    e = run(series(), Decision("croston", True, ()), BASELINE, adopted={"smooth": "croston"})
    assert (e["method"], e["method_reason_code"]) == (BASELINE, "method_fallback_to_baseline")


def test_intermittent_and_lumpy_products_are_flagged_intermittent():
    assert run(series("intermittent"), Decision("croston", True, ()), "croston", adopted={"intermittent": "croston"})["intermittent"] is True
    assert run(series("lumpy"), Decision("croston", True, ()), "croston", adopted={"lumpy": "croston"})["intermittent"] is True


def test_a_not_eligible_product_has_no_forecast_figure_and_names_the_reason_and_fallback():
    s = series("new", n=20)
    s["segment"]["forecast_eligible"] = False
    e = run(s, Decision(FALLBACK, False, ("new",)), FALLBACK, mean=None)
    assert (e["eligibility"], e["eligibility_reason_codes"]) == ("not_eligible", ["new"])
    assert (e["expected"], e["low"], e["high"], e["confidence"]) == (None, None, None, None)
    assert (e["method"], e["method_reason_code"]) == (FALLBACK, "min_max_fallback")


def test_censored_and_excluded_days_are_counted_and_the_window_is_reported():
    e = run(series(n=60, censored_days=16, anomaly_excluded_days=2), Decision("minmax_poisson", True, ()), "minmax_poisson", adopted={"smooth": "minmax_poisson"})
    assert (e["censored_days"], e["anomaly_days_excluded"]) == (16, 2)
    assert (e["history_start"], e["history_end"]) == ("2026-01-01", "2026-03-01")


def test_seed_days_are_estimated_and_never_counted_as_observed():
    e = run(series(n=100), Decision("minmax_poisson", True, ("seed_used",)), "minmax_poisson", adopted={"smooth": "minmax_poisson"}, seed_used=True, seed_days=30)
    assert e["provenance_mix"] == {"observed": 70, "estimated": 30, "manual": 0} and e["dataset_version_id"] == "ds-1"


def test_a_series_from_a_local_export_is_never_observed():
    e = run(series(n=40, provenance="estimated"), Decision("minmax_poisson", True, ()), "minmax_poisson", adopted={"smooth": "minmax_poisson"})
    assert e["provenance_mix"] == {"observed": 0, "estimated": 40, "manual": 0}


def test_the_same_input_gives_the_same_explanation():
    args = (series(), Decision("minmax_poisson", True, ()), "minmax_poisson")
    assert run(*args, adopted={"smooth": "minmax_poisson"}) == run(*args, adopted={"smooth": "minmax_poisson"})
