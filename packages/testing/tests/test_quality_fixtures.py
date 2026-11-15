"""T003: the quality fixtures are synthetic, deterministic and carry the cases the feature 012 tests need."""

import quality_fixtures as qf


def test_all_cases_exist_and_are_deterministic():
    first, second = qf.build_all(), qf.build_all()
    assert set(first) == set(qf.CASES) and first == second


def test_ids_are_fictional():
    for sku, variant_id in qf.CASES.values():
        assert sku.startswith("EJ-91") and 910000 <= variant_id < 920000


def test_series_lengths_match_flags():
    for series in qf.build_all().values():
        assert len(series["demand"]) == len(series["censored"])


def test_stockout_days_are_censored_with_zero_sales():
    s = qf.build_series("stockout")
    assert [d for d, c in enumerate(s["censored"]) if c] == list(qf.STOCKOUT_DAYS)
    assert all(s["demand"][d] == 0 for d in qf.STOCKOUT_DAYS)


def test_outlier_is_far_above_the_rest():
    s = qf.build_series("outlier")
    assert s["demand"][qf.OUTLIER_DAY] == qf.OUTLIER_VALUE and max(v for d, v in enumerate(s["demand"]) if d != qf.OUTLIER_DAY) < 10


def test_short_history_and_seed_only_shapes():
    assert len(qf.build_series("short_history")["demand"]) == 20
    assert sum(qf.build_series("seed_only")["demand"][:60]) == 0
    assert {p for _, _, p in qf.SEED_ROWS["seed_only"]} == {"estimated"}


def test_rejected_movements_have_reason_codes():
    assert len(qf.REJECTED_MOVEMENTS["rejected"]) == 5 and all(reason for _, _, reason in qf.REJECTED_MOVEMENTS["rejected"])
