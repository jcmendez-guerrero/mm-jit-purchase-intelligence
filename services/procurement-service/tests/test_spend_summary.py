"""T121 (procurement side) + T130: proposed spend and its split by supplier."""

from decimal import Decimal

from api import costs, summary
from builders import flat_forecast, inputs, offer, terms, variant
from conftest import NOW, add_supplier
from costs.rules import CostRules
from costs.store import NewCost, add_version
from db.tables import erp_supplier_links
from fastapi.testclient import TestClient
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app
from policies.service import save_budget_cap
from proposals.generate import generate, store
from sqlalchemy import insert

D = Decimal


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


H = {"Authorization": "Bearer viewer"}


def propose(conn, budget=None):
    sa, sb = add_supplier(conn, 1, "Proveedor A"), add_supplier(conn, 2, "Proveedor B")
    for sid, cost in ((sa, "1.00"), (sb, "2.00")):
        add_version(conn, NewCost(product_id=10, supplier_id=sid, cost_with_recargo=D(cost), source="siweb_product_supplier", actor="siweb-import"), CostRules(), NOW)
        conn.execute(insert(erp_supplier_links).values(product_id=10, supplier_id=sid, has_cost=True, last_seen_at=NOW))
    d = generate(inputs([variant(1, [offer(sa, "1.00")], flat_forecast(1.0)), variant(2, [offer(sb, "2.00")], flat_forecast(1.0))], [terms(sa), terms(sb)]), 10)
    pid = store(conn, d, "buyer-1", "2026-W46", budget, NOW)
    return pid, sa, sb


def test_no_proposal_gives_an_empty_summary(engine):
    r = api(engine).get("/summary/spend", headers=H).json()
    assert r["proposal_id"] is None and r["total"] == "0.00" and r["by_supplier"] == [] and r["over_budget"] is False


def test_the_total_is_the_sum_of_the_order_groups_and_split_by_supplier(engine):
    with engine.begin() as c:
        pid, _sa, _sb = propose(c)
    r = api(engine).get("/summary/spend", headers=H).json()
    assert r["proposal_id"] == pid and r["week"] == "2026-W46" and r["status"] == "draft"
    assert {x["supplier_name"] for x in r["by_supplier"]} == {"Proveedor A", "Proveedor B"}
    assert D(r["total"]) == sum(D(x["total"]) for x in r["by_supplier"]) and D(r["total"]) > 0


def test_the_supplier_filter_narrows_the_total_and_never_flags_over_budget(engine):
    with engine.begin() as c:
        _pid, sa, _sb = propose(c, budget=D("1"))
    full = api(engine).get("/summary/spend", headers=H).json()
    one = api(engine).get(f"/summary/spend?supplier_id={sa}", headers=H).json()
    assert full["over_budget"] is True and D(one["total"]) < D(full["total"]) and len(one["by_supplier"]) == 1 and one["over_budget"] is False


def test_the_budget_in_the_policies_is_shown_when_the_proposal_has_none(engine):
    with engine.begin() as c:
        propose(c)
        save_budget_cap(c, "week", "global", None, D("500"), "buyer-1")
    r = api(engine).get("/summary/spend", headers=H).json()
    assert r["budget"] == "500.00" and r["over_budget"] is False


def test_a_superseded_proposal_is_not_the_one_summarised(engine):
    from db.tables import proposals
    from sqlalchemy import update

    with engine.begin() as c:
        pid, _, _ = propose(c)
        c.execute(update(proposals).where(proposals.c.id == pid).values(status="superseded"))
    assert api(engine).get("/summary/spend", headers=H).json()["proposal_id"] is None


def test_authentication_is_required(engine):
    assert api(engine).get("/summary/spend").status_code == 401
