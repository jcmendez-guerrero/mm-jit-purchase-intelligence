"""T037: every platform guarantee maps to an existing test file that the security gate runs."""

from __future__ import annotations

from pathlib import Path

from conftest import REPO
from gates import guarantees as g
from gates import suite_gate as s

MAP = "docs/architecture/integration/guarantee-test-map.md"


def _root(tmp_path: Path, rows: str) -> Path:
    f = tmp_path / MAP
    f.parent.mkdir(parents=True)
    f.write_text("| Guarantee | Covering test file |\n|---|---|\n" + rows)
    return tmp_path


def _all_rows(test="`t/test_a.py`"):
    return "".join(f"| {name} | {test} |\n" for name in g.REQUIRED)


def test_real_map_is_complete_and_files_exist():
    assert g.check(REPO) == []


def test_missing_file_is_reported(tmp_path):
    root = _root(tmp_path, _all_rows())
    assert any("t/test_a.py" in p and "missing" in p for p in g.check(root))


def test_missing_guarantee_row_is_reported(tmp_path):
    (tmp_path / "t").mkdir()
    (tmp_path / "t/test_a.py").write_text("")
    root = _root(tmp_path, "".join(f"| {n} | `t/test_a.py` |\n" for n in g.REQUIRED[1:]))
    assert any(g.REQUIRED[0] in p for p in g.check(root))


def test_security_suite_runs_the_mapped_tests():
    covered = {p for c in s.suite("security", REPO) for p in c.requires_paths}
    assert all(path in covered for path in g.mapped_tests(REPO))


def test_mapped_package_tests_run_in_their_own_package_folder():
    cmds = [c for c in s.suite("security", REPO) if c.argv[1:3] == ("-m", "pytest")]
    packages = [c for c in cmds if c.cwd.startswith("packages/")]
    assert packages, "the map names tests under packages/, which must run from their package folder"
    assert all(not any(a.startswith("packages/") for a in c.argv) for c in packages)


def test_services_are_never_collected_in_one_pytest_process():
    cmds = [c for c in s.suite("security", REPO) if c.argv[1:3] == ("-m", "pytest")]
    service_dirs = [c.cwd for c in cmds if c.cwd.startswith("services/")]
    assert len(service_dirs) == len(set(service_dirs)) > 1
    assert all(not any(a.startswith("services/") for a in c.argv) for c in cmds)
