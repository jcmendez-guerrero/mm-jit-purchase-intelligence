"""T044 (FR-027, constitution Principle I): the sensitive ERP-cost operations, the buyer's release and the admin's override, need a second factor
authenticated within five minutes. A stale one is refused (and audited) before anything downstream is called, until the user confirms again.
"""

from unittest.mock import AsyncMock

import pytest
from test_cost_routes import BUYER, call
from tests_support import headers_for

OVERRIDE_BODY = {"value": "2.50", "reason": "Proveedor con tarifa pactada"}

OPERATIONS = [
    pytest.param("/api/cost-writes/w1/approve", BUYER, "approve_cost_write", {}, id="release by a buyer"),
    pytest.param("/api/cost-writes/w1/override", ["viewer", "admin"], "override_cost_write", OVERRIDE_BODY, id="override by an admin"),
]


def mock_for(method):
    mock = AsyncMock()
    getattr(mock, method).return_value = {"status": "ok"}
    return mock


@pytest.mark.parametrize(("path", "roles", "method", "body"), OPERATIONS)
def test_a_second_factor_older_than_five_minutes_is_refused_before_anything_downstream_runs(role_store, path, roles, method, body):
    mock = mock_for(method)
    refused = call("POST", path, headers_for("user-1", roles, mfa_age_seconds=301), mock, json=body)
    assert refused.status_code == 403 and refused.json() == {"detail": "auth_mfa_stale"}
    getattr(mock, method).assert_not_called()


@pytest.mark.parametrize(("path", "roles", "method", "body"), OPERATIONS)
def test_a_second_factor_just_inside_five_minutes_is_accepted(role_store, path, roles, method, body):
    mock = mock_for(method)
    assert call("POST", path, headers_for("user-1", roles, mfa_age_seconds=299), mock, json=body).status_code == 200
    getattr(mock, method).assert_called_once()


@pytest.mark.parametrize(("path", "roles", "method", "body"), OPERATIONS)
def test_after_confirming_again_the_same_user_can_proceed(role_store, path, roles, method, body):
    mock = mock_for(method)
    assert call("POST", path, headers_for("user-1", roles, mfa_age_seconds=1200), mock, json=body).status_code == 403
    assert call("POST", path, headers_for("user-1", roles, mfa_age_seconds=5), mock, json=body).status_code == 200


@pytest.mark.parametrize(("path", "roles", "method", "body"), OPERATIONS)
def test_the_stale_attempt_is_audited_with_the_user_and_the_path(role_store, path, roles, method, body):
    call("POST", path, headers_for("user-9", roles, mfa_age_seconds=900), mock_for(method), json=body)
    refusals = [e for e in role_store.audit_view() if e["action"] == "access.refused" and e["actor"] == "user-9"]
    assert refusals and path in refusals[-1]["target_user"]


def test_the_wrong_role_is_still_refused_as_a_role_problem_when_the_factor_is_fresh(role_store):
    mock = mock_for("override_cost_write")
    wrong = call("POST", "/api/cost-writes/w1/override", headers_for("buyer-1", BUYER, mfa_age_seconds=5), mock, json=OVERRIDE_BODY)
    assert wrong.status_code == 403 and wrong.json() == {"detail": "auth_forbidden_role"}
    mock.override_cost_write.assert_not_called()
