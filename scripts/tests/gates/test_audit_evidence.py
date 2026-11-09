"""T008: audit evidence must point at real lines, and `complete` needs test evidence."""

from __future__ import annotations

from pathlib import Path

from gates import audit_check as a


def _feature(status="partial", evidence=("src/a.py:1",)):
    return {"id": "f", "title": "F", "status": status, "evidence": list(evidence), "owner": "x"}


def _root(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/a.py").write_text("one\ntwo\nthree\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_a.py").write_text("def test_a(): ...\n")
    return tmp_path


def test_valid_evidence_passes(tmp_path):
    assert a.check(_root(tmp_path), {"features": [_feature()]}) == []


def test_missing_path_fails(tmp_path):
    problems = a.check(_root(tmp_path), {"features": [_feature(evidence=["src/none.py:1"])]})
    assert any("missing" in p for p in problems)


def test_line_beyond_file_or_zero_fails(tmp_path):
    root = _root(tmp_path)
    assert any("line" in p for p in a.check(root, {"features": [_feature(evidence=["src/a.py:99"])]}))
    assert any("line" in p for p in a.check(root, {"features": [_feature(evidence=["src/a.py:0"])]}))


def test_complete_requires_test_evidence(tmp_path):
    root = _root(tmp_path)
    assert any("test" in p for p in a.check(root, {"features": [_feature("complete")]}))
    ok = _feature("complete", ["src/a.py:1", "tests/test_a.py:1"])
    assert a.check(root, {"features": [ok]}) == []


def test_the_markdown_view_has_blank_lines_around_headings_and_lists():
    """markdownlint (MD022, MD032) runs in CI on the generated file."""
    audit = {"audited_commit": "abc1234", "features": [
        {"id": "a", "title": "A", "status": "partial", "evidence": ["x.py:1"], "owner": "svc", "reuse": True},
        {"id": "b", "title": "B", "status": "complete", "evidence": ["y.py:1"], "owner": "svc", "reuse": True}]}
    lines = a.render(audit).splitlines()
    for i, line in enumerate(lines):
        if line.startswith("#"):
            assert lines[i - 1] == "" or i == 0, f"no blank line above: {line}"
            assert lines[i + 1] == "", f"no blank line below: {line}"
        if line.startswith("- ") and not lines[i - 1].startswith("- "):
            assert lines[i - 1] == "", f"no blank line above the list at: {line}"
    assert "- **svc**: a (partial)" in lines


def test_duplicate_ids_fail(tmp_path):
    assert any("duplicate" in p for p in a.check(_root(tmp_path), {"features": [_feature(), _feature()]}))
