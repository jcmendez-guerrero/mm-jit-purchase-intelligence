"""T078: recommended versus effective safety stock and the override flow."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from builders import linear_forecast, offer, variant
from db.tables import audit_events
from mmi_common.auth import Principal
from policies.overrides import OverrideRequestError, decide, effective_overrides, queue, request_override, revert
from proposals.model import VariantInput
from proposals.targets import compute_target
from sqlalchemy import select

NOW = datetime(2026, 11, 9, 9, tzinfo=UTC)


def who(name, roles=("approver",)):
    return Principal(name, frozenset(roles), NOW)


def ask(conn, value=5, field="safety_stock", recommended=2, actor="buyer-1", reason="proveedor poco fiable"):
    return request_override(conn, 7, field, value, reason, actor, recommended, NOW)


def test_a_request_is_pending_and_changes_nothing_until_approved(conn):
    r = ask(conn)
    assert r.status == "pending" and effective_overrides(conn) == {} and [x.id for x in queue(conn)] == [r.id]


def test_validation_and_one_pending_request_per_field(conn):
    for kw in ({"value": -1}, {"field": "units"}, {"reason": ""}, {"reason": "no"}):
        with pytest.raises(OverrideRequestError):
            ask(conn, **kw)
    ask(conn)
    with pytest.raises(OverrideRequestError) as e:
        ask(conn, value=6)
    assert e.value.code == "policy_override_pending"
    ask(conn, field="max", value=20)                                                       # another field is fine


def test_only_a_different_approver_decides_with_no_extra_second_factor(conn):
    r = ask(conn)
    with pytest.raises(OverrideRequestError) as e:
        decide(conn, r.id, who("buyer-2", ("buyer",)), True, 2, NOW)
    assert e.value.code == "not_an_approver"
    with pytest.raises(OverrideRequestError) as e2:
        decide(conn, r.id, who("buyer-1", ("buyer", "approver")), True, 2, NOW)
    assert e2.value.code == "policy_override_self_approval"
    ok = decide(conn, r.id, Principal("approver-1", frozenset({"approver"}), None), True, 2, NOW)       # no auth_time: MFA is not needed
    assert ok.status == "approved" and ok.decided_by == "approver-1" and effective_overrides(conn) == {(7, "safety_stock"): 5}


def test_rejection_keeps_the_recommendation(conn):
    r = ask(conn)
    assert decide(conn, r.id, who("approver-1"), False, 2, NOW).status == "rejected"
    assert effective_overrides(conn) == {}
    with pytest.raises(OverrideRequestError) as e:
        decide(conn, r.id, who("approver-2"), True, 2, NOW)
    assert e.value.code == "policy_override_not_pending"


def test_a_stale_recommendation_is_flagged_at_decision_time(conn):
    r = ask(conn, recommended=2)
    assert decide(conn, r.id, who("approver-1"), True, 4, NOW).recommendation_changed is True
    r2 = ask(conn, field="min", value=3, recommended=2)
    assert decide(conn, r2.id, who("approver-1"), True, 2, NOW).recommendation_changed is False


def test_an_approved_override_can_be_reverted_and_the_effective_value_falls_back(conn):
    r = ask(conn)
    decide(conn, r.id, who("approver-1"), True, 2, NOW)
    assert revert(conn, r.id, who("buyer-1", ("buyer",)), NOW).status == "reverted"          # the requester may withdraw it
    assert effective_overrides(conn) == {}


def test_every_step_is_audited(conn):
    r = ask(conn)
    decide(conn, r.id, who("approver-1"), True, 2, NOW)
    actions = [a.action for a in conn.execute(select(audit_events).where(audit_events.c.entity == "policy_override")).all()]
    assert actions == ["policy_override.requested", "policy_override.approved"]


def test_the_effective_safety_stock_changes_the_target_not_the_recommendation():
    v = variant(1, [offer("s", "1.00")], linear_forecast(1.0))
    base = compute_target(v, 3)
    assert base.safety_stock is not None
    over = compute_target(VariantInput(**{**v.__dict__, "safety_override": 10}), 3)
    assert Decimal(over.order_up_to) > Decimal(base.order_up_to)
    low = compute_target(VariantInput(**{**v.__dict__, "safety_override": 0}), 3)
    assert low.order_up_to < base.order_up_to


def test_a_pending_request_is_flagged_when_the_recommendation_has_moved_since_it_was_made(conn):
    from policies.overrides import drift

    r = ask(conn, recommended=2)
    assert drift(conn, r, lambda c, v: 2) == (False, 2)                       # unchanged: no flag
    assert drift(conn, r, lambda c, v: 4) == (True, 4)                        # moved: flagged, with the new value
    assert drift(conn, r, lambda c, v: None) == (False, None)                 # never proposed again: nothing to compare with


def test_only_pending_safety_stock_requests_are_compared(conn):
    from policies.overrides import drift

    mx = ask(conn, field="max", value=20, recommended=None)
    assert drift(conn, mx, lambda c, v: 9) == (False, None)                    # min and max have no engine recommendation
    done = decide(conn, ask(conn).id, who("approver-1"), True, 2, NOW)
    assert drift(conn, done, lambda c, v: 9) == (bool(done.recommendation_changed), None)   # a decided request keeps what was recorded at the decision


def test_the_pending_list_carries_the_flag_and_the_current_recommendation(conn, monkeypatch):
    import api.policies as api_policies

    ask(conn, recommended=2)
    monkeypatch.setattr(api_policies, "recommended_safety_stock", lambda c, v: 5)
    (row,) = [api_policies.override_json(conn, r) for r in queue(conn)]
    assert row["recommended_value"] == 2 and row["current_recommended"] == 5 and row["recommendation_changed"] is True


def test_the_effective_values_say_whether_they_are_the_recommendation_or_an_approved_override(conn):
    from policies.overrides import effective_for_variant

    none = effective_for_variant(conn, 7, None)
    assert none["safety_stock"] == {"value": None, "source": "none", "request_id": None}
    rec = effective_for_variant(conn, 7, 2)
    assert rec["safety_stock"] == {"value": 2, "source": "recommendation", "request_id": None}
    pending = ask(conn, value=5)
    assert effective_for_variant(conn, 7, 2)["safety_stock"]["source"] == "recommendation"                 # a pending request changes nothing
    decide(conn, pending.id, who("approver-1"), True, 2, NOW)
    eff = effective_for_variant(conn, 7, 2)["safety_stock"]
    assert eff == {"value": 5, "source": "approved_override", "request_id": pending.id}
    revert(conn, pending.id, who("approver-1"))
    assert effective_for_variant(conn, 7, 2)["safety_stock"] == {"value": 2, "source": "recommendation", "request_id": None}


def test_min_and_max_show_their_approved_override_or_nothing(conn):
    from policies.overrides import effective_for_variant

    req = ask(conn, field="min", value=3, recommended=None)
    decide(conn, req.id, who("approver-1"), True, None, NOW)
    eff = effective_for_variant(conn, 7, 2)
    assert eff["min"] == {"value": 3, "source": "approved_override", "request_id": req.id}
    assert eff["max"] == {"value": None, "source": "none", "request_id": None}


def test_the_newest_approved_override_wins_and_other_variants_are_untouched(conn):
    from policies.overrides import effective_for_variant

    first = ask(conn, value=4)
    decide(conn, first.id, who("approver-1"), True, 2, NOW)
    revert(conn, first.id, who("approver-1"))
    second = ask(conn, value=9)
    decide(conn, second.id, who("approver-1"), True, 2, NOW)
    assert effective_for_variant(conn, 7, 2)["safety_stock"]["value"] == 9
    assert effective_for_variant(conn, 8, 2)["safety_stock"] == {"value": 2, "source": "recommendation", "request_id": None}
