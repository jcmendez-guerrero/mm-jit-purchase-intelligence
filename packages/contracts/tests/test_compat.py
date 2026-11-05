"""Schema validity and compatibility against the committed baseline (constitution Principle IV).

Rules: every schema is valid draft 2020-12; event type names carry a version suffix; compared
to ``baseline/`` a change may only be additive (no removed or retyped properties, no new
required property, no narrowed enum). A breaking change needs a new versioned file name.
Refresh the baseline deliberately with ``python packages/contracts/tools/update_baseline.py``.
"""

import json
import re
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
CURRENT = sorted([*ROOT.glob("events/*.schema.json"), *ROOT.glob("dto/*.schema.json")])
BASELINE = ROOT / "baseline"


def load(p: Path):
    return json.loads(p.read_text())


@pytest.mark.parametrize("path", CURRENT, ids=lambda p: p.name)
def test_schema_is_valid_draft_2020_12(path):
    jsonschema.Draft202012Validator.check_schema(load(path))


def test_event_files_are_versioned():
    for p in ROOT.glob("events/*.schema.json"):
        assert re.search(r"\.v[0-9]+\.schema\.json$", p.name), p.name


def _breaking(old: dict, new: dict, path="") -> list[str]:
    problems = []
    for key, spec in old.get("properties", {}).items():
        if key not in new.get("properties", {}):
            problems.append(f"{path}{key}: removed")
            continue
        n = new["properties"][key]
        if spec.get("type") != n.get("type") and "$ref" not in spec:
            problems.append(f"{path}{key}: type changed")
        if "enum" in spec and not set(spec["enum"]) <= set(n.get("enum", spec["enum"])):
            problems.append(f"{path}{key}: enum narrowed")
        if spec.get("type") == "object":
            problems += _breaking(spec, n, f"{path}{key}.")
    added_required = set(new.get("required", [])) - set(old.get("required", []))
    if added_required:
        problems.append(f"{path}new required: {sorted(added_required)}")
    for name, sub in old.get("$defs", {}).items():
        if name in new.get("$defs", {}):
            problems += _breaking(sub, new["$defs"][name], f"{path}${name}.")
    return problems


@pytest.mark.parametrize("path", sorted(BASELINE.glob("*/*.schema.json")), ids=lambda p: p.name)
def test_changes_are_additive(path):
    current = ROOT / path.parent.name / path.name
    assert current.exists(), f"{path.name} removed; breaking changes need a new versioned file"
    assert _breaking(load(path), load(current)) == []


def test_baseline_covers_all_current_schemas():
    names = {(p.parent.name, p.name) for p in BASELINE.glob("*/*.schema.json")}
    assert {(p.parent.name, p.name) for p in CURRENT} <= names, "run tools/update_baseline.py for new schemas"


def test_breaking_detector_works():
    old = {"properties": {"a": {"type": "string"}}, "required": ["a"]}
    assert _breaking(old, {"properties": {}, "required": []})
    assert _breaking(old, {"properties": {"a": {"type": "integer"}}, "required": ["a"]})
    assert _breaking(old, {"properties": {"a": {"type": "string"}, "b": {"type": "string"}}, "required": ["a", "b"]})
    assert not _breaking(old, {"properties": {"a": {"type": "string"}, "b": {"type": "string"}}, "required": ["a"]})
