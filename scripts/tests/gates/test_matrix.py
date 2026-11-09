"""T049: gateway endpoints become matrix entries and survive regeneration."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from conftest import REPO
from gates import matrix as m

OPENAPI = {"paths": {"/api/b": {"post": {}, "get": {}, "parameters": []}, "/api/a": {"put": {}}}}


def test_endpoint_entries_are_sorted_http_methods_only():
    entries = m.endpoint_entries(OPENAPI)
    assert [e["name"] for e in entries] == ["PUT /api/a", "GET /api/b", "POST /api/b"]
    assert all(e["kind"] == "endpoint" and e["owner"] == "agent-00" and e["status"] == "draft" for e in entries)


def test_regeneration_keeps_existing_endpoints_and_refresh_replaces_them(tmp_path: Path):
    (tmp_path / "packages/contracts/dto").mkdir(parents=True)
    path = m.write(tmp_path, OPENAPI)
    assert {e["name"] for e in json.loads(path.read_text())["entries"]} == {"PUT /api/a", "GET /api/b", "POST /api/b"}
    again = m.write(tmp_path)  # no openapi: endpoints are kept
    assert len(json.loads(again.read_text())["entries"]) == 3
    refreshed = m.write(tmp_path, {"paths": {"/api/c": {"get": {}}}})
    assert [e["name"] for e in json.loads(refreshed.read_text())["entries"]] == ["GET /api/c"]


def test_regeneration_keeps_a_curated_owner_and_status_but_new_schemas_get_the_heuristic(tmp_path: Path):
    dto = tmp_path / "packages/contracts/dto"
    dto.mkdir(parents=True)
    (dto / "money.v1.schema.json").write_text("{}")
    path = m.write(tmp_path)
    doc = json.loads(path.read_text())
    assert doc["entries"][0]["owner"] == "agent-00"  # heuristic fallback for an unclaimed schema
    doc["entries"][0].update(owner="procurement-service", status="deprecated", superseded_by="money.v2")
    path.write_text(json.dumps(doc))
    (dto / "fresh.v1.schema.json").write_text("{}")
    again = {e["name"]: e for e in json.loads(m.write(tmp_path).read_text())["entries"]}
    assert again["money"]["owner"] == "procurement-service" and again["money"]["status"] == "deprecated"
    assert again["money"]["superseded_by"] == "money.v2"
    assert again["fresh"]["owner"] == "agent-00" and again["fresh"]["status"] == "frozen"


def test_endpoint_entries_validate_against_the_matrix_schema():
    schema = json.loads((REPO / "docs/architecture/integration/schemas/contract-matrix.schema.json").read_text())
    doc = {"matrix_version": 1, "generated_at": "2026-11-09T00:00:00Z", "schema_ownership": {}, "entries": m.endpoint_entries(OPENAPI)}
    jsonschema.validate(doc, schema)
