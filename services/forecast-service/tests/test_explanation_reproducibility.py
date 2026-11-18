"""T030: the same inputs and versions give identical explanations; changed inputs add new ones and keep the old (FR-009, FR-011, SC-005)."""

from db.tables import forecast_explanations, forecast_runs
from runs.runner import RunConfig, run_forecast
from sqlalchemy import func, select
from tests_helpers import FakeSource, NullWriter


def rows(engine, run_id=None):
    with engine.connect() as c:
        q = select(forecast_explanations).order_by(forecast_explanations.c.run_id, forecast_explanations.c.variant_id)
        if run_id:
            q = q.where(forecast_explanations.c.run_id == run_id)
        return [tuple(r) for r in c.execute(q).all()]


def test_a_run_stores_one_explanation_per_product_with_the_run_versions(engine, make_export, tmp_path):
    res = run_forecast(engine, FakeSource(make_export(seed=3)), NullWriter(tmp_path))
    stored = rows(engine, res.run_id)
    assert len(stored) == res.total == 5
    with engine.connect() as c:
        run = c.execute(select(forecast_runs)).one()
        exp = {r.sku: r for r in c.execute(select(forecast_explanations)).all()}
    assert {r.model_version.split("@")[0] for r in exp.values()} <= set(run.model_versions)
    assert exp["EJ-100"].eligibility == "not_eligible" and exp["EJ-100"].expected is None and exp["EJ-1"].eligibility == "eligible" and exp["EJ-1"].expected is not None
    assert exp["EJ-1"].history_start.isoformat() == "2026-01-01"


def test_identical_inputs_reuse_the_run_and_the_explanations_are_unchanged(engine, make_export, tmp_path):
    first = run_forecast(engine, FakeSource(make_export(seed=3)), NullWriter(tmp_path))
    before = rows(engine)
    again = run_forecast(engine, FakeSource(make_export(seed=3)), NullWriter(tmp_path))
    assert again.reused and again.run_id == first.run_id and rows(engine) == before


def test_the_same_inputs_give_identical_explanations_in_two_databases(make_export, tmp_path):
    from db.tables import metadata
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    out = []
    for _ in range(2):
        eng = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
        metadata.create_all(eng)
        run_forecast(eng, FakeSource(make_export(seed=3)), NullWriter(tmp_path))
        out.append([r[1:] for r in rows(eng)])            # without the run id, which is random
    assert out[0] == out[1]


def test_changed_inputs_make_a_new_run_with_new_explanations_and_keep_the_old(engine, make_export, tmp_path):
    first = run_forecast(engine, FakeSource(make_export(seed=3)), NullWriter(tmp_path))
    old = rows(engine, first.run_id)
    other = run_forecast(engine, FakeSource(make_export(seed=4)), NullWriter(tmp_path))
    cfg = run_forecast(engine, FakeSource(make_export(seed=3)), NullWriter(tmp_path), RunConfig(lead_time=10))
    assert not other.reused and not cfg.reused and len({first.run_id, other.run_id, cfg.run_id}) == 3
    assert rows(engine, first.run_id) == old                                    # the old explanation is never overwritten
    with engine.connect() as c:
        assert c.execute(select(func.count()).select_from(forecast_explanations)).scalar() == 15
