"""T138: sensitivity covers only the strongest binding constraints and stays inside the runtime budget."""

import time
from decimal import Decimal

from conftest import NOW
from scen import Blob, base, suppliers
from scenarios import engine as eng
from scenarios import store as sc
from scenarios.engine import ScenarioParams, apply_params, binding_constraints, sensitivity, solve

D = Decimal


def test_relaxing_a_binding_threshold_reports_what_it_would_change(conn, tmp_path):
    sa, sb = suppliers(conn)
    out = sc.create(conn, Blob(tmp_path), "Envío gratis", ScenarioParams(), base(sa, sb, a_free="30", a_charge="5"), "buyer-1", "k-sen-000001", NOW)
    s = out["sensitivity"]
    assert [x["constraint_key"] for x in s] == [f"free_delivery:{sa}"] and s[0]["delta"] == "-10%" and D(s[0]["cost_impact"]) == D("0.00")      # already free at 27 too: no saving


def test_an_exceeded_budget_is_the_first_constraint_and_its_relaxation_is_solved(conn, tmp_path):
    sa, sb = suppliers(conn)
    b = base(sa, sb)
    p = ScenarioParams(budget=D("20"))
    draft = solve(apply_params(b, p), 5)
    assert binding_constraints(draft, p)[0]["key"] == "budget"
    assert sensitivity(b, p, draft)[0]["constraint_key"] == "budget"


def test_at_most_the_top_n_constraints_are_re_solved(monkeypatch):
    sa, sb = "A", "B"
    b = base(sa, sb, a_free="30", a_charge="5")
    p = ScenarioParams(budget=D("20"))
    draft = solve(apply_params(b, p), 5)
    calls = []
    real = eng.solve
    monkeypatch.setattr(eng, "solve", lambda inputs, t=20.0: calls.append(t) or real(inputs, t))
    sensitivity(b, p, draft, top=1)
    assert len(calls) == 1 and calls[0] == eng.SENSITIVITY_SECONDS


def test_the_whole_creation_stays_well_inside_the_runtime_budget_for_a_small_catalogue(conn, tmp_path):
    sa, sb = suppliers(conn)
    t0 = time.perf_counter()
    sc.create(conn, Blob(tmp_path), "Rápido", ScenarioParams(budget=D("20")), base(sa, sb, n=30), "buyer-1", "k-sen-000004", NOW)
    assert time.perf_counter() - t0 < 30


def test_nothing_binding_means_no_sensitivity_rows(conn, tmp_path):
    sa, sb = suppliers(conn)
    out = sc.create(conn, Blob(tmp_path), "Sin límites", ScenarioParams(), base(sa, sb), "buyer-1", "k-sen-000005", NOW)
    assert out["sensitivity"] == []
