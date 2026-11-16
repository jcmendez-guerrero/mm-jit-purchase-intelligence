"""The proposal detail response validates against the shared schema (AGENTS.md rule 9, Agent 00 finding 1)."""

import json
from pathlib import Path

import jsonschema
from proposal_support import generate, h

SCHEMA = json.loads((Path(__file__).resolve().parents[3] / "packages/contracts/dto/proposal_detail.v1.schema.json").read_text())


def test_a_generated_proposal_matches_the_schema(api):
    client, _ = api
    pid = generate(client)
    body = client.get(f"/proposals/{pid}", headers=h("buyer")).json()
    jsonschema.Draft202012Validator(SCHEMA).validate(body)
    assert body["review_notes"] == []


def test_schema_rejects_an_unknown_property(api):
    client, _ = api
    pid = generate(client)
    body = client.get(f"/proposals/{pid}", headers=h("buyer")).json()
    body["surprise"] = 1
    assert not jsonschema.Draft202012Validator(SCHEMA).is_valid(body)
