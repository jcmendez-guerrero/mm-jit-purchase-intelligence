"""T147 / T151: the inputs provider, the user directory and the production wiring."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from approvals.workflow import ApprovalError, submit
from conftest import NOW, add_product, add_supplier
from costs.rules import CostRules
from costs.store import NewCost, add_version
from db.tables import product_refs, user_roles
from proposals.generate import generate
from proposals.inputs import HttpJsonSource, InputsProvider, InputsUnavailableError, refresh_product_refs, to_forecast
from sqlalchemy import select, update
from terms.service import Terms, save_terms
from users.directory import ConnUserDirectory, DbUserDirectory, DirectoryError, set_roles

D = Decimal
TODAY = date(2026, 11, 9)


class Src:
    def __init__(self, doc):
        self.doc = doc

    def fetch(self):
        if isinstance(self.doc, Exception):
            raise self.doc
        return self.doc


def horizons(rate=1.0, k=2.0):
    import math

    return {str(h): {"mean": rate * h, "quantiles": {lv: math.ceil(rate * h + k * math.sqrt(rate * h)) for lv in ("0.85", "0.90", "0.95", "0.97", "0.99")}} for h in (7, 14, 21, 28, 42)}


def stock(*variants):
    return {"snapshot_date": "2026-11-09", "count": len(variants), "variants": list(variants)}


def sv(vid, pid, on_hand=0, lots=(), level="0.95", critical=False, sku=None):
    return {"variant_id": vid, "product_id": pid, "sku": sku or f"SYN-{vid}", "name": f"Producto {vid}", "pack_size": 1, "on_hand": on_hand, "available": on_hand,
            "lots": list(lots), "segment": {"abc": "B", "pattern": "smooth", "forecast_eligible": True}, "clinical_critical": critical, "service_level": level}


def fc(**by_variant):
    return {"run_id": "run-1", "variants": {k[1:]: v for k, v in by_variant.items()}}


ELIGIBLE = {"eligible": True, "policy": "minmax_poisson", "reasons": [], "service_level": "0.95", "horizons": horizons()}
FALLBACK = {"eligible": False, "policy": "minmax_conservative", "reasons": ["new"], "service_level": "0.95",
            "horizons": {str(h): {"mean": None, "quantiles": {"min": 3, "max": 9}} for h in (7, 14, 21, 28, 42)}}


def cost(conn, sid, pid, value="1.00", **kw):
    return add_version(conn, NewCost(product_id=pid, supplier_id=sid, cost_with_recargo=D(value), source="siweb_product_supplier", actor="siweb-import", **kw), CostRules(), NOW)


def test_inputs_combine_stock_forecast_costs_terms_and_inbound(conn):
    sa, sb = add_supplier(conn, 1, "A"), add_supplier(conn, 2, "B")
    cost(conn, sa, 10, "1.00", lead_time_days=3, pack_size=6, min_order_qty=12)
    cost(conn, sb, 10, "1.20")
    save_terms(conn, sa, Terms(min_order_value=D("50"), order_days=(1,)), "buyer-1", NOW)
    soon = (TODAY + timedelta(days=5)).isoformat()
    later = (TODAY + timedelta(days=60)).isoformat()
    inp = InputsProvider(Src(stock(sv(1, 10, on_hand=4, lots=[{"expiry_date": soon, "quantity": 3}, {"expiry_date": later, "quantity": 9}], critical=True)),
                         ), Src(fc(v1=ELIGIBLE)), budget=D("500")).build(conn, TODAY)
    v = inp.variants[0]
    assert (v.variant_id, v.product_id, v.on_hand, v.expiring_qty, v.clinical_critical, v.service_level) == (1, 10, 4, 3, True, D("0.95"))
    assert {o.supplier_id: (o.unit_cost, o.lead_time_days, o.pack_size, o.min_order_qty) for o in v.offers} == {sa: (D("1.0000"), 3, 6, 12), sb: (D("1.2000"), 7, 1, 0)}
    assert v.forecast.eligible and v.forecast.horizons[14].mean == 14.0 and v.soon_need == 7 and inp.budget == D("500")
    assert inp.suppliers[sa].min_order_value == D("50.0000") and inp.suppliers[sb].min_order_value is None
    draft = generate(inp, 10)                                                                          # the assembled inputs drive the real engine
    assert draft.lines and draft.lines[0].explanation["position"]["expiring"] == 3


def test_ineligible_forecasts_pass_through_as_the_conservative_min_max(conn):
    sa = add_supplier(conn)
    cost(conn, sa, 10)
    v = InputsProvider(Src(stock(sv(1, 10))), Src(fc(v1=FALLBACK))).build(conn, TODAY).variants[0]
    assert not v.forecast.eligible and v.forecast.reasons == ("new",) and v.forecast.horizons[7].quantiles == {"min": 3, "max": 9} and v.soon_need == 0


def test_confirmed_inbound_orders_count_with_their_remaining_quantity(conn):
    from approvals.workflow import decide
    from mmi_common.auth import Principal
    from orders.confirm import ConfirmLine, confirm_order
    from proposals.generate import store

    sa = add_supplier(conn)
    cost(conn, sa, 10)
    pid = store(conn, generate(InputsProvider(Src(stock(sv(1, 10))), Src(fc(v1=ELIGIBLE))).build(conn, TODAY) and
                               InputsProvider(Src(stock(sv(1, 10))), Src(fc(v1=ELIGIBLE))).build(conn, TODAY), 10), "buyer-1", "2026-W46", None, NOW)

    class Users:
        def active_approvers(self):
            return {"approver-2"}

    submit(conn, pid, "buyer-1", 1, Users(), NOW)
    decide(conn, pid, Principal("approver-2", frozenset({"approver"}), NOW - timedelta(minutes=1)), 1, now=NOW)

    class W:
        def put(self, n, d):
            return "file:///dev/null"

    confirm_order(conn, pid, sa, [ConfirmLine(1, 10, D("1.00"))], "buyer-1", W(), NOW, expected_delivery=TODAY + timedelta(days=2))
    v = InputsProvider(Src(stock(sv(1, 10))), Src(fc(v1=ELIGIBLE))).build(conn, TODAY).variants[0]
    assert v.inbound == ((10, 2),)


def test_blocked_costs_are_offered_as_blocked_and_stale_ones_as_stale(conn):
    sa, sb = add_supplier(conn, 1, "A"), add_supplier(conn, 2, "B")
    cost(conn, sa, 10, "1.00")
    add_version(conn, NewCost(product_id=10, supplier_id=sa, cost_with_recargo=D("9.00"), source="manual", actor="x"), CostRules(), NOW)       # unconfirmed jump
    cost(conn, sb, 10, "1.10")
    old = NOW - timedelta(days=90)
    from db.tables import supplier_costs

    conn.execute(update(supplier_costs).where(supplier_costs.c.supplier_id == sb).values(verified_at=old))
    v = InputsProvider(Src(stock(sv(1, 10))), Src(fc(v1=ELIGIBLE))).build(conn, TODAY).variants[0]
    assert {o.supplier_id: o.cost_status for o in v.offers} == {sa: "blocked_jump", sb: "stale"}
    draft = generate(InputsProvider(Src(stock(sv(1, 10))), Src(fc(v1=ELIGIBLE))).build(conn, TODAY), 10)
    assert draft.lines[0].supplier_id == sb and draft.lines[0].confidence == "medium"                          # stale cost lowers confidence; the blocked one is rejected


def test_variants_without_a_cost_or_a_forecast_are_reported_not_guessed(conn):
    sa = add_supplier(conn)
    cost(conn, sa, 10)
    p = InputsProvider(Src(stock(sv(1, 10), sv(2, 20), sv(3, 10))), Src(fc(v1=ELIGIBLE, v2=ELIGIBLE)))
    inp = p.build(conn, TODAY)
    assert [v.variant_id for v in inp.variants] == [1] and p.report.without_cost == [2] and p.report.without_forecast == [3]


def test_a_variant_override_cost_applies_only_to_its_variant(conn):
    sa = add_supplier(conn)
    cost(conn, sa, 10, "1.00")
    add_version(conn, NewCost(product_id=10, supplier_id=sa, cost_with_recargo=D("1.10"), source="csv_price_list", actor="x", variant_id=1, pack_size=12), CostRules(), NOW)
    inp = InputsProvider(Src(stock(sv(1, 10), sv(2, 10))), Src(fc(v1=ELIGIBLE, v2=ELIGIBLE))).build(conn, TODAY)
    by = {v.variant_id: v.offers[0] for v in inp.variants}
    assert (by[1].unit_cost, by[1].pack_size) == (D("1.1000"), 12) and by[2].unit_cost == D("1.0000")


def test_missing_upstream_data_is_a_clear_error(conn):
    with pytest.raises(InputsUnavailableError) as e:
        InputsProvider(Src(stock()), Src(fc())).build(conn, TODAY)
    assert e.value.code == "no_stock_snapshot"
    with pytest.raises(InputsUnavailableError):
        HttpJsonSource("http://x", "t", type("C", (), {"get": lambda s, u, headers=None: type("R", (), {"status_code": 404})()})()).fetch()


def test_product_refs_are_refreshed_without_touching_the_buyers_vat(conn):
    add_product(conn, 1, 10, vat=D("21"))
    refresh_product_refs(conn, [{"variant_id": 1, "product_id": 10, "sku": "NEW-SKU", "name": "Nuevo"}, {"variant_id": 2, "product_id": 10, "sku": "S2", "name": "Dos"},
                                {"variant_id": 3, "product_id": None}])
    rows = {r.variant_id: r for r in conn.execute(select(product_refs)).all()}
    assert set(rows) == {1, 2} and rows[1].sku == "NEW-SKU" and D(str(rows[1].vat_rate)) == D("21.00") and rows[2].vat_rate is None


def test_forecast_entries_convert_to_engine_types():
    f = to_forecast(ELIGIBLE)
    assert f.eligible and f.horizons[7].quantiles["0.95"] >= 7 and f.policy == "minmax_poisson"


# ---- user directory ----------------------------------------------------------------------------------------

def test_directory_lists_only_active_approvers_and_audits_changes(conn, engine):
    set_roles(conn, "u1", ["viewer", "approver"], "bff", now=NOW)
    set_roles(conn, "u2", ["viewer", "buyer"], "bff", now=NOW)
    set_roles(conn, "u3", ["approver"], "bff", active=False, now=NOW)
    set_roles(conn, "u2", ["buyer", "approver"], "bff", now=NOW)
    assert {r.user_id for r in conn.execute(select(user_roles)).all()} == {"u1", "u2", "u3"}
    from audit.chain import verify_chain

    assert verify_chain(conn).ok
    with pytest.raises(DirectoryError):
        set_roles(conn, "u4", ["superuser"], "bff")


def test_submit_uses_the_directory_so_one_approver_who_is_the_creator_cannot_submit(engine):
    from proposals.generate import store

    with engine.begin() as c:
        sa = add_supplier(c)
        cost(c, sa, 10)
        pid = store(c, generate(InputsProvider(Src(stock(sv(1, 10))), Src(fc(v1=ELIGIBLE))).build(c, TODAY), 10), "buyer-1", "2026-W46", None, NOW)
        set_roles(c, "buyer-1", ["buyer", "approver"], "bff", now=NOW)
    users = DbUserDirectory(engine)
    assert users.active_approvers() == {"buyer-1"}
    with engine.begin() as c, pytest.raises(ApprovalError) as e:
        submit(c, pid, "buyer-1", 1, ConnUserDirectory(c), NOW)
    assert e.value.code == "no_eligible_approver"
    with engine.begin() as c:
        set_roles(c, "approver-2", ["approver"], "bff", now=NOW)
    with engine.begin() as c:
        submit(c, pid, "buyer-1", 1, users.bind(c), NOW)


def test_the_production_app_wires_its_dependencies_only_when_configured(monkeypatch, tmp_path, engine):
    import importlib

    import api.costs as costs_api
    import main

    monkeypatch.delenv("MMI_DATABASE_URL", raising=False)
    importlib.reload(main)
    main.configure()
    assert getattr(main.app.state, "user_directory", None) is None and getattr(main.app.state, "inputs_provider", None) is None
    monkeypatch.setenv("MMI_DATABASE_URL", "sqlite://")
    monkeypatch.setenv("MMI_BLOB_ROOT", str(tmp_path))
    monkeypatch.setenv("MMI_INVENTORY_URL", "http://inv.test")
    monkeypatch.setenv("MMI_FORECAST_URL", "http://fc.test")
    monkeypatch.setenv("MMI_WEEKLY_BUDGET", "1234.50")
    monkeypatch.setattr(costs_api, "get_engine", lambda: engine)
    importlib.reload(main)
    main.configure()
    assert main.app.state.inputs_provider.budget == D("1234.50") and main.app.state.user_directory is not None
    assert "token" not in repr(main.app.state.inputs_provider.stock).lower() or "***" in repr(main.app.state.inputs_provider.stock)
