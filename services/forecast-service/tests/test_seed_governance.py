"""MMI-7 T018 + T020 + T030 + T033: second approver, audited owner/admin override, rollback reason, activation conflict. Synthetic data only."""

import pytest
import seed_fixtures as sf
from conftest import KNOWN
from db.tables import audit_events, seed_datasets
from seeds import lifecycle
from seeds.lifecycle import LifecycleError, activate, active_dataset, register_upload, rollback, validate_dataset
from sqlalchemy import select
from upload_settings import ParseLimits

L = ParseLimits()
SKUS = {f"EJ-{v}": v for v in KNOWN}


def validated(conn, store, data=None, uploader="buyer-1", validator="buyer-2"):
    up = register_upload(conn, store, "datos.csv", data if data is not None else sf.static("valid.csv"), "Hoja", uploader, L)
    validate_dataset(conn, store, up["id"], up["suggested_mapping"], KNOWN, validator, L, sku_map=SKUS)
    return up["id"]


def actions(conn):
    return [a.action for a in conn.execute(select(audit_events)).all()]


def test_the_uploader_and_the_validator_cannot_activate(conn, store):
    d = validated(conn, store)
    for who in ("buyer-1", "buyer-2"):
        with pytest.raises(LifecycleError) as e:
            activate(conn, store, d, who)
        assert e.value.code == "import_self_approval"
    assert active_dataset(conn) is None


def test_a_different_person_can_activate(conn, store):
    d = validated(conn, store)
    assert activate(conn, store, d, "approver-1")["status"] == "active"
    assert "seed.self_activated" not in actions(conn)


def test_an_owner_admin_may_self_activate_only_with_a_listed_reason_and_it_is_audited_apart(conn, store):
    d = validated(conn, store, uploader="admin-1", validator="admin-1")
    with pytest.raises(LifecycleError) as e:
        activate(conn, store, d, "admin-1", is_admin=True)
    assert e.value.code == "import_reason_required"
    for bad_code, bad_detail in (("because", None), ("wrong_figures", None), ("only_person", "x" * 101)):                  # not in the self-activation list, or a detail that is too long
        with pytest.raises(LifecycleError) as e:
            activate(conn, store, d, "admin-1", is_admin=True, reason_code=bad_code, reason_detail=bad_detail)
        assert e.value.code == "import_reason_invalid"
    with pytest.raises(LifecycleError) as e:
        activate(conn, store, d, "admin-1", reason_code="only_person")
    assert e.value.code == "import_self_approval"                                  # a reason alone is not enough without the admin role
    assert activate(conn, store, d, "admin-1", is_admin=True, reason_code="only_person", reason_detail="  Tienda   con una sola persona ")["status"] == "active"
    ds = conn.execute(select(seed_datasets).where(seed_datasets.c.id == d)).one()
    assert (ds.self_activation_reason_code, ds.self_activation_reason_detail) == ("only_person", "Tienda con una sola persona")
    entry = conn.execute(select(audit_events).where(audit_events.c.action == "seed.self_activated")).one()
    assert "only_person" in repr(tuple(entry)) and "Tienda" not in repr(tuple(entry))                             # the audit trail holds the code, never the detail


def test_a_losing_activation_race_is_reported_as_a_conflict(conn, store, monkeypatch):
    a = validated(conn, store)
    b = validated(conn, store, sf.static("valid.csv").replace(b"2026-01-05", b"2026-01-08"))
    activate(conn, store, a, "approver-1")
    monkeypatch.setattr(lifecycle, "active_dataset", lambda _c: None)              # the second request read the state before the first committed
    with pytest.raises(LifecycleError) as e:
        activate(conn, store, b, "approver-2")
    assert e.value.code == "import_conflict"


def test_rollback_needs_a_listed_reason_stores_it_and_keeps_the_detail_out_of_the_audit_trail(conn, store):
    d = validated(conn, store)
    activate(conn, store, d, "approver-1")
    for missing in (None, "", "   "):
        with pytest.raises(LifecycleError) as e:
            rollback(conn, store, "approver-1", reason_code=missing)
        assert e.value.code == "import_reason_required"
    for bad_code, bad_detail in (("because", None), ("only_person", None), ("test", "x" * 101)):                          # unknown, from the other list, detail too long
        with pytest.raises(LifecycleError) as e:
            rollback(conn, store, "approver-1", reason_code=bad_code, reason_detail=bad_detail)
        assert e.value.code == "import_reason_invalid"
    assert rollback(conn, store, "approver-1", reason_code="wrong_figures", reason_detail="Cifras   erróneas")["status"] == "rolled_back"
    ds = conn.execute(select(seed_datasets).where(seed_datasets.c.id == d)).one()
    assert ds.status == "rolled_back" and (ds.rollback_reason_code, ds.rollback_reason_detail) == ("wrong_figures", "Cifras erróneas")
    entry = conn.execute(select(audit_events).where(audit_events.c.action == "seed.rolled_back")).one()
    assert "wrong_figures" in repr(tuple(entry)) and "Cifras" not in repr(tuple(entry))                                  # the code is audited, the detail never


def test_rolling_back_a_dataset_restores_the_one_it_replaced(conn, store):
    a = validated(conn, store)
    b = validated(conn, store, sf.static("valid.csv").replace(b"2026-01-05", b"2026-01-08"))
    activate(conn, store, a, "approver-1")
    activate(conn, store, b, "approver-1")
    out = rollback(conn, store, "approver-1", reason_code="test")
    assert out["restored"] == a and active_dataset(conn).id == a


def test_the_dataset_list_shows_who_validated_who_activated_and_why_it_was_rolled_back(conn, store):
    from seeds.lifecycle import list_datasets

    a = validated(conn, store)
    b = validated(conn, store, uploader="admin-1", validator="admin-1", data=sf.static("valid.csv").replace(b"2026-01-05", b"2026-01-08"))
    activate(conn, store, a, "approver-1")
    activate(conn, store, b, "admin-1", is_admin=True, reason_code="only_person", reason_detail="Una sola persona")
    rollback(conn, store, "approver-1", reason_code="wrong_figures", reason_detail="Cifras erróneas")
    items = {i["id"]: i for i in list_datasets(conn, is_admin=True)}
    assert items[a]["validated_by"] == "buyer-2" and items[a]["activated_by"] == "approver-1" and items[a]["self_activated"] is False and items[a]["rollback_reason_code"] is None
    assert items[b]["validated_by"] == "admin-1" and items[b]["self_activated"] is True and items[b]["status"] == "rolled_back"
    assert (items[b]["rollback_reason_code"], items[b]["rollback_reason_detail"]) == ("wrong_figures", "Cifras erróneas")
    assert (items[b]["self_activation_reason_code"], items[b]["self_activation_reason_detail"]) == ("only_person", "Una sola persona")
    for item in list_datasets(conn):                                                          # everyone else sees the chosen reasons but never the free-text details
        assert not {"rollback_reason_detail", "self_activation_reason_detail"} & set(item)
    assert {i["id"]: i["rollback_reason_code"] for i in list_datasets(conn)}[b] == "wrong_figures"


def test_a_second_rollback_that_read_the_state_before_the_first_finished_gets_a_conflict(conn, store, monkeypatch):
    """MMI-7 T074 (FR-019): two rollbacks at the same moment end with exactly one success."""
    a = validated(conn, store)
    activate(conn, store, a, "approver-1")
    stale = active_dataset(conn)                                                      # what the second request read before the first one committed
    rollback(conn, store, "approver-1", reason_code="wrong_figures")                    # the first rollback wins
    monkeypatch.setattr(lifecycle, "active_dataset", lambda _c: stale)
    with pytest.raises(LifecycleError) as e:
        rollback(conn, store, "approver-2", reason_code="test")
    assert e.value.code == "import_conflict"
    entries = [a.action for a in conn.execute(select(audit_events)).all()]
    assert entries.count("seed.rolled_back") == 1                                      # the loser left no second audit entry


def test_the_reason_lists_of_the_service_are_the_enums_of_the_contract():
    import json
    from pathlib import Path

    schema = json.loads((Path(__file__).resolve().parents[3] / "packages/contracts/dto/seed_dataset.v1.schema.json").read_text(encoding="utf-8"))

    def enum(field):
        return next(o["enum"] for o in schema["properties"][field]["oneOf"] if "enum" in o)

    assert list(lifecycle.ROLLBACK_REASONS) == enum("rollback_reason_code") and list(lifecycle.SELF_ACTIVATION_REASONS) == enum("self_activation_reason_code")
    assert lifecycle.MAX_DETAIL == 100
