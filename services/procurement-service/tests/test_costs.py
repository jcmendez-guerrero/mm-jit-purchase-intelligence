"""T071: version immutability, staleness and jump blocking; plus resolution, ERP import and the audit chain."""

from datetime import timedelta
from decimal import Decimal

import pytest
from audit.chain import GENESIS, compute_hash, verify_chain
from conftest import NOW, add_product, add_supplier
from costs.recargo import RecargoTable
from costs.resolve import resolve_cost
from costs.rules import CostRules, is_abnormal_jump, is_stale, load_rules
from costs.siweb_import import import_supplier_rows
from costs.store import CostError, NewCost, add_version, confirm_jump, current, history, verify
from db.tables import audit_events, cost_rule_config, erp_supplier_links, supplier_costs
from sqlalchemy import insert, select, update

D = Decimal
R = CostRules()


def new(sid, value, source="manual", variant=None, product=1, actor="buyer-1", **kw):
    return NewCost(product_id=product, supplier_id=sid, cost_with_recargo=D(value), source=source, actor=actor, variant_id=variant, **kw)


def test_every_change_is_a_new_immutable_version_that_supersedes_the_previous(conn):
    sid = add_supplier(conn)
    v1 = add_version(conn, new(sid, "10.00"), R, NOW)
    v2 = add_version(conn, new(sid, "10.50"), R, NOW + timedelta(days=1))
    h = history(conn, 1, sid)
    assert [r.version for r in h] == [1, 2] and h[0].superseded_by == v2.id and h[1].superseded_by is None
    assert current(conn, 1, sid).id == v2.id
    assert D(str(h[0].cost_with_recargo)) == D("10.00") and h[0].id == v1.id        # the old value is untouched


def test_only_attestation_fields_are_ever_updated(conn):
    sid = add_supplier(conn)
    c = add_version(conn, new(sid, "10"), R, NOW)
    before = dict(conn.execute(select(supplier_costs)).one()._mapping)
    verify(conn, c.id, "buyer-2", NOW + timedelta(days=40))
    after = dict(conn.execute(select(supplier_costs)).one()._mapping)
    changed = {k for k in before if before[k] != after[k]}
    assert changed <= {"verified_at", "verified_by"} and changed


def test_sources_are_restricted_and_last_paid_is_not_an_offer(conn):
    sid = add_supplier(conn)
    for bad in ("last_paid", "erp", ""):
        with pytest.raises(CostError):
            add_version(conn, new(sid, "10", source=bad), R, NOW)
    with pytest.raises(CostError):
        add_version(conn, new(sid, "-1"), R, NOW)


def test_staleness_uses_the_configured_threshold(conn):
    assert not is_stale(NOW - timedelta(days=30), NOW, R) and is_stale(NOW - timedelta(days=31), NOW, R)
    conn.execute(insert(cost_rule_config).values(key="stale_days", value=D("7"), changed_by="admin", changed_at=NOW))
    assert is_stale(NOW - timedelta(days=8), NOW, load_rules(conn))


def test_abnormal_jump_threshold_and_edges():
    assert not is_abnormal_jump(D("10"), D("12.5"), R) and is_abnormal_jump(D("10"), D("12.51"), R)
    assert not is_abnormal_jump(D("10"), D("7.5"), R) and is_abnormal_jump(D("10"), D("7.4"), R)
    assert not is_abnormal_jump(None, D("99"), R) and not is_abnormal_jump(D("0"), D("5"), R)


def test_a_jump_blocks_use_until_the_buyer_confirms_it(conn):
    sid = add_supplier(conn)
    add_version(conn, new(sid, "10"), R, NOW)
    jump = add_version(conn, new(sid, "20", source="csv_price_list"), R, NOW + timedelta(days=1))
    assert jump.jump_flag
    res = resolve_cost(conn, 1, sid, R, now=NOW + timedelta(days=1))
    assert not res.usable and res.status == "blocked_jump"
    confirm_jump(conn, jump.id, "buyer-1", NOW + timedelta(days=1))
    assert resolve_cost(conn, 1, sid, R, now=NOW + timedelta(days=1)).usable
    with pytest.raises(CostError):
        confirm_jump(conn, history(conn, 1, sid)[0].id, "buyer-1")                   # no jump on the first version


def test_a_later_cost_is_compared_with_the_last_accepted_value_not_an_unconfirmed_jump(conn):
    sid = add_supplier(conn)
    add_version(conn, new(sid, "10"), R, NOW)
    add_version(conn, new(sid, "30"), R, NOW)                                          # unconfirmed jump
    back = add_version(conn, new(sid, "10.5"), R, NOW)                                 # near the accepted 10 -> no jump
    assert not back.jump_flag
    again = add_version(conn, new(sid, "40"), R, NOW)
    assert again.jump_flag


def test_stale_costs_are_usable_but_flagged_and_can_be_verified(conn):
    sid = add_supplier(conn)
    c = add_version(conn, new(sid, "10"), R, NOW)
    later = NOW + timedelta(days=45)
    res = resolve_cost(conn, 1, sid, R, now=later)
    assert res.usable and res.status == "stale" and res.warnings == ["stale"]
    verify(conn, c.id, "buyer-1", later)
    assert resolve_cost(conn, 1, sid, R, now=later).status == "ok"


def test_variant_override_beats_the_product_level_cost_and_missing_cost_is_required(conn):
    sid = add_supplier(conn)
    assert resolve_cost(conn, 1, sid, R, now=NOW).needs_entry and resolve_cost(conn, 1, sid, R, now=NOW).status == "cost_required"
    add_version(conn, new(sid, "10", source="siweb_product_supplier"), R, NOW)
    add_version(conn, new(sid, "12", variant=77, pack_size=12), R, NOW)
    over = resolve_cost(conn, 1, sid, R, variant_id=77, now=NOW)
    assert over.from_variant_override and D(str(over.cost.cost_with_recargo)) == D("12")
    other = resolve_cost(conn, 1, sid, R, variant_id=78, now=NOW)
    assert not other.from_variant_override and D(str(other.cost.cost_with_recargo)) == D("10")


def test_erp_import_treats_cost_as_with_recargo_discards_cif_and_counts_import_time_as_verification(conn):
    add_product(conn, 5, 1, vat=D("21"))
    rows = [{"product_id": 1, "contact_id": 9, "supplier_name": "Proveedor Sintetico", "purchase_cost": D("10.52"), "lead_time_days": 3,
             "min_order_qty": 2, "supplier_cif": "A00000000"}]
    out = import_supplier_rows(conn, rows, R, RecargoTable(), NOW)
    assert (out.new_versions, out.unchanged, out.no_cost) == (1, 0, 0)
    c = conn.execute(select(supplier_costs)).one()
    assert D(str(c.cost_with_recargo)) == D("10.52") and D(str(c.cost_net)) == D("10.0000") and c.entered_includes_recargo is True
    assert c.verified_at.replace(tzinfo=NOW.tzinfo) == NOW and c.source == "siweb_product_supplier" and (c.lead_time_days, c.min_order_qty) == (3, 2)
    assert "A00000000" not in str(conn.execute(select(supplier_costs)).all()) + str(conn.execute(select(audit_events)).all())
    out2 = import_supplier_rows(conn, rows, R, RecargoTable(), NOW + timedelta(days=5))
    assert (out2.new_versions, out2.unchanged) == (0, 1)
    c2 = conn.execute(select(supplier_costs)).one()
    assert c2.verified_at.replace(tzinfo=NOW.tzinfo) == NOW + timedelta(days=5) and len(history(conn, 1, c.supplier_id)) == 1


def test_erp_import_records_links_without_a_cost_and_detects_jumps(conn):
    rows = [{"product_id": 1, "contact_id": 9, "supplier_name": "P", "purchase_cost": None}, {"product_id": 2, "contact_id": 9, "supplier_name": "P", "purchase_cost": D("0")}]
    out = import_supplier_rows(conn, rows, R, RecargoTable(), NOW)
    assert out.no_cost == 2 and conn.execute(select(supplier_costs)).all() == []
    assert [r.has_cost for r in conn.execute(select(erp_supplier_links).order_by(erp_supplier_links.c.product_id)).all()] == [False, False]
    import_supplier_rows(conn, [{"product_id": 1, "contact_id": 9, "purchase_cost": D("10")}], R, RecargoTable(), NOW)
    out = import_supplier_rows(conn, [{"product_id": 1, "contact_id": 9, "purchase_cost": D("20")}], R, RecargoTable(), NOW + timedelta(days=1))
    assert out.new_versions == 1 and out.jumps == 1
    assert conn.execute(select(erp_supplier_links.c.has_cost).where(erp_supplier_links.c.product_id == 1)).scalar_one() is True


def test_audit_chain_detects_tampering_removal_and_reordering(conn):
    sid = add_supplier(conn)
    c = add_version(conn, new(sid, "10"), R, NOW)
    verify(conn, c.id, "buyer-1", NOW)
    add_version(conn, new(sid, "10.5"), R, NOW)
    assert verify_chain(conn).ok and verify_chain(conn).checked == 3
    first = conn.execute(select(audit_events).order_by(audit_events.c.id)).first()
    assert first.prev_hash == GENESIS and first.hash == compute_hash(GENESIS, {"ts": NOW.isoformat(), "actor": "buyer-1", "action": "cost.version_added",
                                                                              "entity": "supplier_cost", "entity_id": c.id, "before": None, "after": first.after})
    conn.execute(update(audit_events).where(audit_events.c.id == first.id).values(actor="someone-else"))
    bad = verify_chain(conn)
    assert not bad.ok and bad.broken_at == first.id and bad.reason == "content altered"


def test_audit_chain_detects_a_deleted_event(conn):
    sid = add_supplier(conn)
    for v in ("10", "10.1", "10.2"):
        add_version(conn, new(sid, v), R, NOW)
    middle = conn.execute(select(audit_events.c.id).order_by(audit_events.c.id)).scalars().all()[1]
    conn.execute(audit_events.delete().where(audit_events.c.id == middle))
    check = verify_chain(conn)
    assert not check.ok and check.reason == "link broken: event removed or reordered"
