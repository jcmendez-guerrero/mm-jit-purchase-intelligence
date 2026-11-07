"""T183 (FR-026, SC-006): a proposal and a scenario record the exact dataset and forecast run behind them, without changing any hash."""

from conftest import NOW, add_product, add_supplier  # noqa: F401
from db.tables import proposals
from proposals.generate import generate, store
from proposals.inputs import InputsProvider
from proposals.model import inputs_hash
from scen import Blob
from scenarios import store as sc
from scenarios.engine import RULE_VERSIONS, ScenarioParams, input_fingerprint
from sqlalchemy import select
from test_inputs import ELIGIBLE, TODAY, Src, cost, fc, stock, sv

D = __import__("decimal").Decimal


def build(conn, run_id="run-1", dataset="d1d1d1d1-0000-4000-8000-000000000001"):
    doc = {**fc(v1=ELIGIBLE), "run_id": run_id, "dataset_version_id": dataset}
    return InputsProvider(Src(stock(sv(1, 10))), Src(doc)).build(conn, TODAY)


def test_the_inputs_carry_the_forecast_run_and_the_dataset_it_used(conn):
    sa = add_supplier(conn)
    cost(conn, sa, 10)
    inp = build(conn)
    assert (inp.forecast_run_id, inp.dataset_version_id) == ("run-1", "d1d1d1d1-0000-4000-8000-000000000001")
    plain = InputsProvider(Src(stock(sv(1, 10))), Src(fc(v1=ELIGIBLE))).build(conn, TODAY)          # an older forecast payload without them
    assert plain.dataset_version_id is None and plain.forecast_run_id == "run-1"


def test_the_versions_never_change_a_hash_so_unchanged_inputs_still_give_identical_results(conn):
    sa = add_supplier(conn)
    cost(conn, sa, 10)
    a, b = build(conn, "run-1", "d1d1d1d1-0000-4000-8000-000000000001"), build(conn, "run-2", None)
    assert inputs_hash(a, {"x": "1"}) == inputs_hash(b, {"x": "1"}) and input_fingerprint(a) == input_fingerprint(b)


def test_a_stored_proposal_names_the_dataset_and_the_run(conn):
    sa = add_supplier(conn)
    cost(conn, sa, 10)
    pid = store(conn, generate(build(conn), 10), "buyer-1", "2026-W46", None, NOW)
    row = conn.execute(select(proposals).where(proposals.c.id == pid)).one()
    assert (row.dataset_version_id, row.forecast_run_id) == ("d1d1d1d1-0000-4000-8000-000000000001", "run-1")


def test_a_scenario_records_the_dataset_and_the_run_in_its_input_versions(conn, tmp_path):
    sa = add_supplier(conn)
    cost(conn, sa, 10)
    out = sc.create(conn, Blob(tmp_path), "Escenario", ScenarioParams(), build(conn), "buyer-1", "k-ver-00001", NOW)
    assert out["input_versions"]["dataset"] == "d1d1d1d1-0000-4000-8000-000000000001" and out["input_versions"]["forecast_run"] == "run-1"
    assert out["input_versions"]["rules"] == RULE_VERSIONS


def test_without_a_dataset_the_versions_say_so_rather_than_inventing_one(conn, tmp_path):
    sa = add_supplier(conn)
    cost(conn, sa, 10)
    out = sc.create(conn, Blob(tmp_path), "Escenario", ScenarioParams(), build(conn, dataset=None), "buyer-1", "k-ver-00002", NOW)
    assert out["input_versions"]["dataset"] is None
