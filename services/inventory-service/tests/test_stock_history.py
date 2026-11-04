"""T049: backward stock reconstruction, censoring and mismatch flag."""

from datetime import date, timedelta

from demand.common import Mov
from demand.stock_history import reconstruct

D = date(2026, 3, 1)


def mov(i, day_offset, reason, qty, variant=1):
    return Mov(i, variant, 1, D + timedelta(days=day_offset), reason, qty, False)


def by_day(rows):
    return {r.day: r for r in rows}


def test_history_is_rebuilt_backwards_from_the_current_snapshot():
    ms = [mov(1, 0, "initial_stock", 10), mov(2, 1, "sale_shipment", -3), mov(3, 2, "purchase_receipt", 5), mov(4, 3, "sale_shipment", -2)]
    rows = by_day(reconstruct(ms, {1: 10}, D + timedelta(days=3)))
    assert [rows[D + timedelta(days=i)].on_hand for i in range(4)] == [10, 7, 12, 10]
    assert all(r.reconciled_ok for r in rows.values())


def test_days_without_movements_carry_the_balance():
    ms = [mov(1, 0, "initial_stock", 4), mov(2, 4, "sale_shipment", -1)]
    rows = by_day(reconstruct(ms, {1: 3}, D + timedelta(days=5)))
    assert [rows[D + timedelta(days=i)].on_hand for i in range(6)] == [4, 4, 4, 4, 3, 3]


def test_days_at_or_below_zero_are_censored():
    ms = [mov(1, 0, "initial_stock", 2), mov(2, 1, "sale_shipment", -2), mov(3, 4, "purchase_receipt", 6)]
    rows = by_day(reconstruct(ms, {1: 6}, D + timedelta(days=5)))
    censored = [(r.day - D).days for r in rows.values() if r.censored]
    assert censored == [1, 2, 3, 4]  # sold out on day 1, empty on 2 and 3, restocked on day 4 (opened empty)
    assert not rows[D].censored and not rows[D + timedelta(days=5)].censored


def test_a_negative_reconstructed_balance_is_censored_not_an_error():
    ms = [mov(1, 0, "initial_stock", 1), mov(2, 1, "sale_shipment", -2), mov(3, 2, "purchase_receipt", 5)]
    rows = by_day(reconstruct(ms, {1: 4}, D + timedelta(days=2)))
    assert rows[D + timedelta(days=1)].on_hand == -1 and rows[D + timedelta(days=1)].censored


def test_mismatch_when_the_balance_before_the_first_movement_is_not_zero():
    ms = [mov(1, 0, "sale_shipment", -1)]  # history starts mid-life: 5 units existed before the first fetched movement
    rows = reconstruct(ms, {1: 4}, D)
    assert not rows[0].reconciled_ok


def test_mismatch_when_an_earlier_forward_snapshot_disagrees():
    ms = [mov(1, 0, "initial_stock", 10), mov(2, 2, "sale_shipment", -3)]
    ok = reconstruct(ms, {1: 7}, D + timedelta(days=3), {1: {D + timedelta(days=1): 10}})
    bad = reconstruct(ms, {1: 7}, D + timedelta(days=3), {1: {D + timedelta(days=1): 9}})
    assert all(r.reconciled_ok for r in ok) and not any(r.reconciled_ok for r in bad)


def test_undated_movement_marks_the_variant_unreconciled_and_quarantined_ones_still_move_stock():
    undated = [mov(1, 0, "initial_stock", 3), Mov(2, 1, 1, None, "sale_shipment", -1, False)]
    assert not any(r.reconciled_ok for r in reconstruct(undated, {1: 2}, D))
    q = [mov(1, 0, "initial_stock", 3), Mov(2, 1, 1, D + timedelta(days=1), "sale_shipment", -1, True)]
    assert all(r.reconciled_ok for r in reconstruct(q, {1: 2}, D + timedelta(days=1)))


def test_variants_are_independent_and_unknown_current_stock_is_skipped():
    ms = [mov(1, 0, "initial_stock", 5, variant=1), mov(2, 0, "initial_stock", 5, variant=2)]
    rows = reconstruct(ms, {1: 5}, D)
    assert {r.variant_id for r in rows} == {1}
