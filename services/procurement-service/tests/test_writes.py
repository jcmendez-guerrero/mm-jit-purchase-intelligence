"""T100 / T140: cost write requests, buyer release with fresh MFA, pending_link, outcomes, forged messages."""

from datetime import timedelta
from decimal import Decimal

import pytest
from audit.chain import verify_chain
from conftest import NOW, add_product, add_supplier
from costs.recargo import RecargoTable
from costs.rules import CostRules
from costs.siweb_import import import_supplier_rows
from costs.store import NewCost, add_version
from costs.writes import (
    WriteError,
    apply_outcome,
    approve_write,
    cancel_write,
    list_visible,
    request_write,
    writer_view,
)
from db.tables import cost_write_requests, erp_supplier_links, outbox
from mmi_common.auth import Principal
from sqlalchemy import insert, select

D = Decimal
R = CostRules()


class Blob:
    def __init__(self, tmp):
        self.tmp = tmp

    def put(self, name, data):
        p = self.tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p.as_uri()


@pytest.fixture
def blob(tmp_path):
    return Blob(tmp_path)


def buyer(subject="buyer-1", age=1, roles=("buyer",)):
    return Principal(subject, frozenset(roles), None if age is None else NOW - timedelta(minutes=age))


def link(conn, sid, has_cost, product=1):
    conn.execute(insert(erp_supplier_links).values(product_id=product, supplier_id=sid, has_cost=has_cost, last_seen_at=NOW))


def manual(conn, sid, value="10.52", product=1, variant=None):
    return add_version(conn, NewCost(product_id=product, supplier_id=sid, cost_with_recargo=D(value), source="manual", actor="buyer-1", variant_id=variant), R, NOW)


def test_missing_cost_case_creates_a_reviewable_request(conn):
    sid = add_supplier(conn)
    link(conn, sid, has_cost=False)
    res = request_write(conn, manual(conn, sid).id, "missing_cost", "buyer-1", NOW)
    r = res.request
    assert res.status == "pending_review" and r.attempts == 0 and r.previous_siweb_value is None and D(str(r.proposed_value)) == D("10.52")
    assert [x.id for x in list_visible(conn)] == [r.id]


def test_no_erp_record_parks_the_request_as_pending_link_and_nothing_can_be_sent(conn, blob):
    sid = add_supplier(conn)
    res = request_write(conn, manual(conn, sid).id, "missing_cost", "buyer-1", NOW)
    assert res.status == "pending_link"
    with pytest.raises(WriteError) as e:
        approve_write(conn, res.request.id, buyer(), blob, now=NOW)
    assert e.value.code == "pending_link" and conn.execute(select(outbox)).all() == [] and writer_view(conn, res.request.id) is None


def test_the_request_becomes_releasable_once_the_erp_link_appears_and_the_buyer_re_releases(conn, blob):
    sid = add_supplier(conn, 9)
    res = request_write(conn, manual(conn, sid).id, "missing_cost", "buyer-1", NOW)
    assert res.status == "pending_link"
    import_supplier_rows(conn, [{"product_id": 1, "contact_id": 9, "supplier_name": "P", "purchase_cost": None}], R, RecargoTable(), NOW)   # link now exists, no cost
    assert conn.execute(select(cost_write_requests.c.status)).scalar_one() == "pending_review"                                     # reviewable, not released
    assert conn.execute(select(outbox)).all() == []
    approve_write(conn, res.request.id, buyer(), blob, now=NOW)
    assert conn.execute(select(cost_write_requests.c.status)).scalar_one() == "approved_by_buyer" and len(conn.execute(select(outbox)).all()) == 1


def test_release_needs_the_buyer_role_and_a_fresh_second_factor(conn, blob):
    sid = add_supplier(conn)
    link(conn, sid, False)
    rid = request_write(conn, manual(conn, sid).id, "missing_cost", "buyer-1", NOW).request.id
    for p, code in [(buyer(age=6), "mfa_required"), (buyer(age=None), "mfa_required"), (buyer(roles=("approver",)), "not_a_buyer"), (buyer(roles=("admin",)), "not_a_buyer")]:
        with pytest.raises(WriteError) as e:
            approve_write(conn, rid, p, blob, now=NOW)
        assert e.value.code == code
    assert conn.execute(select(outbox)).all() == [] and writer_view(conn, rid) is None
    approve_write(conn, rid, buyer(age=4), blob, now=NOW)
    v = writer_view(conn, rid)
    assert v["cents"] == 1052 and v["status"] == "approved_by_buyer" and v["supplier_contact_id"] == 1


def test_only_released_requests_are_visible_to_the_writer_so_a_forged_id_gets_nothing(conn, blob):
    sid = add_supplier(conn)
    link(conn, sid, False)
    rid = request_write(conn, manual(conn, sid).id, "missing_cost", "buyer-1", NOW).request.id
    assert writer_view(conn, rid) is None and writer_view(conn, "forged-id") is None
    approve_write(conn, rid, buyer(), blob, now=NOW)
    cancel_write(conn, rid, "buyer-1", NOW)
    assert writer_view(conn, rid) is None


def test_order_confirmation_case_only_when_the_cost_differs_from_the_erp(conn):
    sid = add_supplier(conn, 9)
    import_supplier_rows(conn, [{"product_id": 1, "contact_id": 9, "supplier_name": "P", "purchase_cost": D("10.00")}], R, RecargoTable(), NOW)
    same = manual(conn, sid, "10.00")
    assert request_write(conn, same.id, "order_confirmed", "buyer-1", NOW).status == "unchanged"
    diff = manual(conn, sid, "10.40")
    res = request_write(conn, diff.id, "order_confirmed", "buyer-1", NOW)
    assert res.status == "pending_review" and D(str(res.request.previous_siweb_value)) == D("10.00")
    assert request_write(conn, diff.id, "order_confirmed", "buyer-1", NOW).request.id == res.request.id        # idempotent


def test_missing_cost_trigger_is_refused_when_the_erp_already_has_a_cost(conn):
    sid = add_supplier(conn)
    link(conn, sid, has_cost=True)
    with pytest.raises(WriteError) as e:
        request_write(conn, manual(conn, sid).id, "missing_cost", "buyer-1", NOW)
    assert e.value.code == "erp_already_has_cost"
    with pytest.raises(WriteError):
        request_write(conn, manual(conn, sid, "11").id, "bogus", "buyer-1", NOW)


def test_variant_conflict_must_be_acknowledged_before_release(conn, blob):
    sid = add_supplier(conn)
    link(conn, sid, False)
    add_product(conn, 5, 1)
    add_product(conn, 6, 1)                                                                                     # two variants share the product-level ERP cost
    res = request_write(conn, manual(conn, sid).id, "missing_cost", "buyer-1", NOW)
    assert res.warnings == ["variant_conflict"]
    with pytest.raises(WriteError) as e:
        approve_write(conn, res.request.id, buyer(), blob, now=NOW)
    assert e.value.code == "variant_conflict_unacknowledged"
    approve_write(conn, res.request.id, buyer(), blob, acknowledge_variant_conflict=True, now=NOW)


def test_a_superseded_cost_cannot_be_written(conn, blob):
    sid = add_supplier(conn)
    link(conn, sid, False)
    rid = request_write(conn, manual(conn, sid, "10").id, "missing_cost", "buyer-1", NOW).request.id
    manual(conn, sid, "10.5")
    with pytest.raises(WriteError) as e:
        approve_write(conn, rid, buyer(), blob, now=NOW)
    assert e.value.code == "cost_superseded"


def test_failures_and_retries_stay_visible_until_success(conn, blob):
    sid = add_supplier(conn)
    link(conn, sid, False)
    rid = request_write(conn, manual(conn, sid).id, "missing_cost", "buyer-1", NOW).request.id
    approve_write(conn, rid, buyer(), blob, now=NOW)
    apply_outcome(conn, rid, "retrying", 2, "503 Service Unavailable", NOW)
    r = apply_outcome(conn, rid, "failed", 5, "503 Service Unavailable", NOW)
    assert (r.status, r.attempts, r.last_error) == ("failed", 5, "503 Service Unavailable") and [x.id for x in list_visible(conn)] == [rid]
    approve_write(conn, rid, buyer(), blob, now=NOW)                                                           # buyer re-releases a failed write
    ok = apply_outcome(conn, rid, "succeeded", 6, None, NOW)
    assert ok.status == "succeeded" and list_visible(conn) == []
    assert conn.execute(select(erp_supplier_links.c.has_cost)).scalar_one() is True
    assert apply_outcome(conn, rid, "failed", 7, "late duplicate", NOW).status == "succeeded"                   # a final state never regresses
    with pytest.raises(WriteError):
        apply_outcome(conn, rid, "weird", 1)


def test_every_step_is_in_the_tamper_evident_audit_trail(conn, blob):
    sid = add_supplier(conn)
    link(conn, sid, False)
    rid = request_write(conn, manual(conn, sid).id, "missing_cost", "buyer-1", NOW).request.id
    approve_write(conn, rid, buyer(), blob, now=NOW)
    apply_outcome(conn, rid, "succeeded", 1, None, NOW)
    from db.tables import audit_events

    actions = [r.action for r in conn.execute(select(audit_events).order_by(audit_events.c.id)).all()]
    assert actions[-3:] == ["cost_write.requested", "cost_write.approved", "cost_write.succeeded"] and verify_chain(conn).ok
