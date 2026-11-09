"""T086 (Constitution IV): the real drill-down payload, from the function and from the route, validates against DrillPage in the v2 contract.

The schema is still a draft under specs/; T005 moves it to packages/contracts/dto, and SCHEMA below changes with it.
"""

import copy
import json
from pathlib import Path

import jsonschema
import pytest
from conftest import auth
from dashboard.drilldown import drilldown
from dashboard.kpis import Filters
from reference_dataset import TODAY, seed_reference

SCHEMA = Path(__file__).resolve().parents[3] / "specs" / "006-executive-dashboard-analytics" / "contracts" / "dashboard_indicators.v2.schema.json"
KINDS = [("inventory_value", {}), ("coverage", {}), ("stockout_risk", {}), ("expiry_risk", {}), ("abc_xyz", {"abc": "A", "xyz": "X"}), ("trend_day", {"day": "2026-11-08"})]


def check(payload):
    defs = json.loads(SCHEMA.read_text(encoding="utf-8"))["$defs"]
    jsonschema.validate(payload, {"$ref": "#/$defs/DrillPage", "$defs": defs})


@pytest.mark.parametrize("kind,extra", KINDS)
def test_every_drilldown_kind_matches_the_contract(engine, kind, extra):
    seed_reference(engine)
    with engine.connect() as c:
        check(drilldown(c, kind, TODAY, Filters(), **extra))


def test_a_sorted_and_paged_payload_matches_the_contract(engine):
    seed_reference(engine)
    with engine.connect() as c:
        check(drilldown(c, "inventory_value", TODAY, Filters(), limit=2, offset=2, sort="name", order="desc"))


def test_the_route_payload_matches_the_contract(client, engine):
    seed_reference(engine)
    res = client.get("/dashboard/drilldown?kind=inventory_value&limit=2&sort=sku", headers=auth("buyer"))
    assert res.status_code == 200
    check(res.json())


def test_the_contract_really_rejects_a_payload_that_drifts(engine):
    seed_reference(engine)
    with engine.connect() as c:
        good = drilldown(c, "inventory_value", TODAY, Filters())
    for mutate in (lambda p: p.pop("sum"), lambda p: p["rows"][0].__setitem__("contribution", "1"), lambda p: p["rows"][0].pop("sku"), lambda p: p.__setitem__("offset", -1)):
        bad = copy.deepcopy(good)
        mutate(bad)
        with pytest.raises(jsonschema.ValidationError):
            check(bad)
