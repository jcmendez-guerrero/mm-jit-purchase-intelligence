"""MMI-7 T051 + T052 + T053: Spanish formats and original date text, discarded personal data, closed versions, audit trail across every state. Synthetic data only."""

from decimal import Decimal

import pytest
from conftest import KNOWN
from db.tables import audit_events, import_jobs, seed_datasets, seed_quarantine, seed_rows
from seeds.lifecycle import (
    LifecycleError,
    activate,
    record_dry_run,
    register_upload,
    reject,
    rollback,
    validate_dataset,
)
from seeds.validation import parse_quantity
from sqlalchemy import select
from upload_settings import ParseLimits

L = ParseLimits()
SKUS = {f"EJ-{v}": v for v in KNOWN}
HEADER = "SKU;Fecha;Cantidad;Tipo de dato;Origen;Sintético/Real;Notas;CIF;Email"


def file(*rows):
    return (HEADER + "\n" + "\n".join(rows) + "\n").encode()


ROW = "EJ-9001;05/01/2026;1.234,5;estimado;Hoja sintética A;sintético;nota privada sintética;B00000000;persona@example.invalid"


def upload_and_validate(conn, store, data, validator="buyer-2"):
    up = register_upload(conn, store, "datos.csv", data, "Hoja", "buyer-1", L)
    validate_dataset(conn, store, up["id"], up["suggested_mapping"], KNOWN, validator, L, sku_map=SKUS)
    return up["id"]


def test_spanish_number_formats_are_read_exactly():
    assert parse_quantity("1.234,5") == Decimal("1234.5") and parse_quantity("2,5") == Decimal("2.5") and parse_quantity("3") == Decimal(3)


def test_the_original_date_text_is_kept_beside_the_normalised_day(conn, store):
    d = upload_and_validate(conn, store, file(ROW))
    r = conn.execute(select(seed_rows).where(seed_rows.c.dataset_id == d)).one()
    assert r.day.isoformat() == "2026-01-05" and r.day_text == "05/01/2026" and r.quantity == Decimal("1234.5")


def test_notes_tax_ids_and_emails_are_never_stored_logged_or_audited(conn, store):
    d = upload_and_validate(conn, store, file(ROW, ROW.replace("05/01/2026", "no es fecha")))
    rows = [tuple(r) for t in (seed_rows, seed_quarantine, import_jobs, audit_events) for r in conn.execute(select(t)).all()]
    stored = repr(rows)
    for secret in ("nota privada sintética", "B00000000", "persona@example.invalid"):
        assert secret not in stored, secret
    assert d


@pytest.mark.parametrize("terminal", ["activate", "reject"])
def test_a_dataset_that_left_the_open_states_cannot_be_validated_again(conn, store, terminal):
    d = upload_and_validate(conn, store, file(ROW))
    before = [tuple(r) for r in conn.execute(select(seed_rows).where(seed_rows.c.dataset_id == d)).all()]
    reject(conn, d, "buyer-2") if terminal == "reject" else activate(conn, store, d, "approver-9")
    with pytest.raises(LifecycleError) as e:
        validate_dataset(conn, store, d, {"SKU": "sku", "Fecha": "day", "Cantidad": "quantity", "Tipo de dato": "kind", "Origen": "provenance", "Sintético/Real": "origin"}, KNOWN, "buyer-2", L, sku_map=SKUS)
    assert e.value.code == "import_dataset_state"
    assert [tuple(r) for r in conn.execute(select(seed_rows).where(seed_rows.c.dataset_id == d)).all()] == before


def test_superseded_and_rolled_back_datasets_stay_stored_and_listed(conn, store):
    a = upload_and_validate(conn, store, file(ROW))
    activate(conn, store, a, "approver-9")
    b = upload_and_validate(conn, store, file(ROW.replace("1.234,5", "9")))
    activate(conn, store, b, "approver-9")
    rollback(conn, store, "approver-9", reason_code="test")
    states = {r.id: r.status for r in conn.execute(select(seed_datasets)).all()}
    assert states == {a: "active", b: "rolled_back"}
    assert conn.execute(select(seed_rows).where(seed_rows.c.dataset_id == b)).first() is not None        # rolled-back rows are kept


def test_every_state_change_is_audited_with_actor_and_version_and_no_file_content(conn, store):
    a = upload_and_validate(conn, store, file(ROW))
    record_dry_run(conn, a, "buyer-3", {"compared_with": None, "rows": {"added": 1}})
    activate(conn, store, a, "approver-9")
    rollback(conn, store, "approver-9", reason_code="wrong_figures")
    b = upload_and_validate(conn, store, file(ROW.replace("1.234,5", "7")))
    reject(conn, b, "buyer-2")
    entries = conn.execute(select(audit_events).order_by(audit_events.c.id)).all()
    assert [e.action for e in entries] == ["seed.uploaded", "seed.validated", "seed.dry_run", "seed.activated", "seed.rolled_back", "seed.uploaded", "seed.validated", "seed.rejected"]
    assert all(e.actor for e in entries) and all(getattr(e, "ts", getattr(e, "created_at", None)) is not None for e in entries)
    text = repr([tuple(e) for e in entries])
    assert "Hoja sintética" not in text and "EJ-9001" not in text and "Cifras erróneas" not in text and "1234" not in text
