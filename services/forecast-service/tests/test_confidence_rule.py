"""T041: the confidence rule - flags from history sufficiency and data quality, and the level they give (feature 012, FR-012, research R5)."""

from runs.confidence import assess


def series(n=120, *, demand=None, censored_days=0, xyz="X", excluded=0, provenance="observed"):
    demand = demand if demand is not None else [2] * n
    return {"demand": demand, "censored": [False] * (len(demand) - censored_days) + [True] * censored_days, "anomaly_excluded_days": excluded,
            "provenance": provenance, "segment": {"xyz": xyz}}


def test_a_long_dense_clean_history_has_high_confidence_and_no_flags():
    c = assess(series())
    assert (c.level, c.reasons) == ("alta", [])


def test_one_or_two_flags_give_medium_confidence_and_name_them():
    one = assess(series(60))
    assert (one.level, one.reasons) == ("media", ["short_history"])
    two = assess(series(60, xyz="Z"))
    assert (two.level, two.reasons) == ("media", ["short_history", "high_variability"])


def test_three_flags_give_low_confidence():
    c = assess(series(60, xyz="Z", censored_days=30))
    assert c.level == "baja" and set(c.reasons) == {"short_history", "high_variability", "many_stockout_days"}


def test_sparse_sales_are_flagged():
    demand = ([1] + [0] * 19) * 6                                       # 5 % of days sell
    assert "sparse_sales" in assess(series(demand=demand)).reasons


def test_many_stockout_days_and_many_excluded_days_are_flagged_at_their_thresholds():
    assert "many_stockout_days" not in assess(series(120, censored_days=36)).reasons         # exactly 30 %: not above
    assert "many_stockout_days" in assess(series(120, censored_days=37)).reasons
    assert "many_excluded_days" not in assess(series(120, excluded=6)).reasons               # exactly 5 %
    assert "many_excluded_days" in assess(series(120, excluded=7)).reasons


def test_data_that_is_mostly_estimated_is_flagged_whether_from_seed_days_or_a_local_export():
    assert "mostly_estimated" in assess(series(100), seed_days=60).reasons
    assert "mostly_estimated" not in assess(series(100), seed_days=40).reasons
    assert "mostly_estimated" in assess(series(100, provenance="estimated")).reasons


def test_an_empty_history_does_not_divide_by_zero():
    c = assess(series(demand=[]))
    assert c.level in ("media", "baja") and "short_history" in c.reasons


def test_the_same_input_gives_the_same_assessment():
    assert assess(series(60, xyz="Z")) == assess(series(60, xyz="Z"))
