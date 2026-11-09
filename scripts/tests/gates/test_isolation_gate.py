"""T014: isolation gate against throwaway service folders."""

from __future__ import annotations

from pathlib import Path

import pytest
from gates import isolation_gate as g

OWN = {"inventory-service": "inventory", "procurement-service": "procurement"}


def _svc(root: Path, service: str, name: str, text: str) -> None:
    f = root / "services" / service / "src" / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


@pytest.mark.parametrize("sql", [
    "SELECT 1 FROM procurement.orders",
    "select * from other join procurement.lots on 1=1",
    'ForeignKey("procurement.orders.id")',
    '{"schema": "procurement"}',
    "SET search_path = procurement",
])
def test_foreign_schema_reference_fails(tmp_path, sql):
    _svc(tmp_path, "inventory-service", "q.py", sql)
    problems = g.scan(tmp_path, OWN)
    assert problems and "procurement" in problems[0]


@pytest.mark.parametrize("sql", [
    "SELECT 1 FROM inventory.stock",
    "inventory = load()",
    "from procurement_client import procurement",
    '"""projection (from procurement.order.confirmed.v1)."""',
])
def test_own_schema_and_plain_words_pass(tmp_path, sql):
    _svc(tmp_path, "inventory-service", "q.py", sql)
    assert g.scan(tmp_path, OWN) == []


def test_tests_folders_are_ignored(tmp_path):
    f = tmp_path / "services/inventory-service/tests/t.py"
    f.parent.mkdir(parents=True)
    f.write_text("FROM procurement.orders")
    assert g.scan(tmp_path, OWN) == []


def stub(rc=0, out=""):
    from types import SimpleNamespace

    return lambda argv, **kw: SimpleNamespace(returncode=rc, stdout=out, stderr="")


def _root(tmp_path):
    (tmp_path / "infra/tests").mkdir(parents=True)
    (tmp_path / "infra/tests/test_migrations_postgres.py").write_text("")
    return tmp_path


def test_database_check_is_off_by_default_and_says_so(tmp_path):
    r = g.run(_root(tmp_path), OWN)
    assert r.result == "pass" and any("role grants not checked" in e for e in r.evidence)


def test_database_check_passing_failing_and_skipped(tmp_path):
    root = _root(tmp_path)
    have = lambda tool: f"/usr/bin/{tool}"  # noqa: E731  (pretend Docker is installed)
    assert g.run(root, OWN, database=True, runner=stub(0, "6 passed in 40s"), which=have).result == "pass"
    failed = g.run(root, OWN, database=True, runner=stub(1, "FAILED infra/tests/test_migrations_postgres.py::test_roles - boom\n"), which=have)
    assert failed.result == "fail" and any("test_roles" in e for e in failed.evidence)
    assert g.run(root, OWN, database=True, runner=stub(0, "6 skipped in 0.1s"), which=have).result == "not_run"
    assert g.run(root, OWN, database=True, runner=stub(0, "6 passed"), which=lambda t: None).result == "not_run"  # no Docker


def test_static_failure_wins_over_database_not_run(tmp_path):
    root = _root(tmp_path)
    _svc(root, "inventory-service", "q.py", "FROM procurement.orders")
    assert g.run(root, OWN, database=True, runner=stub(0, "6 skipped"), which=lambda t: t).result == "fail"


def test_run_results(tmp_path):
    assert g.run(tmp_path, {}).result == "not_run"
    _svc(tmp_path, "inventory-service", "q.py", "FROM procurement.orders")
    assert g.run(tmp_path, OWN).result == "fail"
