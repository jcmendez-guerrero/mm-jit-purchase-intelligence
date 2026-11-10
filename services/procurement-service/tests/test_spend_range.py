"""T022 (procurement part, feature 006, research R15): the spend summary over a date range.

Budget = per ISO week whose Monday is in the range, the stricter of the weekly cap and the monthly cap / 4.33, added up; spend = the newest live proposal of each such week;
open orders = confirmed orders not yet received, at their confirmed cost. All synthetic.
"""

from datetime import date
from decimal import Decimal

from api import costs, summary
from conftest import NOW, add_supplier
from db.tables import inbound_order_lines, inbound_orders, proposals, supplier_order_groups
from fastapi.testclient import TestClient
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app
from policies.service import save_budget_cap
from sqlalchemy import insert

D = Decimal
H = {"Authorization": "Bearer viewer"}
RANGE = "date_from=2026-10-26&date_to=2026-11-09"            # Mondays: 26 Oct (W44), 2 Nov (W45), 9 Nov (W46)


class V:
    def validate(self, token, required_roles=()):
        if token != "viewer":  # noqa: S105 - test token name
            raise AuthError("forbidden", 403)
        return Principal("u", frozenset({"buyer"}), None)


def api(engine):
    app = create_service_app("procurement-service", validator=V())
    app.include_router(costs.build_router(app))
    app.include_router(summary.build_router(app))
    app.dependency_overrides[costs.get_engine] = lambda: engine
    return TestClient(app)


def proposal(conn, pid, week, supplier, total, status="draft", at=NOW):
    conn.execute(insert(proposals).values(id=pid, week=week, status=status, created_by="u", last_edited_by="u", version=1, inputs_hash=pid, rule_versions={}, solver_status="optimal",
                                          budget=None, flags={}, created_at=at, updated_at=at))
    conn.execute(insert(supplier_order_groups).values(proposal_id=pid, supplier_id=supplier, subtotal=total, delivery_charge=0, total_cost=total, minimum_status="met", shortfall_options=[]))


def order(conn, oid, pid, supplier, status, lines):
    conn.execute(insert(inbound_orders).values(id=oid, proposal_id=pid, supplier_id=supplier, status=status, confirmed_by="u", confirmed_at=NOW))
    for variant_id, qty, cost, received in lines:
        conn.execute(insert(inbound_order_lines).values(order_id=oid, variant_id=variant_id, qty=qty, confirmed_cost_with_recargo=cost, received_qty=received))


def caps(conn):
    save_budget_cap(conn, "week", "global", None, D("500"), "buyer-1", valid_from=date(2026, 10, 1), today=date(2026, 10, 1))
    save_budget_cap(conn, "month", "global", None, D("1000"), "buyer-1", valid_from=date(2026, 11, 1), today=date(2026, 11, 1))


def test_the_budget_over_three_weeks_applies_the_stricter_cap_each_week_and_adds_them(engine):
    with engine.begin() as c:
        caps(c)
    r = api(engine).get(f"/summary/spend?{RANGE}", headers=H).json()["range"]
    # 26 Oct: only the weekly cap exists = 500.00; 2 Nov and 9 Nov: the monthly 1000 / 4.33 = 230.95 is stricter
    assert [(w["week_start"], w["cap"]) for w in r["weeks"]] == [("2026-10-26", "500.00"), ("2026-11-02", "230.95"), ("2026-11-09", "230.95")]
    assert r["budget"] == "961.90" and r["date_from"] == "2026-10-26" and r["date_to"] == "2026-11-09"


def test_weeks_without_a_cap_add_nothing_and_no_cap_at_all_says_so(engine):
    assert api(engine).get(f"/summary/spend?{RANGE}", headers=H).json()["range"]["budget"] is None
    with engine.begin() as c:
        save_budget_cap(c, "week", "global", None, D("300"), "buyer-1", valid_from=date(2026, 11, 2), today=date(2026, 11, 2))
    r = api(engine).get(f"/summary/spend?{RANGE}", headers=H).json()["range"]
    assert r["budget"] == "600.00" and [w["cap"] for w in r["weeks"]] == [None, "300.00", "300.00"]


def test_proposed_spend_is_the_newest_live_proposal_of_each_week_in_the_range(engine):
    with engine.begin() as c:
        sa = add_supplier(c, 1)
        proposal(c, "p44", "2026-W44", sa, D("100.00"))
        proposal(c, "p45-old", "2026-W45", sa, D("999.00"), status="superseded")
        proposal(c, "p45", "2026-W45", sa, D("40.50"), status="approved")
        proposal(c, "p43", "2026-W43", sa, D("77.00"))              # Monday 19 Oct: outside the range
        proposal(c, "p47", "2026-W47", sa, D("88.00"))              # Monday 16 Nov: outside the range
    r = api(engine).get(f"/summary/spend?{RANGE}", headers=H).json()["range"]
    assert r["proposed"] == "140.50" and [w["proposed"] for w in r["weeks"]] == ["100.00", "40.50", "0.00"] and r["spend"] == "0.00"      # no order confirmed: nothing is spend


def test_the_supplier_filter_narrows_the_range_proposed_spend(engine):
    with engine.begin() as c:
        sa, sb = add_supplier(c, 1), add_supplier(c, 2)
        proposal(c, "p44", "2026-W44", sa, D("100.00"))
        c.execute(insert(supplier_order_groups).values(proposal_id="p44", supplier_id=sb, subtotal=D("30"), delivery_charge=0, total_cost=D("30.00"), minimum_status="met", shortfall_options=[]))
    full = api(engine).get(f"/summary/spend?{RANGE}", headers=H).json()["range"]
    one = api(engine).get(f"/summary/spend?{RANGE}&supplier_id={sa}", headers=H).json()["range"]
    assert full["proposed"] == "130.00" and one["proposed"] == "100.00"


def test_open_orders_are_what_is_confirmed_and_not_yet_received_at_confirmed_cost(engine):
    with engine.begin() as c:
        sa, sb = add_supplier(c, 1), add_supplier(c, 2)
        order(c, "o1", "p1", sa, "confirmed", [(1, 10, D("2.00"), 0)])                         # 20.00
        order(c, "o2", "p2", sa, "partially_received", [(2, 10, D("3.00"), 4)])                # 6 left x 3.00 = 18.00
        order(c, "o3", "p3", sb, "received", [(3, 5, D("9.00"), 5)])                           # nothing left
        order(c, "o4", "p4", sb, "cancelled", [(4, 5, D("9.00"), 0)])                          # cancelled: not counted
        order(c, "o5", "p5", sb, "confirmed", [(5, 2, D("1.25"), 5)])                          # received more than ordered: never negative
    r = api(engine).get(f"/summary/spend?{RANGE}", headers=H).json()
    assert r["open_orders"] == "38.00"
    assert api(engine).get(f"/summary/spend?{RANGE}&supplier_id={sa}", headers=H).json()["open_orders"] == "38.00"
    assert api(engine).get(f"/summary/spend?{RANGE}&supplier_id={sb}", headers=H).json()["open_orders"] == "0.00"


def test_without_a_range_the_answer_keeps_its_old_shape_and_gains_the_open_orders(engine):
    r = api(engine).get("/summary/spend", headers=H).json()
    assert r["range"] is None and r["open_orders"] == "0.00" and r["proposal_id"] is None


def test_a_bad_or_oversized_range_is_refused(engine):
    c = api(engine)
    assert c.get("/summary/spend?date_from=2026-11-09&date_to=2026-10-26", headers=H).status_code == 422
    assert c.get("/summary/spend?date_from=2020-01-01&date_to=2026-11-09", headers=H).status_code == 422
    assert c.get("/summary/spend?date_from=2026-10-26", headers=H).status_code == 422
    assert c.get("/summary/spend?date_from=nope&date_to=2026-11-09", headers=H).status_code == 422


def test_spend_is_the_confirmed_orders_by_week_of_confirmation_and_leaves_the_proposed(engine):
    """T101 (FR-026): a supplier group whose order is confirmed stops being proposed and becomes spend; a cancelled order goes back to proposed; confirmed in another week is another week."""
    with engine.begin() as c:
        sa, sb, sc = add_supplier(c, 1), add_supplier(c, 2), add_supplier(c, 3)
        proposal(c, "p45", "2026-W45", sa, D("100.00"))
        c.execute(insert(supplier_order_groups).values(proposal_id="p45", supplier_id=sb, subtotal=D("30"), delivery_charge=0, total_cost=D("30.00"), minimum_status="met", shortfall_options=[]))
        c.execute(insert(supplier_order_groups).values(proposal_id="p45", supplier_id=sc, subtotal=D("5"), delivery_charge=0, total_cost=D("5.00"), minimum_status="met", shortfall_options=[]))
        order(c, "o1", "p45", sa, "confirmed", [(1, 10, D("9.00"), 0)])                       # 90.00 confirmed on Wed 4 Nov (week 2 Nov)
        order(c, "o2", "p45", sb, "cancelled", [(2, 3, D("10.00"), 0)])                       # cancelled: its group is proposed again, no spend
    r = api(engine).get(f"/summary/spend?{RANGE}", headers=H).json()["range"]
    assert [(w["week_start"], w["proposed"], w["spend"]) for w in r["weeks"]] == [("2026-10-26", "0.00", "0.00"), ("2026-11-02", "35.00", "90.00"), ("2026-11-09", "0.00", "0.00")]
    assert r["proposed"] == "35.00" and r["spend"] == "90.00"
    assert api(engine).get(f"/summary/spend?{RANGE}&supplier_id={sa}", headers=H).json()["range"]["spend"] == "90.00"
    assert api(engine).get(f"/summary/spend?{RANGE}&supplier_id={sb}", headers=H).json()["range"]["spend"] == "0.00"
