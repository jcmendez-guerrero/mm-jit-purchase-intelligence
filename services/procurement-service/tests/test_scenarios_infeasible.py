"""T137: an unreachable budget or minimum is explained, and clinical-critical needs are shown, never dropped."""

from decimal import Decimal

from conftest import NOW
from scen import Blob, base, suppliers
from scenarios import store as sc
from scenarios.engine import ScenarioParams

D = Decimal


def test_a_low_cap_explains_the_shortfall_and_keeps_every_clinical_critical_need(conn, tmp_path):
    sa, sb = suppliers(conn)
    out = sc.create(conn, Blob(tmp_path), "Tope bajo", ScenarioParams(budget=D("5")), base(sa, sb, critical=True), "buyer-1", "k-inf-000001", NOW)
    inf = out["summary"]["infeasible"]
    assert out["status"] == "ready" and D(inf["over_by"]) == D("25.00") and inf["clinical_critical_variants"] == [1]
    critical_lines = [ln for r in out["results"] for ln in r["lines"] if ln["variant_id"] == 1]
    assert critical_lines and critical_lines[0]["qty"] > 0 and critical_lines[0]["clinical_critical"] is True


def test_a_feasible_scenario_has_no_infeasibility_block(conn, tmp_path):
    sa, sb = suppliers(conn)
    out = sc.create(conn, Blob(tmp_path), "Holgado", ScenarioParams(budget=D("1000")), base(sa, sb), "buyer-1", "k-inf-000002", NOW)
    assert out["summary"]["infeasible"] is None and D(out["summary"]["scenario"]["over_budget"]) == 0


def test_an_unreachable_minimum_is_a_flagged_shortfall_with_the_supplier_named(conn, tmp_path):
    sa, sb = suppliers(conn)
    only_a = ScenarioParams(disabled_suppliers=(sb,))
    out = sc.create(conn, Blob(tmp_path), "Solo A", only_a, base(sa, sb, a_min="500"), "buyer-1", "k-inf-000003", NOW)
    assert any(c["key"] == f"min_order:{sa}" and c["params"]["status"] == "shortfall" for c in out["summary"]["binding"])
    assert out["results"][0]["binding_constraints"][0]["key"] == f"min_order:{sa}"
