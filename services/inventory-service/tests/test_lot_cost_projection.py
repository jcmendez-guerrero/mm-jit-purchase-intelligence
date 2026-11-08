"""T127: the lot-cost projection from procurement.lot_cost.changed.v1."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from db.tables import lot_cost_projection
from mmi_common.dispatch import RejectMessageError
from projections.lot_costs import apply_lot_cost
from sqlalchemy import select

T = datetime(2026, 11, 9, 8, tzinfo=UTC)
DOC = {"variant_id": 1, "supplier_id": "s1", "lot": "L1", "unit_cost": "2.5000", "source": "confirmed_order"}


def row(engine):
    with engine.connect() as c:
        return c.execute(select(lot_cost_projection)).all()


def test_the_cost_is_stored_exactly_and_a_correction_replaces_it(engine):
    with engine.begin() as c:
        apply_lot_cost(c, DOC, T)
        apply_lot_cost(c, {**DOC, "unit_cost": "3.1000", "source": "receipt_correction"}, T + timedelta(minutes=1))
    r = row(engine)
    assert len(r) == 1 and Decimal(str(r[0].unit_cost)) == Decimal("3.1") and r[0].source == "receipt_correction"


def test_an_older_event_never_overwrites_a_newer_one(engine):
    with engine.begin() as c:
        apply_lot_cost(c, {**DOC, "unit_cost": "3.1000"}, T + timedelta(minutes=5))
        apply_lot_cost(c, DOC, T)
    assert Decimal(str(row(engine)[0].unit_cost)) == Decimal("3.1")


def test_redelivery_is_idempotent_and_two_suppliers_keep_two_rows(engine):
    with engine.begin() as c:
        apply_lot_cost(c, DOC, T)
        apply_lot_cost(c, DOC, T)
        apply_lot_cost(c, {**DOC, "supplier_id": "s2", "unit_cost": "4.0000"}, T)
    assert len(row(engine)) == 2


@pytest.mark.parametrize("bad", [{"unit_cost": "-1"}, {"unit_cost": "abc"}, {"unit_cost": "NaN"}, {"source": "erp_movement"}, {"lot": ""}, {"variant_id": "x"}])
def test_malformed_events_are_rejected_not_stored(engine, bad):
    with pytest.raises(RejectMessageError), engine.begin() as c:
        apply_lot_cost(c, {**DOC, **bad}, T)
    assert row(engine) == []


def test_a_missing_field_is_rejected(engine):
    with pytest.raises(RejectMessageError), engine.begin() as c:
        apply_lot_cost(c, {"variant_id": 1}, T)


def test_the_consumer_handles_the_event_type():
    from projections.consumer import LOT_COST, InventoryConsumer

    assert LOT_COST == "procurement.lot_cost.changed.v1" and LOT_COST in InventoryConsumer().handlers()
