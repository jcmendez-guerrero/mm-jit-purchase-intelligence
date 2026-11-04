"""T047: demand = sale_shipment - return_customer; other reasons excluded (kept in their own series)."""

from datetime import date

from demand.common import Mov
from demand.losses import flows_from_movements
from demand.provider import MovementsDemandProvider
from generator import generate
from generator.dataset import REASONS

D = date(2026, 3, 2)


def mov(i, reason, qty, day=D, variant=1, wh=1, q=False):
    return Mov(i, variant, wh, day, reason, qty, q)


def test_demand_is_sales_minus_returns():
    rows = MovementsDemandProvider().daily_demand([mov(1, "sale_shipment", -3), mov(2, "sale_shipment", -2), mov(3, "return_customer", 1)])
    assert [(r.variant_id, r.warehouse_id, r.day, r.demand_qty) for r in rows] == [(1, 1, D, 4)]


def test_a_day_with_only_a_return_has_negative_demand():
    assert MovementsDemandProvider().daily_demand([mov(1, "return_customer", 2)])[0].demand_qty == -2


def test_every_other_reason_is_excluded_from_demand_and_present_in_flows():
    others = [r for r in REASONS if r not in ("sale_shipment", "return_customer")]
    movements = [mov(i, r, 5 if r != "adjustment_negative" else -5, variant=i) for i, r in enumerate(others, start=1)]
    assert MovementsDemandProvider().daily_demand(movements) == []
    flows = flows_from_movements(movements)
    assert {f.variant_id for f in flows} == {m.variant_id for m in movements}  # each reason lands in a flow, none vanish


def test_separate_variants_warehouses_and_days_stay_separate():
    ms = [mov(1, "sale_shipment", -1), mov(2, "sale_shipment", -1, wh=2), mov(3, "sale_shipment", -1, variant=2), mov(4, "sale_shipment", -1, day=date(2026, 3, 3))]
    assert len(MovementsDemandProvider().daily_demand(ms)) == 4


def test_quarantined_and_undated_movements_are_excluded():
    ms = [mov(1, "sale_shipment", -9, q=True), mov(2, "sale_shipment", -9, day=None), mov(3, "sale_shipment", -1)]
    rows = MovementsDemandProvider().daily_demand(ms)
    assert [r.demand_qty for r in rows] == [1]


def test_lineage_is_deterministic_and_changes_with_inputs():
    a = MovementsDemandProvider().daily_demand([mov(1, "sale_shipment", -1), mov(2, "sale_shipment", -1)])[0].lineage
    b = MovementsDemandProvider().daily_demand([mov(2, "sale_shipment", -1), mov(1, "sale_shipment", -1)])[0].lineage
    c = MovementsDemandProvider().daily_demand([mov(1, "sale_shipment", -1), mov(3, "sale_shipment", -1)])[0].lineage
    assert a == b != c


def test_over_the_synthetic_dataset_demand_matches_an_independent_sum():
    data = generate()
    ms = [Mov(m["id"], m["variant_id"], m["warehouse_id"] if m["warehouse_id"] is not None else 0, date.fromisoformat(m["created_at"][:10]),
              m["reason"], m["quantity"], False) for m in data.movements]
    got = sum(r.demand_qty for r in MovementsDemandProvider().daily_demand(ms))
    assert got == -sum(m["quantity"] for m in data.movements if m["reason"] in ("sale_shipment", "return_customer"))
