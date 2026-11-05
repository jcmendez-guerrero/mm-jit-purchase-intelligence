"""T067/T069: versioned reproducible runs, uncertainty output and forecast.completed.v1."""

from datetime import UTC, datetime

from db.tables import backtest_metrics, forecast_runs, forecast_values, model_registry, outbox
from mmi_common.bus import validate_envelope, verify_payload
from runs.runner import RunConfig, input_hash, model_versions, run_forecast
from sqlalchemy import func, select
from tests_helpers import FakeSource, NullWriter


def count(engine, table):
    with engine.connect() as c:
        return c.execute(select(func.count()).select_from(table)).scalar_one()


def test_a_run_records_versions_hash_config_and_counts(engine, make_export, tmp_path):
    export = make_export()
    res = run_forecast(engine, FakeSource(export), NullWriter(tmp_path))
    with engine.connect() as c:
        run = c.execute(select(forecast_runs)).one()
    assert run.status == "completed" and run.input_hash == res.input_hash == input_hash(export, RunConfig())
    assert run.model_versions == model_versions() and "minmax_poisson" in run.model_versions and run.config["horizons"] == [7, 14, 21, 28, 42]
    assert (run.total_count, run.eligible_count) == (5, 3) == (res.total, res.eligible)


def test_identical_inputs_reproduce_the_same_outputs_and_are_not_duplicated(engine, make_export, tmp_path):
    first = run_forecast(engine, FakeSource(make_export(seed=3)), NullWriter(tmp_path))
    again = run_forecast(engine, FakeSource(make_export(seed=3)), NullWriter(tmp_path))
    assert again.reused and again.run_id == first.run_id
    assert count(engine, forecast_runs) == 1 and count(engine, outbox) == 1


def test_changed_inputs_or_configuration_create_a_new_run(engine, make_export, tmp_path):
    run_forecast(engine, FakeSource(make_export(seed=3)), NullWriter(tmp_path))
    other = run_forecast(engine, FakeSource(make_export(seed=4)), NullWriter(tmp_path))
    cfg = run_forecast(engine, FakeSource(make_export(seed=3)), NullWriter(tmp_path), RunConfig(lead_time=10))
    assert not other.reused and not cfg.reused and count(engine, forecast_runs) == 3


def test_same_inputs_give_identical_values_in_two_databases(make_export, tmp_path):
    from db.tables import metadata
    from sqlalchemy import create_engine

    outs = []
    for i in range(2):
        eng = create_engine("sqlite://")
        metadata.create_all(eng)
        run_forecast(eng, FakeSource(make_export(seed=9)), NullWriter(tmp_path / str(i)))
        with eng.connect() as c:
            outs.append(sorted((r.variant_id, r.horizon_days, r.mean, str(r.quantiles), r.policy_used) for r in c.execute(select(forecast_values)).all()))
    assert outs[0] == outs[1]


def test_uncertainty_is_expressed_as_quantiles_that_grow_with_the_horizon_and_level(engine, make_export, tmp_path):
    run_forecast(engine, FakeSource(make_export()), NullWriter(tmp_path))
    with engine.connect() as c:
        rows = [r for r in c.execute(select(forecast_values).where(forecast_values.c.variant_id == 1)).all()]
    by_h = {r.horizon_days: r for r in rows}
    assert by_h[7].mean < by_h[42].mean and by_h[7].quantiles["0.99"] <= by_h[42].quantiles["0.99"]
    q = by_h[14].quantiles
    assert q["0.85"] <= q["0.90"] <= q["0.95"] <= q["0.97"] <= q["0.99"]
    assert q["0.95"] >= by_h[14].mean * 0.8   # the service-level quantile sits at or above the typical level


def test_completed_event_is_valid_and_carries_the_run(engine, make_export, tmp_path):
    res = run_forecast(engine, FakeSource(make_export()), NullWriter(tmp_path))
    with engine.connect() as c:
        env = c.execute(select(outbox)).one().envelope
    validate_envelope(env, now=datetime.now(UTC))
    from pathlib import Path

    payload = Path(env["payload_ref"]["uri"].removeprefix("file://")).read_bytes()
    verify_payload(env, payload)
    assert env["type"] == "forecast.completed.v1" and env["resource_id"] == res.run_id
    assert b'"eligible_count":3' in payload and res.input_hash.encode() in payload


def test_backtests_and_model_registry_are_stored(engine, make_export, tmp_path):
    run_forecast(engine, FakeSource(make_export(n_smooth=12)), NullWriter(tmp_path))
    with engine.connect() as c:
        bt = c.execute(select(backtest_metrics)).all()
        reg = {r.name for r in c.execute(select(model_registry)).all()}
    assert {r.policy for r in bt} >= {"minmax_poisson", "tsb"} and all(r.segment == "smooth" for r in bt)
    assert sum(1 for r in bt if r.adopted) <= 1 and reg >= {"minmax_poisson", "croston_sba", "adida"}


def test_job_runs_against_an_http_source(monkeypatch, tmp_path, make_export):
    import job
    from sqlalchemy import create_engine

    db = tmp_path / "f.db"
    from db.tables import metadata

    metadata.create_all(create_engine(f"sqlite:///{db}"))
    export = make_export()

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return export

    class Client:
        def __init__(self, *a, **k):
            pass

        def get(self, url, headers=None):
            assert url.endswith("/export/series") and headers["Authorization"].startswith("Bearer ")
            return Resp()

    monkeypatch.setattr("runs.sources.httpx.Client", Client)
    for k, v in {"MMI_DATABASE_URL": f"sqlite:///{db}", "MMI_INVENTORY_URL": "http://inv.test", "MMI_INVENTORY_TOKEN": "t", "MMI_BLOB_ROOT": str(tmp_path / "b")}.items():
        monkeypatch.setenv(k, v)
    assert job.main() == 0
    assert job.main() == 0     # an identical second run is recognised, not duplicated
    with create_engine(f"sqlite:///{db}").connect() as c:
        assert c.execute(select(func.count()).select_from(forecast_runs)).scalar_one() == 1


def test_job_fails_visibly_without_configuration(monkeypatch):
    import job

    monkeypatch.delenv("MMI_DATABASE_URL", raising=False)
    assert job.main() == 1
