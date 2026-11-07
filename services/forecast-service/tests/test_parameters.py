"""T081: forecast parameters accept only approved keys and ranges and are versioned."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app
from parameters import (
    APPROVED,
    ParameterConflict,
    ParameterError,
    config_from_parameters,
    effective,
    listing,
    save_parameter,
)

TODAY = date(2026, 11, 9)


def test_only_approved_keys_and_ranges(conn):
    with pytest.raises(ParameterError) as e:
        save_parameter(conn, "random_seed", 1, "b", today=TODAY)
    assert e.value.code == "unknown_parameter"
    for key, value in (("lead_time", 0), ("lead_time", 61), ("lead_time", "7.5"), ("lead_time", "abc"), ("backtest.min_gain", "0.6"), ("backtest.max_censored_share", "-0.1"),
                       ("backtest.min_windows", 0), ("lead_time", "NaN")):
        with pytest.raises(ParameterError):
            save_parameter(conn, key, value, "b", today=TODAY)
    with pytest.raises(ParameterError):
        save_parameter(conn, "lead_time", 7.0, "b", today=TODAY)                      # floats are refused
    assert save_parameter(conn, "lead_time", 10, "b", today=TODAY) == 1
    assert save_parameter(conn, "backtest.min_gain", "0.10", "b", today=TODAY) == 1


def test_revisions_conflicts_and_effective_dating(conn):
    save_parameter(conn, "lead_time", 10, "b", today=TODAY)
    save_parameter(conn, "lead_time", 14, "b", expected_revision=1, valid_from=TODAY + timedelta(days=7), today=TODAY)
    with pytest.raises(ParameterConflict) as e:
        save_parameter(conn, "lead_time", 12, "b", expected_revision=1, today=TODAY)
    assert e.value.current_revision == 2
    with pytest.raises(ParameterError):
        save_parameter(conn, "lead_time", 12, "b", valid_from=TODAY - timedelta(days=1), today=TODAY)
    assert effective(conn, TODAY)[0]["lead_time"] == 10 and effective(conn, TODAY + timedelta(days=7))[0]["lead_time"] == 14
    assert effective(conn, TODAY)[1] == {"lead_time": 1} and effective(conn, TODAY + timedelta(days=7))[1] == {"lead_time": 2}


def test_defaults_apply_when_nothing_is_set_and_build_the_run_configuration(conn):
    values, revisions = effective(conn, TODAY)
    assert revisions == {} and values["lead_time"] == APPROVED["lead_time"].default
    save_parameter(conn, "backtest.min_history", 90, "b", today=TODAY)
    cfg, versions = config_from_parameters(conn, TODAY)
    assert cfg.backtest.min_history == 90 and cfg.lead_time == 7 and versions == {"backtest.min_history": 1}
    assert {p["key"] for p in listing(conn, TODAY)} == set(APPROVED)


class V:
    def validate(self, token, required_roles=()):
        roles = {"viewer", "buyer"} if token == "buyer" else {"viewer"}  # noqa: S105 - test token name
        if not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        return Principal(f"user-{token}", frozenset(roles), None)


@pytest.fixture
def api(engine):
    from api import build_router, get_engine

    app = create_service_app("forecast-service", validator=V())
    app.include_router(build_router(app))
    app.dependency_overrides[get_engine] = lambda: engine
    return TestClient(app)


def h(role, **extra):
    return {"Authorization": f"Bearer {role}", **extra}


def test_http_flow_roles_if_match_and_codes(api):
    assert api.put("/parameters/lead_time", json={"value": "9"}, headers=h("viewer")).status_code == 403
    assert api.put("/parameters/lead_time", json={"value": "9"}, headers=h("buyer")).json() == {"key": "lead_time", "revision": 1}
    assert api.put("/parameters/lead_time", json={"value": "10"}, headers=h("buyer")).status_code == 428
    stale = api.put("/parameters/lead_time", json={"value": "10"}, headers=h("buyer", **{"If-Match": '"0"'}))
    assert stale.status_code == 412 and stale.json() == {"detail": "revision_conflict", "current_version": 1}
    assert api.put("/parameters/lead_time", json={"value": "99"}, headers=h("buyer", **{"If-Match": '"1"'})).json()["detail"] == "policy_out_of_range"
    assert api.put("/parameters/seed", json={"value": "1"}, headers=h("buyer")).json()["detail"] == "unknown_parameter"
    rows = {p["key"]: p for p in api.get("/parameters", headers=h("viewer")).json()["parameters"]}
    assert rows["lead_time"]["value"] == "9" and Decimal(rows["lead_time"]["default"]) == 7


def test_a_run_cannot_be_requested_without_its_wiring_and_viewers_cannot_request(api):
    assert api.post("/runs", headers=h("viewer")).status_code == 403
    assert api.post("/runs", headers=h("buyer")).status_code == 503
