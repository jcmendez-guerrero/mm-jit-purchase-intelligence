"""T012: money fields are hidden from roles that may not see costs."""

from dashboard.roles import can_see_money, hide_money

PAYLOAD = {"day": "2026-11-09", "inventory_value": "92.00", "expiring_value": "60.00", "stockout_risk": 2}


def test_buyer_approver_and_admin_see_money():
    for role in ("buyer", "approver", "admin"):
        assert can_see_money({"viewer", role}) and hide_money(PAYLOAD, {role}) == PAYLOAD


def test_viewer_gets_counts_but_no_money_and_is_told_which_fields_are_hidden():
    out = hide_money(PAYLOAD, {"viewer"})
    assert "inventory_value" not in out and "expiring_value" not in out
    assert out["stockout_risk"] == 2 and out["hidden_by_role"] == ["inventory_value", "expiring_value"]


def test_no_roles_means_no_money():
    assert not can_see_money(set()) and "inventory_value" not in hide_money(PAYLOAD, set())
