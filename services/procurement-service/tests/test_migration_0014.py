"""T083: migration 0014 widens cost_write_requests.status (approved_by_buyer is 17 characters, the column held 16) and downgrades cleanly."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from db.tables import cost_write_requests

MIG = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0014_cost_write_status_length.py"
spec = importlib.util.spec_from_file_location("mig0014", MIG)
mig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mig)


def test_revision_chain_continues_after_0013():
    assert (mig.revision, mig.down_revision) == ("0014", "0013")


def test_the_model_holds_the_longest_status_the_code_writes():
    from costs.writes import OPEN_STATES

    assert cost_write_requests.c.status.type.length >= max(len(s) for s in (*OPEN_STATES, "approved_by_buyer", "released", "rejected", "confirmed"))


def test_the_migration_widens_the_column_and_is_reversible():
    eng = sa.create_engine("sqlite://")
    with eng.begin() as c:
        c.execute(sa.text("create table cost_write_requests (id varchar(36) primary key, status varchar(16) not null)"))
    with eng.begin() as c, Operations.context(MigrationContext.configure(c)):
        mig.upgrade()
    assert next(col for col in sa.inspect(eng).get_columns("cost_write_requests") if col["name"] == "status")["type"].length == 24
    with eng.begin() as c, Operations.context(MigrationContext.configure(c)):
        mig.downgrade()
    assert next(col for col in sa.inspect(eng).get_columns("cost_write_requests") if col["name"] == "status")["type"].length == 16
