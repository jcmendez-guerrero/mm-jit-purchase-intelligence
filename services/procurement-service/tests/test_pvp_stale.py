"""T163: a selling price last confirmed by a sync more than 7 days ago is treated like a missing price (FR-043, clarified 2026-11-07)."""

from decimal import Decimal

import pytest
from builders import FakeLots
from conftest import NOW, add_product, add_supplier
from costs.lot_costs import record_lot_cost
from costs.median_suggestion import request_median_write
from costs.pvp import PvpQuote, lowest_pvp_info
from costs.writes import WriteError, approve_write, set_override
from db.tables import erp_supplier_links
from sqlalchemy import insert
from test_margin_override import Blob, who

D = Decimal


class Quotes:
    """A price source that reports age, like the inventory service."""

    def __init__(self, **quotes):
        self.q = {int(k[1:]): v for k, v in quotes.items()}

    def quotes(self, ids):
        return {i: v for i, v in self.q.items() if i in ids}

    def prices(self, ids):
        return {i: v.price for i, v in self.quotes(ids).items() if not v.stale}


def fresh(price, days=2):
    return PvpQuote(D(price), age_days=days, stale=False)


def stale(price, days=9):
    return PvpQuote(D(price), age_days=days, stale=True)


def test_the_lowest_fresh_price_wins_and_carries_its_age():
    info = lowest_pvp_info(Quotes(v1=fresh("12.00", 3), v2=fresh("10.00", 5), v3=stale("8.00", 20)), [1, 2, 3])
    assert (info.price, info.age_days, info.stale_only) == (D("10.00"), 5, False)


def test_only_stale_prices_mean_no_price_and_say_why():
    info = lowest_pvp_info(Quotes(v1=stale("10.00", 9), v2=stale("11.00", 30)), [1, 2])
    assert info.price is None and info.stale_only is True and info.age_days == 9


def test_no_prices_at_all_is_not_reported_as_stale():
    info = lowest_pvp_info(Quotes(), [1])
    assert info.price is None and info.stale_only is False


def test_a_source_that_does_not_report_age_keeps_the_old_behaviour():
    class Plain:
        def prices(self, ids):
            return {1: D("10.00")}

    info = lowest_pvp_info(Plain(), [1])
    assert info.price == D("10.00") and info.age_days is None and info.stale_only is False


@pytest.fixture
def request_with(conn, tmp_path):
    def make(source):
        sid = add_supplier(conn)
        add_product(conn, 1, 10, vat=D("21"))
        conn.execute(insert(erp_supplier_links).values(product_id=10, supplier_id=sid, has_cost=False, last_seen_at=NOW))
        record_lot_cost(conn, Blob(tmp_path), variant_id=1, supplier_id=sid, lot="L1", unit_cost=D("9.00"), source="confirmed_order", actor="system", quantity=3, now=NOW)
        return request_median_write(conn, FakeLots([{"variant_id": 1, "lot": "L1", "quantity": 3}]), 10, sid, "receipt_matched", "system", NOW, source).request

    return make


def test_a_stale_price_blocks_the_release_like_a_missing_one_but_an_admin_can_override(conn, request_with, tmp_path):
    req = request_with(Quotes(v1=stale("10.00", 9)))
    assert req.pvp_used is None and "margin_unavailable" in req.rule_flags and "pvp_stale" in req.rule_flags and req.pvp_age_days == 9
    with pytest.raises(WriteError) as e:
        approve_write(conn, req.id, who("buyer-1", {"buyer"}), Blob(tmp_path), now=NOW)
    assert e.value.code == "margin_unavailable"
    set_override(conn, req.id, who("admin-1", {"admin"}), D("9.00"), "precio confirmado por teléfono", NOW)


def test_a_fresh_price_is_used_and_its_age_is_recorded(conn, request_with):
    req = request_with(Quotes(v1=fresh("20.00", 4)))
    assert D(str(req.pvp_used)) == D("20.00") and req.pvp_age_days == 4 and "pvp_stale" not in req.rule_flags
