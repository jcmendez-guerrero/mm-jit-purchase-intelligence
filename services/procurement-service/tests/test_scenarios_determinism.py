"""T013 (FR-006, SC-001): the same scenario on the same inputs gives one result 20 times."""

from decimal import Decimal

from conftest import NOW
from scen import Blob, base, suppliers
from scenarios import store as sc
from scenarios.engine import ScenarioParams, SupplierDelta

D = Decimal


def test_twenty_runs_give_one_result_hash_and_one_set_of_results(conn, tmp_path):
    sa, sb = suppliers(conn)
    params = ScenarioParams(supplier_deltas={sa: SupplierDelta(min_order_value=D("100"))})
    runs = [sc.create(conn, Blob(tmp_path), f"Run {i}", params, base(sa, sb), "buyer-1", f"k-det-{i:05d}", NOW) for i in range(20)]
    assert len({r["result_hash"] for r in runs}) == 1
    assert len({str([(x["supplier_id"], x["lines"], x["order_total"]) for x in r["results"]]) for r in runs}) == 1
