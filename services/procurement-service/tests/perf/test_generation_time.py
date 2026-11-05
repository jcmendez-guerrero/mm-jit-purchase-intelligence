"""T144: Performance test: proposal generation completes within target (< 2 minutes)."""

import time
from decimal import Decimal

from allocation.common import build_lines
from allocation.cpsat import allocate_cpsat
from builders import flat_forecast, inputs, offer, terms, variant


def test_proposal_generation_within_time_budget():
    # Build a simulated catalogue of 100 variants across 5 suppliers
    suppliers = ["SUPP-A", "SUPP-B", "SUPP-C", "SUPP-D", "SUPP-E"]
    supp_terms = [
        terms(
            s,
            min_value="150.00",
            free="300.00",
            charge="15.00",
        )
        for s in suppliers
    ]

    var_list = []
    for i in range(1, 101):
        # 2 supplier offers per variant
        s1 = suppliers[i % len(suppliers)]
        s2 = suppliers[(i + 1) % len(suppliers)]
        price1 = Decimal(f"{5 + (i % 20)}.50")
        price2 = price1 + Decimal("0.80")
        var_list.append(
            variant(
                i,
                [offer(s1, str(price1), pack=6, moq=12), offer(s2, str(price2), pack=1, moq=1)],
                on_hand=5,
                forecast=flat_forecast(10),
            )
        )

    inp = inputs(var_list, supp_terms)

    start = time.monotonic()
    lines = build_lines(inp)
    alloc = allocate_cpsat(inp, lines, time_limit_s=30)
    elapsed = time.monotonic() - start

    assert alloc is not None
    assert len(alloc.chosen) > 0
    # Must complete well under 120 seconds target
    assert elapsed < 120.0, f"Generation took {elapsed:.2f}s, exceeding 120s target"
