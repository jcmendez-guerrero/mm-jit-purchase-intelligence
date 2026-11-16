"""Feature 011 (T078): two censoring-rule saves that read the same revision are caught by the database: the loser gets the conflict, never a server error or a duplicate."""

import importlib.util
from datetime import date
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from db.tables import censoring_rules
from projections import rules
from projections.rules import RuleConflict, set_censoring_rule
from sqlalchemy import func, select

TODAY = date(2026, 11, 9)
RULE = "min_zero_stock_days"


def test_a_save_that_loses_the_race_is_a_conflict_and_stores_nothing(engine, monkeypatch):
    with engine.begin() as c:
        set_censoring_rule(c, RULE, 3, "a", today=TODAY)
    real, calls = rules.censoring_revision, {"n": 0}

    def stale_first_read(*a, **k):                            # the loser read the revision before the winner committed
        calls["n"] += 1
        return 0 if calls["n"] == 1 else real(*a, **k)

    monkeypatch.setattr(rules, "censoring_revision", stale_first_read)
    with engine.begin() as c:
        with pytest.raises(RuleConflict) as e:
            set_censoring_rule(c, RULE, 4, "b", today=TODAY, expected_revision=0)
        assert e.value.current_revision == 1
        assert c.execute(select(func.count()).select_from(censoring_rules)).scalar() == 1


def test_the_unique_revision_index_migration_stops_on_duplicates_and_is_reversible():
    path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0010_censoring_unique_revision.py"
    spec = importlib.util.spec_from_file_location("mig0010", path)
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)
    assert (mig.revision, mig.down_revision) == ("0010", "0009")
    eng = sa.create_engine("sqlite://")
    with eng.begin() as c:
        c.execute(sa.text("create table censoring_rules (id integer primary key, rule varchar(40), scope varchar(10), key varchar(40), value integer, valid_from date, "
                          "revision integer, changed_by varchar(120))"))
        c.execute(sa.text("insert into censoring_rules (rule, scope, key, value, valid_from, revision, changed_by) values "
                          "('r', 'global', '*', 3, '2026-10-01', 1, 'u'), ('r', 'global', '*', 4, '2026-10-01', 1, 'v')"))
    with pytest.raises(sa.exc.IntegrityError), eng.begin() as c, Operations.context(MigrationContext.configure(c)):
        mig.upgrade()                                         # duplicates already stored: stop, rewrite nothing
    with eng.begin() as c:
        c.execute(sa.text("delete from censoring_rules where value = 4"))
    with eng.begin() as c, Operations.context(MigrationContext.configure(c)):
        mig.upgrade()
    assert "uq_censoring_rules_revision" in {i["name"] for i in sa.inspect(eng).get_indexes("censoring_rules")}
    with eng.begin() as c, Operations.context(MigrationContext.configure(c)):
        mig.downgrade()
    assert "uq_censoring_rules_revision" not in {i["name"] for i in sa.inspect(eng).get_indexes("censoring_rules")}
