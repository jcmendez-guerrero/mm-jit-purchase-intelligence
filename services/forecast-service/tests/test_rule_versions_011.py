"""Feature 011 (T040): a run records the exclusion and censoring-rule revisions of the export it used, and the run list shows them."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from db.tables import forecast_runs
from runs.runner import run_forecast
from sqlalchemy import select
from tests_helpers import FakeSource, NullWriter

MIG = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0006_run_rule_versions.py"
spec = importlib.util.spec_from_file_location("mig0006", MIG)
mig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mig)


def test_a_run_stores_the_rule_versions_of_its_export(engine, make_export, tmp_path):
    export = {**make_export(), "rule_versions": {"exclusions": 2, "censoring.min_zero_stock_days": 1}}
    run_forecast(engine, FakeSource(export), NullWriter(tmp_path))
    with engine.connect() as c:
        assert c.execute(select(forecast_runs)).one().rule_version_ids == {"exclusions": 2, "censoring.min_zero_stock_days": 1}


def test_an_export_without_rule_versions_leaves_the_column_empty(engine, make_export, tmp_path):
    run_forecast(engine, FakeSource(make_export()), NullWriter(tmp_path))
    with engine.connect() as c:
        assert c.execute(select(forecast_runs)).one().rule_version_ids is None


def test_migration_0006_adds_and_removes_the_column():
    eng = sa.create_engine("sqlite://")
    with eng.begin() as c:
        c.execute(sa.text("create table forecast_runs (id varchar(36) primary key)"))
    for fn, present in ((mig.upgrade, True), (mig.downgrade, False)):
        with eng.begin() as c, Operations.context(MigrationContext.configure(c)):
            fn()
        assert ("rule_version_ids" in {col["name"] for col in sa.inspect(eng).get_columns("forecast_runs")}) is present
    assert (mig.revision, mig.down_revision) == ("0006", "0005")
