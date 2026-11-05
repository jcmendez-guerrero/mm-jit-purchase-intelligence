"""T058: ABC/XYZ/pattern classification, eligibility, criticality and service levels on known profiles."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from classification.criticality import CriticalityError, critical_products, set_critical
from classification.run import compute_segments
from classification.segments import SeriesInput, assign_abc, classify_series
from classification.service_levels import ServiceLevelError, effective_target, history, set_target
from db.tables import (
    ALL_WAREHOUSES,
    criticality_changes,
    demand_observations,
    product_segments,
    products,
    stock_history,
    stock_movements,
    variants,
)
from sqlalchemy import insert, select

END = date(2026, 10, 31)


def series(weekly, vid=1, price="10", censored_weeks=(), **kw):
    """Known profile: ``weekly`` units per 7-day block, sold on the first day of the block; ends at END."""
    n = len(weekly) * 7
    days = [END - timedelta(days=n - 1 - i) for i in range(n)]
    demand = [0] * n
    censored = [False] * n
    for w, units in enumerate(weekly):
        demand[w * 7] = units
        if w in censored_weeks:
            censored[w * 7:(w + 1) * 7] = [True] * 7
    return SeriesInput(vid, days, demand, censored, Decimal(price), **kw)


SMOOTH = [7, 6, 8, 7, 7, 6, 8, 7] * 4            # sells every week, low variability
INTERMITTENT = [0, 0, 2] * 11                    # every third week, constant size
LUMPY = [0, 0, 1, 0, 0, 14, 0, 0, 2, 0, 0, 16] * 3  # every third week, wildly different sizes


def test_known_profiles_get_the_expected_pattern_and_xyz():
    smooth = classify_series(series(SMOOTH), "A")
    assert (smooth.pattern, smooth.xyz, smooth.eligible, smooth.reasons) == ("smooth", "X", True, [])
    inter = classify_series(series(INTERMITTENT), "C")
    assert (inter.pattern, inter.xyz, inter.eligible) == ("intermittent", "Z", True)
    lumpy = classify_series(series(LUMPY), "B")
    assert lumpy.pattern == "lumpy" and lumpy.xyz == "Z" and lumpy.metrics["cv2"] > 0.49


def test_frequent_but_erratic_demand_counts_as_lumpy():
    assert classify_series(series([1, 20, 2, 18, 1, 25, 3, 19] * 4), "A").pattern == "lumpy"


def test_metrics_carry_the_rationale():
    m = classify_series(series(INTERMITTENT), "C").metrics
    assert m["adi"] == 3.0 and m["cv2"] == 0.0 and m["nonzero_blocks"] == 11 and m["history_days"] == 231


def test_new_and_discontinued_take_precedence_and_are_not_eligible():
    new = classify_series(series([5, 6, 5, 7, 6, 5]), "B")
    assert new.pattern == "new" and new.reasons == ["new"] and not new.eligible
    disc = classify_series(series(SMOOTH, product_discontinued=True), "C")
    assert disc.pattern == "discontinued" and "discontinued" in disc.reasons and not disc.eligible


def test_sparse_unreconciled_censored_and_pending_review_each_block_eligibility_with_a_reason():
    sparse = classify_series(series([0] * 28 + [1, 0, 0, 1]), "C")
    assert "too_sparse" in sparse.reasons and not sparse.eligible
    assert classify_series(series(SMOOTH, history_reconciled=False), "A").reasons == ["history_unreconciled"]
    assert classify_series(series(SMOOTH, pending_review=True), "A").reasons == ["pending_review"]
    cens = classify_series(series(SMOOTH, censored_weeks={w for w in range(32) if w % 4}), "A")
    assert "mostly_censored" in cens.reasons and cens.metrics["censored_blocks"] == 24


def test_censored_weeks_are_excluded_from_the_statistics_not_counted_as_zero_demand():
    # alternate empty-shelf weeks (no sales possible) with normal weeks: without exclusion this would look intermittent
    weekly = [7 if w % 2 == 0 else 0 for w in range(32)]
    seg = classify_series(series(weekly, censored_weeks={w for w in range(32) if w % 2}), "A")
    assert seg.pattern == "smooth" and seg.metrics["blocks"] == 16


def test_no_sales_at_all_is_c_z_and_ineligible():
    seg = classify_series(series([0] * 30), "C")
    assert (seg.xyz, seg.eligible) == ("Z", False) and seg.metrics["adi"] is None


def test_abc_uses_cumulative_value_and_is_deterministic():
    values = {1: Decimal(100), 2: Decimal(50), 3: Decimal(30), 4: Decimal(10), 5: Decimal(5), 6: Decimal(5), 7: Decimal(0)}
    assert assign_abc(values) == {1: "A", 2: "A", 3: "A", 4: "B", 5: "C", 6: "C", 7: "C"}
    assert assign_abc({1: Decimal(5), 2: Decimal(5)}) == assign_abc({2: Decimal(5), 1: Decimal(5)})
    assert assign_abc({1: Decimal(0)}) == {1: "C"}


# ---- storage-backed -------------------------------------------------------------------------------------

def seed_variant(engine, vid, pid, weekly, price="10", status="active", reconciled=True):
    s = series(weekly, vid, price)
    with engine.begin() as c:
        if c.execute(select(products.c.external_id).where(products.c.external_id == pid)).first() is None:
            c.execute(insert(products).values(external_id=pid, name=f"P{pid}", status=status, missed_syncs=0))
        c.execute(insert(variants).values(external_id=vid, product_id=pid, sku=f"S{vid}", price=Decimal(price)))
        c.execute(insert(stock_history), [{"variant_id": vid, "warehouse_id": ALL_WAREHOUSES, "day": d, "on_hand_reconstructed": 50,
                                           "censored": False, "reconciled_ok": reconciled} for d in s.days])
        rows = [{"variant_id": vid, "warehouse_id": 1, "day": d, "demand_qty": q, "censored": False, "lineage": "x"} for d, q in zip(s.days, s.demand, strict=True) if q]
        c.execute(insert(demand_observations), rows)


def test_compute_segments_stores_one_row_per_variant_with_reasons(engine):
    seed_variant(engine, 1, 1, SMOOTH, price="20")
    seed_variant(engine, 2, 2, INTERMITTENT, price="2")
    seed_variant(engine, 3, 3, SMOOTH, price="5", status="discontinued")
    seed_variant(engine, 4, 4, SMOOTH, reconciled=False)
    with engine.begin() as c:
        assert compute_segments(c, now=datetime(2026, 11, 1, tzinfo=UTC)) == 4
    with engine.connect() as c:
        seg = {r.variant_id: r for r in c.execute(select(product_segments)).all()}
    assert seg[1].abc == "A" and seg[1].pattern == "smooth" and seg[1].forecast_eligible and seg[1].reason == ""
    assert seg[2].abc == "C" and seg[2].pattern == "intermittent"
    assert seg[3].pattern == "discontinued" and "discontinued" in seg[3].reason
    assert "history_unreconciled" in seg[4].reason and seg[1].metrics["value"] > 0
    with engine.begin() as c:
        compute_segments(c)                                  # replaces, never duplicates
    with engine.connect() as c:
        assert len(c.execute(select(product_segments)).all()) == 4


def test_quarantined_sales_make_the_variant_pending_review(engine):
    seed_variant(engine, 1, 1, SMOOTH)
    with engine.begin() as c:
        c.execute(insert(stock_movements).values(external_id=1, created_at_utc=datetime(2026, 10, 1, tzinfo=UTC), created_at_raw="x", variant_id=1,
                                                 warehouse_id=1, quantity=-1, reason="sale_shipment", has_note=False, quarantined=True))
        compute_segments(c)
        assert "pending_review" in c.execute(select(product_segments.c.reason)).scalar_one()


# ---- criticality ----------------------------------------------------------------------------------------

def test_criticality_is_manual_audited_and_never_inferred(engine):
    seed_variant(engine, 1, 1, SMOOTH)
    with engine.begin() as c:
        compute_segments(c)                                   # classification never touches the flag
        assert critical_products(c) == set()
        assert set_critical(c, 1, True, "buyer-1") is True and set_critical(c, 1, True, "buyer-1") is False
        assert critical_products(c) == {1}
        compute_segments(c)
        assert critical_products(c) == {1}                    # respected across recomputation
        assert set_critical(c, 1, False, "buyer-2") is True
        with pytest.raises(CriticalityError):
            set_critical(c, 99, True, "buyer-1")
        assert [(r.clinical_critical, r.changed_by) for r in c.execute(select(criticality_changes)).all()] == [(True, "buyer-1"), (False, "buyer-2")]


# ---- service levels -------------------------------------------------------------------------------------

def T(day):
    return datetime(2026, 11, day, tzinfo=UTC)


def test_default_service_levels(engine):
    with engine.connect() as c:
        t = lambda abc, pattern="smooth", crit=False: effective_target(c, 1, abc, pattern, crit, T(1))  # noqa: E731
        assert t("A") == Decimal("0.97") and t("B") == Decimal("0.95") and t("C") == Decimal("0.90")
        assert t("A", "intermittent") == Decimal("0.85") and t("C", "lumpy") == Decimal("0.85")   # sparse caps the ABC value
        assert t("C", "smooth", True) == Decimal("0.99") and t("C", "lumpy", True) == Decimal("0.99")  # critical is never reduced


def test_product_override_wins_and_history_applies_to_later_proposals_only(engine):
    with engine.begin() as c:
        set_target(c, "abc", "A", Decimal("0.98"), "admin", valid_from=T(10))
        set_target(c, "product", "7", Decimal("0.995"), "buyer", valid_from=T(12))
    with engine.connect() as c:
        assert effective_target(c, 1, "A", "smooth", False, T(9)) == Decimal("0.97")      # before the change
        assert effective_target(c, 1, "A", "smooth", False, T(11)) == Decimal("0.98")
        assert effective_target(c, 7, "A", "smooth", False, T(11)) == Decimal("0.98")
        assert effective_target(c, 7, "C", "lumpy", False, T(13)) == Decimal("0.995")     # override beats ABC and sparse cap
        assert [h["scope"] for h in history(c)] == ["abc", "product"]


def test_service_level_validation(engine):
    with engine.begin() as c:
        for args in [("abc", "D", "0.9"), ("abc", "A", "1.0"), ("abc", "A", "0.4"), ("nope", "*", "0.9"), ("product", "x", "0.9"), ("critical", "A", "0.9")]:
            with pytest.raises(ServiceLevelError):
                set_target(c, args[0], args[1], Decimal(args[2]), "admin")
