"""The scenario routes: roles, Idempotency-Key, promotion and export over HTTP."""

from datetime import UTC, datetime, timedelta

import pytest
from api import costs, scenarios
from conftest import add_supplier
from db.tables import product_refs
from db.tables import scenarios as scenarios_table
from fastapi.testclient import TestClient
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app
from scen import Blob, base
from sqlalchemy import insert, select

ROLES = {"buyer": {"viewer", "buyer"}, "viewer": {"viewer"}}


class V:
    def validate(self, token, required_roles=()):
        roles = ROLES.get(token)
        if roles is None or not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        return Principal(f"user-{token}", frozenset(roles), datetime.now(UTC) - timedelta(minutes=1))


class Provider:
    def __init__(self, sa, sb):
        self.sa, self.sb = sa, sb

    def build(self, conn, today):
        return base(self.sa, self.sb)


def h(role="buyer", **extra):
    return {"Authorization": f"Bearer {role}", **extra}


@pytest.fixture
def api(engine, tmp_path):
    with engine.begin() as c:
        sa, sb = add_supplier(c, 1, "Proveedor A"), add_supplier(c, 2, "Proveedor B")
    app = create_service_app("procurement-service", validator=V())
    app.include_router(costs.build_router(app))
    app.include_router(scenarios.build_router(app))
    app.state.inputs_provider, app.state.blob_writer = Provider(sa, sb), Blob(tmp_path)
    app.dependency_overrides[costs.get_engine] = lambda: engine
    c = TestClient(app)
    c.sa = sa
    return c


def body(sa):
    return {"name": "Sin A", "disabled_suppliers": [sa]}


def test_creating_needs_the_buyer_role_and_an_idempotency_key_and_validates_the_input(api):
    assert api.post("/scenarios", json=body(api.sa), headers=h("viewer", **{"Idempotency-Key": "abcdefgh1"})).status_code == 403
    assert api.post("/scenarios", json=body(api.sa), headers=h()).json()["detail"] == "idempotency_key_required"
    assert api.post("/scenarios", json={"name": "x", "budget": "-5"}, headers=h(**{"Idempotency-Key": "abcdefgh2"})).status_code == 422
    assert api.post("/scenarios", json={"name": "", "disabled_suppliers": []}, headers=h(**{"Idempotency-Key": "abcdefgh3"})).status_code == 422


def test_the_same_key_returns_the_same_scenario_and_it_can_be_listed_and_read(api):
    one = api.post("/scenarios", json=body(api.sa), headers=h(**{"Idempotency-Key": "key-repeat-1"}))
    two = api.post("/scenarios", json=body(api.sa), headers=h(**{"Idempotency-Key": "key-repeat-1"}))
    assert one.status_code == 201 and two.json()["id"] == one.json()["id"]
    sid = one.json()["id"]
    assert api.get(f"/scenarios/{sid}", headers=h("viewer")).json()["status"] == "ready"
    assert [s["id"] for s in api.get("/scenarios", headers=h("viewer")).json()["scenarios"]] == [sid]
    assert api.get("/scenarios/nope", headers=h("viewer")).json()["detail"] == "unknown_scenario" and api.get("/scenarios").status_code == 401


def test_promotion_is_buyer_only_creates_a_draft_and_cannot_repeat(api):
    sid = api.post("/scenarios", json=body(api.sa), headers=h(**{"Idempotency-Key": "key-promote-1"})).json()["id"]
    assert api.post(f"/scenarios/{sid}/promote", headers=h("viewer")).status_code == 403
    r = api.post(f"/scenarios/{sid}/promote", json={"week": "2026-W46"}, headers=h())
    assert r.status_code == 201 and r.json()["week"] == "2026-W46" and r.json()["proposal_id"]
    assert api.post(f"/scenarios/{sid}/promote", headers=h()).json()["detail"] == "scenario_already_promoted"
    assert api.post("/scenarios/nope/promote", headers=h()).status_code == 404
    assert api.post(f"/scenarios/{sid}/promote", json={"week": "x"}, headers=h()).status_code == 422


def test_export_returns_the_chosen_format_and_refuses_others(api):
    sid = api.post("/scenarios", json=body(api.sa), headers=h(**{"Idempotency-Key": "key-export-1"})).json()["id"]
    csv = api.get(f"/scenarios/{sid}/export?format=csv", headers=h("buyer"))
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv") and "escenario.csv" in csv.headers["content-disposition"]
    assert api.get(f"/scenarios/{sid}/export?format=xlsx", headers=h("buyer")).status_code == 200
    assert api.get(f"/scenarios/{sid}/export?format=pdf", headers=h("buyer")).status_code == 422
    assert api.get("/scenarios/nope/export?format=csv", headers=h("buyer")).status_code == 404

    assert api.get(f"/scenarios/{sid}/export?format=csv", headers=h("viewer")).status_code == 403      # T027: a viewer cannot export (FR-010)

def _ref(engine, variant_id, sku):
    with engine.begin() as c:
        c.execute(insert(product_refs).values(variant_id=variant_id, product_id=variant_id, sku=sku, name="Producto sintético"))


def _lines_and_changes(doc):
    return [ln for r in doc["results"] for ln in r["lines"]], doc["summary"]["changes"]


def test_changes_and_lines_carry_the_catalogue_sku_and_null_when_it_cannot_be_resolved(api, engine):
    _ref(engine, 1, "SYN-0001")
    _ref(engine, 2, "  ")                                                                    # a blank SKU is unresolved, never shown as blank
    # variant 3 has no catalogue row at all
    doc = api.post("/scenarios", json=body(api.sa), headers=h(**{"Idempotency-Key": "key-sku-0001"})).json()
    lines, changes = _lines_and_changes(api.get(f"/scenarios/{doc['id']}", headers=h("viewer")).json())
    assert changes and lines
    for x in (*changes, *lines):
        assert "sku" in x and "variant_id" in x                                              # additive: the id stays for API use
        assert x["sku"] == {1: "SYN-0001", 2: None, 3: None}[x["variant_id"]]
    assert {c["variant_id"] for c in changes} == {1, 2, 3} and {ln["variant_id"] for ln in lines} == {1, 2, 3}      # nothing is dropped when a SKU is missing


def test_a_scenario_stored_before_the_sku_existed_gets_it_on_read_without_changing_its_hash_or_totals(api, engine):
    sid = api.post("/scenarios", json=body(api.sa), headers=h(**{"Idempotency-Key": "key-sku-0002"})).json()["id"]
    before = api.get(f"/scenarios/{sid}", headers=h("viewer")).json()
    with engine.begin() as c:
        stored = c.execute(select(scenarios_table.c.summary)).scalar()
    assert all("sku" not in ch for ch in stored["changes"])                                   # the SKU is never persisted
    _ref(engine, 1, "SYN-0001")
    after = api.get(f"/scenarios/{sid}", headers=h("viewer")).json()
    assert before["result_hash"] == after["result_hash"] and before["status"] == after["status"] == "ready"
    assert [r["order_total"] for r in before["results"]] == [r["order_total"] for r in after["results"]]
    strip = lambda d: [{k: v for k, v in x.items() if k not in ("sku", "name")} for x in d]            # noqa: E731
    assert strip(before["summary"]["changes"]) == strip(after["summary"]["changes"])
    assert next(c["sku"] for c in after["summary"]["changes"] if c["variant_id"] == 1) == "SYN-0001"
    assert next(c["sku"] for c in before["summary"]["changes"] if c["variant_id"] == 1) is None


def test_a_surrogate_id_from_a_local_load_resolves_to_its_sku_like_any_other(api, engine):
    from policies.service import product_labels

    _ref(engine, 9_000_001, "SYN-9001")
    with engine.begin() as c:
        assert product_labels(c, [9_000_001])[9_000_001]["sku"] == "SYN-9001"


def test_an_infeasible_scenario_still_carries_a_sku_on_every_change_and_line(api, engine):
    _ref(engine, 1, "SYN-0001")
    doc = api.post("/scenarios", json={"name": "Presupuesto mínimo", "budget": "1"}, headers=h(**{"Idempotency-Key": "key-sku-0003"})).json()
    got = api.get(f"/scenarios/{doc['id']}", headers=h("viewer")).json()
    assert got["summary"]["infeasible"] is not None                                          # the budget cannot be met
    lines, changes = _lines_and_changes(got)
    assert lines and all("sku" in x for x in (*changes, *lines))
    assert {x["sku"] for x in lines if x["variant_id"] == 1} == {"SYN-0001"}


def test_each_change_and_line_also_carries_the_product_name_so_rows_without_a_sku_can_be_told_apart(api, engine):
    _ref(engine, 1, "SYN-0001")
    _ref(engine, 2, None)
    doc = api.post("/scenarios", json=body(api.sa), headers=h(**{"Idempotency-Key": "key-sku-0004"})).json()
    lines, changes = _lines_and_changes(api.get(f"/scenarios/{doc['id']}", headers=h("viewer")).json())
    for x in (*changes, *lines):
        assert x["name"] == ("Producto sintético" if x["variant_id"] in (1, 2) else None)      # variant 3 has no catalogue row
    assert [x["sku"] for x in lines if x["variant_id"] == 2] == [None]


def test_the_critical_products_of_an_infeasible_scenario_are_listed_by_sku_in_the_same_order(engine):
    from scenarios.store import _with_skus

    _ref(engine, 1, "SYN-0001")
    _ref(engine, 3, "SYN-0003")
    summary = {"changes": [], "infeasible": {"over_by": "5.00", "clinical_critical_variants": [1, 2, 3]}}
    with engine.begin() as c:
        out = _with_skus(c, summary, [])
    assert out["infeasible"]["clinical_critical_skus"] == ["SYN-0001", None, "SYN-0003"]          # an unknown product stays in the list as null
    assert out["infeasible"]["clinical_critical_variants"] == [1, 2, 3] and "clinical_critical_skus" not in summary["infeasible"]      # the stored summary is not touched


def test_the_real_scenario_response_matches_the_shared_scenario_schema(api, engine):
    """The summary of GET /scenarios/{id} is the contract's `summary` (changes and infeasible); every change names its SKU, even when it is null."""
    import json
    from pathlib import Path

    from jsonschema import Draft202012Validator

    schema = json.loads((Path(__file__).resolve().parents[3] / "packages/contracts/dto/scenario.v1.schema.json").read_text())
    _ref(engine, 1, "SYN-0001")
    validator = Draft202012Validator(schema["properties"]["summary"])
    moved = api.post("/scenarios", json=body(api.sa), headers=h(**{"Idempotency-Key": "key-sku-0005"})).json()
    tight = api.post("/scenarios", json={"name": "Presupuesto mínimo", "budget": "1"}, headers=h(**{"Idempotency-Key": "key-sku-0006"})).json()
    for sid in (moved["id"], tight["id"]):
        assert not list(validator.iter_errors(api.get(f"/scenarios/{sid}", headers=h("viewer")).json()["summary"]))
    got = api.get(f"/scenarios/{moved['id']}", headers=h("viewer")).json()["summary"]
    assert got["changes"] and any(c["sku"] == "SYN-0001" for c in got["changes"])               # the check ran on real changes, not an empty list
    assert api.get(f"/scenarios/{tight['id']}", headers=h("viewer")).json()["summary"]["infeasible"]["clinical_critical_skus"] == []
    item = schema["properties"]["summary"]["properties"]["changes"]["items"]
    assert "sku" in item["properties"] and "sku" not in item["required"]       # ADR-021: only added optional properties in v1; the service still always sends it
