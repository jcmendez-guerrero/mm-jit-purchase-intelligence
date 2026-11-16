"""T009: migration 0013 adds the unique budget-cap revision index and downgrades cleanly."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from db.tables import budget_caps
from sqlalchemy.exc import IntegrityError

MIG = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0013_budget_cap_revision.py"
spec = importlib.util.spec_from_file_location("mig0013", MIG)
mig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mig)


def run(eng, fn):
    with eng.begin() as c:
        with Operations.context(MigrationContext.configure(c)):
            fn()


def test_revision_chain_continues_after_0012():
    assert (mig.revision, mig.down_revision) == ("0013", "0012")


def test_the_index_refuses_a_duplicate_revision_even_for_the_global_cap_and_downgrade_removes_it():
    eng = sa.create_engine("sqlite://")
    with eng.begin() as c:
        budget_caps.create(c)                                    # the table as 0006 built it, without the index
        c.execute(sa.text("DROP INDEX IF EXISTS uq_budget_caps_revision"))
    run(eng, mig.upgrade)
    row = {"period": "week", "scope": "global", "scope_key": None, "amount": 1, "valid_from": "2026-11-09", "revision": 1, "changed_by": "u"}
    with eng.begin() as c:
        c.execute(budget_caps.insert().values(id="a", **{**row, "valid_from": sa.func.date("2026-11-09")}))
    with pytest.raises(IntegrityError), eng.begin() as c:
        c.execute(budget_caps.insert().values(id="b", **{**row, "valid_from": sa.func.date("2026-11-09")}))
    run(eng, mig.downgrade)
    assert "uq_budget_caps_revision" not in {i["name"] for i in sa.inspect(eng).get_indexes("budget_caps")}
