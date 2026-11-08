"""T100 + T104: activation is atomic, audited, announces a run, and a repeated file needs an explicit decision."""

import pytest
import seed_fixtures as sf
from conftest import KNOWN
from db.tables import audit_events, outbox, seed_datasets
from seeds.lifecycle import (
    LifecycleError,
    activate,
    active_dataset,
    duplicate_of,
    list_datasets,
    register_upload,
    reject,
    validate_dataset,
)
from seeds.storage import SeedFileError
from sqlalchemy import func, select, update
from upload_settings import ParseLimits

L = ParseLimits()


def upload(conn, store, data=None, name="datos.csv", who="buyer-1"):
    return register_upload(conn, store, name, data if data is not None else sf.static("valid.csv"), "Hoja", who, L)


def validated(conn, store, data=None, name="datos.csv"):
    up = upload(conn, store, data, name)
    validate_dataset(conn, store, up["id"], up["suggested_mapping"], KNOWN, "buyer-1", L)
    return up["id"]


def test_upload_keeps_the_original_privately_and_stores_no_rows_yet(conn, store):
    up = upload(conn, store)
    assert up["status"] == "uploaded" and up["row_count"] == 5 and up["missing"] == [] and len(up["preview"]) == 5 and up["version"] == 1
    ds = conn.execute(select(seed_datasets)).one()
    assert ds.file_ref.startswith("file://seeds/") and ds.accepted_count == 0 and store.get(ds.file_ref) == sf.static("valid.csv")


def test_validation_stores_accepted_rows_and_quarantine_and_is_repeatable(conn, store):
    did = validated(conn, store, sf.static("partly_invalid.csv"))
    ds = conn.execute(select(seed_datasets)).one()
    assert (ds.status, ds.accepted_count, ds.quarantined_count) == ("validated", 2, 8)
    again = validate_dataset(conn, store, did, register_map(), KNOWN, "buyer-1", L)
    assert again["accepted"] == 2 and again["quarantined"] == 8


def register_map():
    from seeds.mapping import suggest

    return suggest(sf.HEADER)


def test_a_file_missing_a_required_column_cannot_be_validated(conn, store):
    up = upload(conn, store, b"Fecha;Cantidad\n2026-01-05;2\n")
    with pytest.raises(SeedFileError) as e:
        validate_dataset(conn, store, up["id"], up["suggested_mapping"], KNOWN, "buyer-1", L)
    assert e.value.code == "import_missing_column"


def test_activation_is_audited_announces_a_run_and_supersedes_the_previous_one(conn, store):
    first = validated(conn, store)
    out = activate(conn, store, first, "buyer-1")
    assert out["status"] == "active" and active_dataset(conn).id == first
    events = [e for e in conn.execute(select(outbox)).all() if e.type == "forecast.seed.activated.v1"]
    assert len(events) == 1
    second = validated(conn, store, sf.static("valid.csv").replace(b"2026-01-05", b"2026-01-06"))
    out2 = activate(conn, store, second, "admin-1")
    assert out2["superseded"] == first and active_dataset(conn).id == second
    status = {d["id"]: d["status"] for d in list_datasets(conn)}
    assert status == {first: "superseded", second: "active"}
    actions = [a.action for a in conn.execute(select(audit_events)).all()]
    assert actions.count("seed.activated") == 2 and "seed.uploaded" in actions and "seed.validated" in actions


def test_only_a_validated_dataset_with_rows_can_be_activated(conn, store):
    up = upload(conn, store)
    with pytest.raises(LifecycleError) as e:
        activate(conn, store, up["id"], "buyer-1")
    assert e.value.code == "import_dataset_state"
    empty = upload(conn, store, sf.static("partly_invalid.csv").split(b"\n")[0] + "\n9999;2026-01-05;1;;estimado;X;sintético\n".encode(), name="vacio.csv")
    validate_dataset(conn, store, empty["id"], empty["suggested_mapping"], KNOWN, "buyer-1", L)
    with pytest.raises(LifecycleError) as e2:
        activate(conn, store, empty["id"], "buyer-1")
    assert e2.value.code == "import_nothing_to_activate"
    with pytest.raises(LifecycleError):
        activate(conn, store, "nope", "buyer-1")


def test_a_failure_leaves_the_previous_dataset_active(conn, store):
    first = validated(conn, store)
    activate(conn, store, first, "buyer-1")
    real = validated(conn, store, sf.static("valid.csv").replace(b"sint\xc3\xa9tico", b"real").replace(b"2026-01-05", b"2026-01-07"))
    with pytest.raises(SeedFileError) as e:
        activate(conn, store, real, "buyer-1")
    assert e.value.code == "import_mixed_origin"
    assert active_dataset(conn).id == first
    assert conn.execute(select(func.count()).select_from(outbox).where(outbox.c.type == "forecast.seed.activated.v1")).scalar() == 1


def test_a_repeated_file_is_flagged_and_needs_an_explicit_decision(conn, store):
    first = validated(conn, store)
    activate(conn, store, first, "buyer-1")
    again = upload(conn, store)
    assert again["duplicate_of"] == first and duplicate_of(conn, again["sha256"], again["id"]) == first
    validate_dataset(conn, store, again["id"], again["suggested_mapping"], KNOWN, "buyer-1", L)
    with pytest.raises(LifecycleError) as e:
        activate(conn, store, again["id"], "buyer-1")
    assert e.value.code == "import_duplicate_file"
    assert activate(conn, store, again["id"], "buyer-1", acknowledge_duplicate=True)["status"] == "active"
    last = [a for a in conn.execute(select(audit_events)).all() if a.action == "seed.activated"][-1]
    assert "duplicate_acknowledged" in str(last.after) and "true" in str(last.after).lower()


def test_an_unrelated_file_is_not_a_duplicate(conn, store):
    first = validated(conn, store)
    activate(conn, store, first, "buyer-1")
    assert upload(conn, store, sf.static("valid.csv").replace(b"2026-01-05", b"2026-01-09"))["duplicate_of"] is None


def test_a_dataset_can_be_rejected_unless_active(conn, store):
    did = validated(conn, store)
    reject(conn, did, "buyer-1")
    assert conn.execute(select(seed_datasets.c.status)).scalar() == "rejected"
    other = validated(conn, store, sf.static("valid.csv").replace(b"2026-01-05", b"2026-01-10"))
    activate(conn, store, other, "buyer-1")
    with pytest.raises(LifecycleError):
        reject(conn, other, "buyer-1")
    conn.execute(update(seed_datasets).where(seed_datasets.c.id == other).values(status="active"))
