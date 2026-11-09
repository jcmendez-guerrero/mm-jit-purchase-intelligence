"""T037 (FR-035, SC-012): a cost quoted in another currency is converted with the stored ECB rate for the proposal date. Without a usable rate
(none, not published by the ECB, or older than 7 days) the supplier is left out of automatic allocation and one review item says why: never
converted silently, never compared as if it were euros.
"""

from __future__ import annotations

import socket
from datetime import date
from decimal import Decimal

import httpx
import pytest
from conftest import NOW, add_product, add_supplier
from costs.rules import CostRules
from costs.store import NewCost, add_version
from db.tables import supplier_review_items
from fx.rates import refresh_if_due
from proposals.generate import generate
from proposals.inputs import InputsProvider
from sqlalchemy import select
from test_fx_rates import Source, text
from test_inputs import ELIGIBLE, TODAY, Src, fc, stock, sv

D = Decimal
PUBLISHED = date(2026, 11, 6)                         # the fixture's publication day; USD is 1.25 per euro, so 0.8 EUR per dollar


def world(conn, usd_cost="1.10", currency="USD", eur_cost="1.00", rates=True):
    sa, sb = add_supplier(conn, 1, "A"), add_supplier(conn, 2, "B")
    add_product(conn, 1, 10)
    add_version(conn, NewCost(product_id=10, supplier_id=sa, cost_with_recargo=D(usd_cost), source="manual", actor="x", pack_size=1, lead_time_days=3,
                              currency=currency), CostRules(), NOW)
    add_version(conn, NewCost(product_id=10, supplier_id=sb, cost_with_recargo=D(eur_cost), source="manual", actor="x", pack_size=1, lead_time_days=3), CostRules(), NOW)
    if rates:
        refresh_if_due(conn, Source(text()), NOW)
    return sa, sb


def build(conn, today=TODAY):
    provider = InputsProvider(Src(stock(sv(1, 10))), Src(fc(v1=ELIGIBLE)))
    built = provider.build(conn, today)
    return built, provider.report


def review_items(conn):
    return [(r.kind, r.supplier_id, r.detail) for r in conn.execute(select(supplier_review_items).where(supplier_review_items.c.kind.like("fx_rate_%"))).all()]


def test_a_fresh_rate_converts_the_cost_and_the_cheaper_converted_supplier_wins(conn):
    sa, _ = world(conn, usd_cost="1.10")
    built, _ = build(conn)
    offer = next(o for o in built.variants[0].offers if o.supplier_id == sa)
    assert offer.unit_cost == D("0.8800")                                          # 1.10 USD x 0.8
    assert generate(built, 5).lines[0].supplier_id == sa


def test_the_line_names_the_rate_the_currency_and_the_day_it_was_published(conn):
    world(conn, usd_cost="1.10")
    built, _ = build(conn)
    fx = generate(built, 5).lines[0].explanation["terms"]["fx"]
    assert fx == {"currency": "USD", "original_cost": "1.1000", "eur_per_unit": "0.8", "published_on": "2026-11-06"}


def test_a_dearer_converted_cost_loses_to_the_euro_supplier(conn):
    _, sb = world(conn, usd_cost="1.40")                                           # 1.12 EUR against 1.00
    assert generate(build(conn)[0], 5).lines[0].supplier_id == sb


@pytest.mark.parametrize(("rates", "currency", "code"), [(False, "USD", "fx_rate_missing"), (True, "XYZ", "fx_rate_missing")])
def test_no_usable_rate_leaves_the_supplier_out_and_raises_one_review_item(conn, rates, currency, code):
    sa, sb = world(conn, currency=currency, rates=rates)
    built, report = build(conn)
    assert {o.supplier_id for o in built.variants[0].offers} == {sb}
    assert report.fx_excluded == [(1, sa, code)]
    assert review_items(conn) == [(code, sa, currency)]
    build(conn)                                                                    # a second build must not pile up duplicates
    assert len(review_items(conn)) == 1


def test_a_rate_is_usable_for_seven_days_and_stale_on_the_eighth(conn):
    sa, sb = world(conn)
    seventh, _ = build(conn, date(2026, 11, 13))
    assert sa in {o.supplier_id for o in seventh.variants[0].offers}
    eighth, report = build(conn, date(2026, 11, 14))
    assert {o.supplier_id for o in eighth.variants[0].offers} == {sb} and report.fx_excluded == [(1, sa, "fx_rate_stale")]
    assert review_items(conn) == [("fx_rate_stale", sa, "USD")]


def test_when_every_offer_is_excluded_the_product_is_reported_without_a_cost_not_dropped_silently(conn):
    sa = add_supplier(conn, 1, "A")
    add_product(conn, 1, 10)
    add_version(conn, NewCost(product_id=10, supplier_id=sa, cost_with_recargo=D("1.10"), source="manual", actor="x", pack_size=1, currency="USD"), CostRules(), NOW)
    built, report = build(conn)
    assert report.without_cost == [1] and report.fx_excluded == [(1, sa, "fx_rate_missing")] and generate(built, 5).lines == ()


def test_euro_suppliers_need_no_rate_at_all(conn):
    sa, sb = world(conn, currency="EUR", usd_cost="1.50", rates=False)
    built, report = build(conn)
    assert {o.supplier_id for o in built.variants[0].offers} == {sa, sb} and report.fx_excluded == [] and review_items(conn) == []


def test_conversion_rounds_to_four_decimals(conn):
    sa, _ = world(conn, usd_cost="1.2346")
    offer = next(o for o in build(conn)[0].variants[0].offers if o.supplier_id == sa)
    assert offer.unit_cost == D("0.9877")                                          # 0.98768 rounds half up


def test_building_a_proposal_never_calls_the_rate_service(conn, monkeypatch):
    world(conn)

    def tripwire(*a, **k):
        raise AssertionError("proposal generation must read stored rates only")

    monkeypatch.setattr(httpx.Client, "send", tripwire)
    monkeypatch.setattr(httpx.AsyncClient, "send", tripwire)
    monkeypatch.setattr(socket, "create_connection", tripwire)
    assert generate(build(conn)[0], 5).lines


def test_the_converted_cost_and_the_rate_are_part_of_the_inputs_hash(conn):
    from db.tables import fx_rates
    from proposals.generate import RULE_VERSIONS
    from proposals.model import inputs_hash
    from sqlalchemy import update

    world(conn)
    first = inputs_hash(build(conn)[0], RULE_VERSIONS)
    conn.execute(update(fx_rates).where(fx_rates.c.currency == "USD").values(eur_per_unit=D("1.0")))      # a different rate is a different input
    assert inputs_hash(build(conn)[0], RULE_VERSIONS) != first


# ---- the supplier's product list shows the euro equivalent, the rate and its day (FR-035) ----
def _listed(conn, today, currency="USD", rates=True):
    from suppliers.links import list_links
    from suppliers.service import SupplierInput, create_supplier
    from suppliers_support import make_ref

    make_ref(conn, 1, 10, "SYN-000001")
    sid = create_supplier(conn, SupplierInput(name="Proveedor Sintetico USD", fiscal_type="foreign", country="US", currency=currency), "buyer-1", now=NOW).id
    add_version(conn, NewCost(product_id=10, supplier_id=sid, cost_with_recargo=D("1.10"), source="siweb_product_supplier", actor="siweb-import", currency=currency), CostRules(), NOW)
    if rates:
        refresh_if_due(conn, Source(text()), NOW)
    (row,) = list_links(conn, sid, today)
    return row


def test_a_foreign_cost_is_listed_with_its_euro_equivalent_the_rate_and_the_day(conn):
    row = _listed(conn, TODAY)
    assert (row["currency"], row["cost"], row["fx_state"]) == ("USD", "1.1000", "ok")
    assert (row["eur_equivalent"], row["fx_rate"], row["fx_date"]) == ("0.8800", "0.8", "2026-11-06")


def test_a_foreign_cost_with_no_rate_or_an_old_one_says_so_and_has_no_equivalent(conn):
    missing = _listed(conn, TODAY, rates=False)
    assert (missing["fx_state"], missing["eur_equivalent"], missing["fx_rate"], missing["fx_date"]) == ("missing", None, None, None)


def test_an_old_rate_is_reported_as_stale_with_its_day(conn):
    row = _listed(conn, date(2026, 11, 14))
    assert row["fx_state"] == "stale" and row["eur_equivalent"] is None and row["fx_date"] == "2026-11-06"


def test_a_euro_cost_has_no_fx_fields_set(conn):
    row = _listed(conn, TODAY, currency="EUR", rates=False)
    assert (row["fx_state"], row["eur_equivalent"], row["fx_rate"], row["fx_date"]) == (None, None, None, None)
