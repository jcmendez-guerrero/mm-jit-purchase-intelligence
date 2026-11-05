"""T157: a realistic weekly proposal (about 1,000 variants, several suppliers) generates within the plan's two-minute target."""

import time
from decimal import Decimal

import pytest
from builders import flat_forecast, inputs, offer, terms, variant
from proposals.generate import generate

D = Decimal
SUPPLIERS = [f"S{i}" for i in range(1, 9)]


def catalogue(n=1000):
    vs = []
    for i in range(1, n + 1):
        rate = 0.2 + (i % 17) * 0.15                                   # mostly slow movers, a few fast ones, like the real catalogue
        offers = [offer(SUPPLIERS[i % 8], f"{2 + i % 13}.{i % 90 + 10}", pack=(1, 6, 12)[i % 3], lead=2 + i % 6, moq=(0, 0, 6)[i % 3]),
                  offer(SUPPLIERS[(i + 3) % 8], f"{2 + i % 13}.{(i * 7) % 90 + 10}", pack=1, lead=3 + i % 5)]
        if i % 5 == 0:
            offers.append(offer(SUPPLIERS[(i + 5) % 8], f"{3 + i % 11}.{(i * 3) % 90 + 10}", pack=6, lead=4))
        vs.append(variant(i, offers, flat_forecast(rate), on_hand=i % 9, soon=1 if i % 4 == 0 else 0))
    terms_ = [terms(s, min_value="60", free="400", charge="9.5", min_qty=10 if k % 2 else None) for k, s in enumerate(SUPPLIERS)]
    return inputs(vs, terms_, budget="25000")


@pytest.fixture(scope="module")
def draft():
    t0 = time.perf_counter()
    d = generate(catalogue(), time_limit_s=30)
    return d, time.perf_counter() - t0


def test_generation_stays_within_the_two_minute_target(draft):
    d, seconds = draft
    assert seconds < 120, f"took {seconds:.1f}s"
    assert len(d.lines) > 200 and d.solver_status in ("optimal", "feasible")


def test_the_large_plan_is_still_consistent(draft):
    d, _ = draft
    assert d.optimized_total <= d.greedy_total or any(g.minimum_status == "shortfall" for g in d.groups)
    by_supplier = {}
    for ln in d.lines:
        assert ln.qty > 0 and ln.line_total == ln.unit_cost * ln.qty
        by_supplier[ln.supplier_id] = by_supplier.get(ln.supplier_id, D(0)) + ln.line_total
    for g in d.groups:
        assert g.subtotal == by_supplier[g.supplier_id] and g.total == g.subtotal + g.delivery_charge


def test_the_large_plan_is_deterministic(draft):
    d, _ = draft
    again = generate(catalogue(), time_limit_s=30)
    assert (again.lines == d.lines and again.inputs_hash == d.inputs_hash and again.solver_status == d.solver_status) or d.solver_status == "feasible"
