"""US2 independent test over the synthetic dataset: demand equals shipments minus returns, other reasons stay in
their own series, and stockout days are censored."""

from collections import defaultdict
from datetime import timedelta

from db.tables import (
    ALL_WAREHOUSES,
    demand_observations,
    flow_series,
    stock_history,
    stock_movements,
    stock_snapshots,
)
from demand.rebuild import rebuild
from generator import generate
from projections.apply import apply_payload
from sqlalchemy import func, insert, select


def load(engine):
    data = generate()
    last_day = max(m["created_at"][:10] for m in data.movements)
    from datetime import date

    snap_day = date.fromisoformat(last_day) + timedelta(days=1)
    quarantined = {m: "x" for m in data.truth["unreferenced_sale_ids"]}
    with engine.begin() as c:
        apply_payload(c, {"kind": "movements", "records": data.movements, "quarantined": {str(k): [v] for k, v in quarantined.items()}}, snap_day)
        final: dict[int, int] = defaultdict(int)
        for (vid, _wh), qty in data.truth["final_stock"].items():
            final[vid] += qty
        c.execute(insert(stock_snapshots), [{"variant_id": v, "warehouse_id": ALL_WAREHOUSES, "snapshot_date": snap_day, "on_hand": q, "available": q, "reserved": 0}
                                           for v, q in final.items()])
        rebuild(c)
    return data


def test_demand_flows_and_history_over_the_synthetic_dataset(engine):
    data = load(engine)
    q = set(data.truth["unreferenced_sale_ids"])
    with engine.connect() as c:
        got = c.execute(select(func.sum(demand_observations.c.demand_qty))).scalar_one()
        expect = -sum(m["quantity"] for m in data.movements if m["reason"] in ("sale_shipment", "return_customer") and m["id"] not in q)
        assert got == expect                                        # quarantined sales excluded, nothing else dropped
        flows = {r for r in c.execute(select(flow_series.c.flow).distinct()).scalars()}
        assert "supplier_receipt" in flows and "loss_unclassified" in flows and "loss_unspecified" in flows
        assert not flows & {"sale_shipment", "return_customer"}      # demand never appears as a flow
        total = c.execute(select(func.count()).select_from(stock_history)).scalar_one()
        bad = c.execute(select(func.count(func.distinct(stock_history.c.variant_id))).where(stock_history.c.reconciled_ok.is_(False))).scalar_one()
        assert total > 10_000 and bad == 0                          # a complete history reconciles with the final snapshot
        assert c.execute(select(func.count()).select_from(stock_history).where(stock_history.c.censored)).scalar_one() > 0
        # every censored demand observation sits on a censored history day
        cens = c.execute(select(demand_observations.c.variant_id, demand_observations.c.day).where(demand_observations.c.censored)).all()
        hist = {(r.variant_id, r.day) for r in c.execute(select(stock_history.c.variant_id, stock_history.c.day).where(stock_history.c.censored)).all()}
        assert all(tuple(x) in hist for x in cens)
        assert c.execute(select(func.count()).select_from(stock_movements)).scalar_one() == len(data.movements)
