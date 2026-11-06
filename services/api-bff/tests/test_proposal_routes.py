"""Proposal routes: the version the user reviewed travels with the action, only the right roles decide, and refusals are codes."""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from routes.api import get_procurement_client
from tests_support import headers_for

BUYER = ["viewer", "buyer"]
APPROVER = ["viewer", "approver"]


def call(method, path, headers, mock, **kw):
    from main import app

    app.dependency_overrides[get_procurement_client] = lambda: mock
    try:
        return TestClient(app).request(method, path, headers=headers, **kw)
    finally:
        app.dependency_overrides.clear()


def test_editing_a_line_forwards_the_body_the_user_and_the_version_reviewed(role_store):
    mock = AsyncMock()
    mock.edit_proposal_line.return_value = {"version": 4}
    res = call("PUT", "/api/proposals/p1/lines/l1", {**headers_for("buyer-1", BUYER), "If-Match": '"3"'}, mock, json={"qty": 12})
    assert res.status_code == 200
    kw = mock.edit_proposal_line.call_args.kwargs
    assert (kw["proposal_id"], kw["line_id"], kw["payload"], kw["user_id"], kw["if_match"]) == ("p1", "l1", {"qty": 12}, "buyer-1", '"3"')


def test_submitting_forwards_the_version_and_needs_the_buyer_role(role_store):
    mock = AsyncMock()
    mock.submit_proposal.return_value = {"status": "submitted"}
    assert call("POST", "/api/proposals/p1/submit", {**headers_for("buyer-1", BUYER), "If-Match": '"2"'}, mock).status_code == 200
    assert mock.submit_proposal.call_args.kwargs["if_match"] == '"2"'
    for roles in (["viewer"], ["viewer", "admin"], APPROVER):
        assert call("POST", "/api/proposals/p1/submit", headers_for("someone", roles), AsyncMock()).status_code == 403


def test_submission_is_refused_with_a_code_when_the_registry_has_fewer_than_two_approvers(role_store):
    role_store.replace_all({"buyer-1": ["viewer", "buyer"], "approver-1": ["viewer", "approver"]})
    mock = AsyncMock()
    res = call("POST", "/api/proposals/p1/submit", headers_for("buyer-1", BUYER), mock)
    assert res.status_code == 409 and res.json() == {"detail": "approval_fewer_than_two_approvers"}
    mock.submit_proposal.assert_not_called()


def test_only_an_approver_can_decide_not_even_an_admin(role_store):
    mock = AsyncMock()
    for roles in (["viewer", "admin"], BUYER, ["viewer"]):
        res = call("POST", "/api/proposals/p1/approve", headers_for("someone-9", roles), mock)
        assert res.status_code == 403 and res.json() == {"detail": "auth_forbidden_role"}
    mock.approve_proposal.assert_not_called()


def test_approval_needs_a_fresh_second_factor_and_forwards_the_version_reviewed(role_store):
    mock = AsyncMock()
    mock.approve_proposal.return_value = {"status": "approved"}
    stale = call("POST", "/api/proposals/p1/approve", {**headers_for("approver-1", APPROVER, mfa_age_seconds=1200), "If-Match": '"2"'}, mock)
    assert stale.status_code == 403 and stale.json() == {"detail": "auth_mfa_stale"}
    mock.approve_proposal.assert_not_called()
    ok = call("POST", "/api/proposals/p1/approve", {**headers_for("approver-1", APPROVER, mfa_age_seconds=30), "If-Match": '"2"'}, mock)
    assert ok.status_code == 200 and mock.approve_proposal.call_args.kwargs["if_match"] == '"2"'


def test_a_viewer_cannot_edit_a_line(role_store):
    mock = AsyncMock()
    assert call("PUT", "/api/proposals/p1/lines/l1", headers_for("viewer-1", ["viewer"]), mock, json={"qty": 1}).status_code == 403
    mock.edit_proposal_line.assert_not_called()


def test_the_downstream_call_uses_the_method_procurement_exposes_for_line_edits():
    """Procurement serves PATCH for line edits; a PUT there would 405 in the real stack."""
    import inspect

    from clients.procurement import ProcurementClient

    src = inspect.getsource(ProcurementClient.edit_proposal_line)
    assert "self.patch(" in src and "self.put(" not in src
