# ruff: noqa: F811
"""T046 (FR-029, constitution rule 7): free-text ERP notes, tax identifiers and bank details are never stored, logged or returned.

They are refused at the door (the request models forbid unknown fields, so nothing is silently dropped), no table has a column that could hold
them, and the only trace of a note is the boolean ``has_note``. The marker text below must not be found anywhere afterwards.
"""

from __future__ import annotations

import re

import pytest
from db.tables import metadata
from refusal_support import app, client, engine, h, sid  # noqa: F401
from sqlalchemy import func, select, text
from test_internal_supplier_import import client as loader_client  # noqa: F401  (fixture: the local loader's import route)
from test_internal_supplier_import import post, row

MARKER = "MARCADOR-PRIVADO-9F3A"
SENSITIVE_FIELDS = ["tax_id", "cif", "nif", "supplier_cif", "iban", "bank_account", "note", "notes", "observaciones", "nota"]
SENSITIVE_COLUMN = re.compile(r"^(cif|nif|tax_id|vat_id|iban|bank.*|swift|bic|note|notes|note_text|nota|observ.*)$")
BASE = {"name": "Proveedor Sintetico Nuevo", "fiscal_type": "national", "country": "ES", "currency": "EUR"}


def everything(engine) -> str:
    """Every cell of every table, as text."""
    out = []
    with engine.begin() as conn:
        for table in metadata.sorted_tables:
            for r in conn.execute(select(table)).all():
                out.extend(str(v) for v in r)
    return "\n".join(out)


def supplier_count(engine) -> int:
    with engine.begin() as conn:
        return int(conn.execute(text("select count(*) from suppliers")).scalar())


@pytest.mark.parametrize("field", SENSITIVE_FIELDS)
def test_creating_a_supplier_with_a_sensitive_field_is_refused_and_nothing_is_kept(client, engine, field):
    before = supplier_count(engine)
    res = client.post("/suppliers", json={**BASE, field: MARKER}, headers=h())
    assert res.status_code == 422
    assert supplier_count(engine) == before and MARKER not in everything(engine)


@pytest.mark.parametrize("field", SENSITIVE_FIELDS)
def test_editing_a_supplier_with_a_sensitive_field_is_refused_and_nothing_is_kept(client, engine, sid, field):
    res = client.patch(f"/suppliers/{sid}", json={field: MARKER}, headers=h(**{"If-Match": '"1"'}))
    assert res.status_code == 422
    assert MARKER not in everything(engine)


@pytest.mark.parametrize("field", SENSITIVE_FIELDS)
def test_the_import_refuses_a_sensitive_field_too(loader_client, engine, field):
    res = post(loader_client, [row(**{field: MARKER})])
    assert res.status_code == 422
    assert supplier_count(engine) == 0 and MARKER not in everything(engine)


def test_the_only_trace_of_a_note_is_a_flag(loader_client, engine):
    assert post(loader_client, [row(has_note=True)]).status_code == 200
    with engine.begin() as conn:
        (supplier,) = conn.execute(text("select name, has_note from suppliers")).all()
    assert supplier.has_note in (1, True) and MARKER not in everything(engine)


def test_no_table_has_a_column_that_could_hold_a_note_a_tax_id_or_bank_details():
    holders = [f"{t.name}.{c.name}" for t in metadata.sorted_tables for c in t.columns if SENSITIVE_COLUMN.match(c.name)]
    assert holders == []


def test_a_supplier_read_never_returns_such_fields(client, engine, sid):
    body = client.get(f"/suppliers/{sid}", headers=h("viewer")).json()
    assert not [key for key in body if SENSITIVE_COLUMN.match(key)] and body["has_note"] is False
    listed = client.get("/suppliers", headers=h("viewer")).json()
    assert listed and not [key for item in listed for key in item if SENSITIVE_COLUMN.match(key)]


def test_a_refused_attempt_leaves_no_free_text_in_the_audit_trail_either(client, engine):
    client.post("/suppliers", json={**BASE, "note": MARKER, "iban": MARKER}, headers=h())
    with engine.begin() as conn:
        refused = conn.execute(text("select count(*) from audit_events where action like '%.refused'")).scalar()
    assert refused == 1 and MARKER not in everything(engine)


def test_a_normal_create_stores_the_name_and_nothing_else_free_form(client, engine):
    created = client.post("/suppliers", json=BASE, headers=h())
    assert created.status_code == 201
    with engine.begin() as conn:
        assert conn.execute(select(func.count()).select_from(metadata.tables["suppliers"])).scalar() == 1
    assert "Proveedor Sintetico Nuevo" in everything(engine)
