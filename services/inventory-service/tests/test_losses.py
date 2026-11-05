"""T048: loss classification before/after the cutover date and reclassification when the cutover changes."""

from datetime import UTC, date, datetime

from db.tables import flow_series, stock_movements
from demand.common import DEFAULT_CUTOVER, Mov
from demand.losses import classify, flows_from_movements
from demand.rebuild import rebuild, set_cutover
from sqlalchemy import insert, select

BEFORE, ON, AFTER = date(2026, 9, 18), date(2026, 9, 19), date(2026, 9, 20)


def test_default_cutover_is_19_september_2026():
    assert DEFAULT_CUTOVER == date(2026, 9, 19)


def test_before_cutover_every_negative_adjustment_is_unclassified_and_reasons_are_not_trusted():
    assert classify("adjustment_negative", BEFORE) == "loss_unclassified"
    for r in ("expiry", "damage", "theft"):
        assert classify(r, BEFORE) == "loss_unclassified"


def test_after_cutover_structured_reasons_are_trusted_and_reasonless_is_unspecified():
    assert classify("adjustment_negative", AFTER) == "loss_unspecified"
    assert [classify(r, AFTER) for r in ("expiry", "damage", "theft")] == ["expiry", "damage", "theft"]


def test_the_cutover_day_itself_counts_as_after():
    assert classify("adjustment_negative", ON) == "loss_unspecified"


def test_losses_are_never_demand_and_other_reasons_have_their_own_flow():
    assert classify("sale_shipment", AFTER) is None and classify("return_customer", AFTER) is None
    assert classify("transfer_out", AFTER) == "transfer" and classify("count_adjustment", AFTER) == "count"
    assert classify("purchase_receipt", AFTER) == "supplier_receipt" and classify("initial_stock", AFTER) == "initial_stock"


def test_flows_sum_signed_quantities_and_skip_quarantined():
    ms = [Mov(1, 1, 1, AFTER, "damage", -2, False), Mov(2, 1, 1, AFTER, "damage", -3, False), Mov(3, 1, 1, AFTER, "theft", -9, True)]
    assert [(f.flow, f.qty) for f in flows_from_movements(ms)] == [("damage", -5)]


def seed(engine, rows):
    with engine.begin() as c:
        for i, (reason, ts, qty) in enumerate(rows, start=1):
            c.execute(insert(stock_movements).values(external_id=i, created_at_utc=ts, created_at_raw=ts.isoformat(), variant_id=1,
                                                     warehouse_id=1, quantity=qty, reason=reason, has_note=False, quarantined=False))


def flows(engine):
    with engine.connect() as c:
        return sorted((r.day.isoformat(), r.flow) for r in c.execute(select(flow_series)).all())


def test_changing_the_cutover_reclassifies_history_and_is_audited(engine):
    seed(engine, [("adjustment_negative", datetime(2026, 9, 10, 10, tzinfo=UTC), -1), ("adjustment_negative", datetime(2026, 9, 25, 10, tzinfo=UTC), -1)])
    with engine.begin() as c:
        rebuild(c, through_day=date(2026, 10, 1))
    assert flows(engine) == [("2026-09-10", "loss_unclassified"), ("2026-09-25", "loss_unspecified")]
    with engine.begin() as c:
        set_cutover(c, date(2026, 10, 15), "admin-1")
        rebuild(c, through_day=date(2026, 10, 1))
    assert flows(engine) == [("2026-09-10", "loss_unclassified"), ("2026-09-25", "loss_unclassified")]
    with engine.begin() as c:
        set_cutover(c, date(2026, 9, 1), "admin-1")
        rebuild(c, through_day=date(2026, 10, 1))
    assert flows(engine) == [("2026-09-10", "loss_unspecified"), ("2026-09-25", "loss_unspecified")]
    from db.tables import config_loss_cutover

    with engine.connect() as c:
        assert [r.changed_by for r in c.execute(select(config_loss_cutover)).all()] == ["admin-1", "admin-1"]
