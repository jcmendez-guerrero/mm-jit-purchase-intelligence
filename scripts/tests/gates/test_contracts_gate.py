"""T013: contracts gate against a throwaway contracts tree."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from conftest import write_json
from gates import contracts_gate as g

C = "packages/contracts"


def _entry(name="money", version=1, **kw):
    e = {"name": name, "kind": "dto", "version": version, "schema_path": f"dto/{name}.v{version}.schema.json",
         "owner": "svc", "consumers": [], "status": "frozen"}
    return {**e, **kw}


def _tree(tmp_path: Path, files: dict[str, dict], baseline: dict[str, dict] | None = None) -> Path:
    for rel, schema in files.items():
        write_json(tmp_path / C / rel, schema)
    for rel, schema in (baseline or {}).items():
        write_json(tmp_path / C / "baseline" / rel, schema)
    return tmp_path


def _matrix(*entries):
    return {"entries": list(entries)}


def test_matching_matrix_passes(tmp_path):
    root = _tree(tmp_path, {"dto/money.v1.schema.json": {"type": "object"}})
    assert g.check(root, _matrix(_entry())) == []


def test_schema_without_entry_fails(tmp_path):
    root = _tree(tmp_path, {"dto/money.v1.schema.json": {}})
    assert any("no matrix entry" in p for p in g.check(root, _matrix()))


def test_entry_without_file_fails(tmp_path):
    root = _tree(tmp_path, {})
    assert any("not found" in p for p in g.check(root, _matrix(_entry())))


def test_baseline_removed_property_fails_and_additive_passes(tmp_path):
    old = {"type": "object", "properties": {"a": {"type": "string"}}}
    root = _tree(tmp_path, {"dto/money.v1.schema.json": {"type": "object", "properties": {}}},
                 {"dto/money.v1.schema.json": old})
    assert any("removed" in p for p in g.check(root, _matrix(_entry())))
    new = {"type": "object", "properties": {"a": {"type": "string"}, "b": {"type": "string"}}}
    write_json(root / C / "dto/money.v1.schema.json", new)
    assert g.check(root, _matrix(_entry())) == []


def test_v2_with_deprecated_v1(tmp_path):
    root = _tree(tmp_path, {"dto/money.v1.schema.json": {}, "dto/money.v2.schema.json": {}})
    ok = _matrix(_entry(status="deprecated", superseded_by="money.v2", consumers=["a"]),
                 _entry(version=2, consumers=["a"]))
    assert g.check(root, ok) == []
    unmoved = _matrix(_entry(status="deprecated", superseded_by="money.v2", consumers=["a", "b"]),
                      _entry(version=2, consumers=["a"]))
    assert any("not on successor" in p for p in g.check(root, unmoved))
    missing = _matrix(_entry(status="deprecated", superseded_by="money.v3"), _entry(version=2))
    assert any("successor" in p for p in g.check(root, missing))


def _packaged_rule():
    """The rule `packages/contracts/tests/test_compat.py` enforces in the contracts package's own CI."""
    from conftest import REPO

    spec = importlib.util.spec_from_file_location("mmi_package_compat", REPO / "packages/contracts/tests/test_compat.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._breaking


BASE = {"type": "object", "required": ["a"], "properties": {"a": {"type": "string", "enum": ["x", "y"]}, "b": {"type": "integer"}}}
CHANGES = {
    "removed field": {**BASE, "properties": {"a": BASE["properties"]["a"]}},
    "retyped field": {**BASE, "properties": {**BASE["properties"], "b": {"type": "string"}}},
    "narrowed enum": {**BASE, "properties": {**BASE["properties"], "a": {"type": "string", "enum": ["x"]}}},
    "new required field": {**BASE, "required": ["a", "b"]},
    "added optional field": {**BASE, "properties": {**BASE["properties"], "c": {"type": "string"}}},
}


def test_the_gate_and_the_packages_own_compatibility_rule_agree():
    rule = _packaged_rule()
    for label, new in CHANGES.items():
        assert sorted(g.breaking(BASE, new)) == sorted(rule(BASE, new)), label
    assert g.breaking(BASE, CHANGES["added optional field"]) == []  # additive is allowed
    assert all(g.breaking(BASE, new) for label, new in CHANGES.items() if label != "added optional field")


# A required property added below the top level is just as breaking (PR 29 added `sku` to the required list of the lines of an array).
LINE = {"type": "object", "required": ["id"], "properties": {"id": {"type": "integer"}, "sku": {"type": ["string", "null"]}}}
HEAD = {"type": ["object", "null"], "required": ["id"], "properties": {"id": {"type": "integer"}, "sku": {"type": "string"}}}
NESTED_BASE = {"type": "object", "properties": {"lines": {"type": "array", "items": LINE}, "head": HEAD}}


def _nested(line=None, head=None):
    return {"type": "object", "properties": {"lines": {"type": "array", "items": {**LINE, **(line or {})}}, "head": {**HEAD, **(head or {})}}}


NESTED = {
    "required added to array items": (_nested(line={"required": ["id", "sku"]}), True),
    "required added to a nullable object": (_nested(head={"required": ["id", "sku"]}), True),
    "property removed from array items": (_nested(line={"properties": {"id": LINE["properties"]["id"]}}), True),
    "optional property added to array items": (_nested(line={"properties": {**LINE["properties"], "name": {"type": "string"}}}), False),
    "unchanged": (NESTED_BASE, False),
}


def test_a_required_property_added_below_the_top_level_is_breaking():
    rule = _packaged_rule()
    for label, (new, is_breaking) in NESTED.items():
        assert bool(g.breaking(NESTED_BASE, new)) is is_breaking, label
        assert sorted(g.breaking(NESTED_BASE, new)) == sorted(rule(NESTED_BASE, new)), label   # the package's own CI must say the same


OPENAPI = {"paths": {"/api/a": {"get": {}, "post": {}, "parameters": []}}}


def _ep(name):
    return {"name": name, "kind": "endpoint", "version": 1, "owner": "agent-00", "consumers": ["web"], "status": "draft"}


def test_endpoints_in_sync_pass():
    assert g.check_endpoints(_matrix(_ep("GET /api/a"), _ep("POST /api/a")), OPENAPI) == []


def test_new_gateway_endpoint_without_entry_fails():
    problems = g.check_endpoints(_matrix(_ep("POST /api/a")), OPENAPI)
    assert any("GET /api/a" in p and "no matrix entry" in p for p in problems)


def test_matrix_endpoint_that_left_the_gateway_fails():
    matrix = _matrix(_ep("GET /api/a"), _ep("POST /api/a"), _ep("PUT /api/z"))
    assert any("PUT /api/z" in p and "not in the gateway" in p for p in g.check_endpoints(matrix, OPENAPI))


def _svc(name="GET /forecasts/eligibility", **kw):
    return {"name": name, "kind": "service_endpoint", "version": 1, "owner": "forecast-service", "consumers": ["inventory-service"],
            "status": "draft", **kw}


def test_a_service_endpoint_needs_no_schema_file_and_is_not_compared_with_the_gateway(tmp_path):
    root = _tree(tmp_path, {"dto/money.v1.schema.json": {}})
    matrix = _matrix(_entry(), _ep("GET /api/a"), _ep("POST /api/a"), _svc())
    assert g.check(root, matrix) == []
    assert g.check_endpoints(matrix, OPENAPI) == []          # it is not a gateway route, so the gateway's OpenAPI does not list it


def test_a_service_endpoint_may_name_the_schema_it_answers_with_and_that_schema_must_exist(tmp_path):
    root = _tree(tmp_path, {"dto/money.v1.schema.json": {}})
    assert g.check(root, _matrix(_entry(), _svc(response="money.v1"))) == []
    assert any("money.v2" in p and "not in the matrix" in p for p in g.check(root, _matrix(_entry(), _svc(response="money.v2"))))


def test_run_checks_endpoints_only_when_openapi_is_supplied(tmp_path):
    root = _tree(tmp_path, {"dto/money.v1.schema.json": {}})
    path = root / "m.json"
    path.write_text(json.dumps(_matrix(_entry())))
    unchecked = g.run(root, path)
    assert unchecked.result == "pass" and any("endpoints not checked" in e for e in unchecked.evidence)
    checked = g.run(root, path, OPENAPI)
    assert checked.result == "fail" and any("no matrix entry" in e for e in checked.evidence)


def test_run_not_run_without_matrix(tmp_path):
    assert g.run(tmp_path).result == "not_run"


def test_run_reports_pass_and_fail(tmp_path):
    root = _tree(tmp_path, {"dto/money.v1.schema.json": {}})
    path = root / "m.json"
    path.write_text(json.dumps(_matrix(_entry())))
    assert g.run(root, path).result == "pass"
    path.write_text(json.dumps(_matrix()))
    assert g.run(root, path).result == "fail"
