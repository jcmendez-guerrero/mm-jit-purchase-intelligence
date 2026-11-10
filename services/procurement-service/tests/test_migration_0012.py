"""T008: migration 0012 creates the idempotency and exchange-rate tables exactly as db.tables defines them, and downgrades cleanly."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from db.tables import fx_rates, terms_idempotency

MIG = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0012_terms_idempotency_fx_rates.py"
spec = importlib.util.spec_from_file_location("mig0012", MIG)
mig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mig)


def run(eng, fn):
    with eng.begin() as c:
        with Operations.context(MigrationContext.configure(c)):
            fn()


def columns(eng, table):
    return {c["name"]: c for c in sa.inspect(eng).get_columns(table)}


def test_revision_chain_continues_after_0011():
    assert (mig.revision, mig.down_revision) == ("0012", "0011")


def test_upgrade_matches_the_table_definitions_and_downgrade_removes_them():
    eng = sa.create_engine("sqlite://")
    run(eng, mig.upgrade)
    for table in (terms_idempotency, fx_rates):
        assert set(columns(eng, table.name)) == {c.name for c in table.columns}, table.name
        assert set(sa.inspect(eng).get_pk_constraint(table.name)["constrained_columns"]) == {c.name for c in table.primary_key.columns}
    assert {i["name"] for i in sa.inspect(eng).get_indexes("terms_idempotency")} == {"ix_terms_idempotency_created_at"}
    run(eng, mig.downgrade)
    assert not {"terms_idempotency", "fx_rates"} & set(sa.inspect(eng).get_table_names())


def test_exact_decimal_rate_and_composite_keys_are_defined():
    assert isinstance(fx_rates.c.eur_per_unit.type, sa.Numeric) and fx_rates.c.eur_per_unit.type.scale == 12
    assert [c.name for c in fx_rates.primary_key.columns] == ["currency", "published_on"]
    assert [c.name for c in terms_idempotency.primary_key.columns] == ["scope", "key"]
