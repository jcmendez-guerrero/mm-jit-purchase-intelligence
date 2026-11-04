"""T030: supplier_cif and free-text notes never reach storage; only has_note is kept."""

import json

from mapping.normalise import normalise_movement, normalise_supplier_row, strip_sensitive
from mapping.quality import check_movement

SECRET_NOTE = "Nota privada del cliente 12345"  # noqa: S105 - synthetic test text


def raw_movement(**kw):
    base = {"id": 1, "created_at": "2026-03-01T10:00:00", "variant_id": 7, "product_id": 3, "warehouse_id": 1, "quantity": -2,
            "movement_type": "out", "reason": "sale_shipment", "reference_type": "ticket", "reference_id": 9,
            "reference_number": "T-1", "unit_cost_cents": "1234.5", "notes": SECRET_NOTE}
    return {**base, **kw}


def test_normalised_movement_has_no_note_text_only_flag():
    mv = normalise_movement(raw_movement())
    assert mv.has_note is True
    assert SECRET_NOTE not in repr(mv)
    assert normalise_movement(raw_movement(notes="  ")).has_note is False
    assert normalise_movement(raw_movement(notes=None)).has_note is False


def test_supplier_cif_is_discarded():
    row = normalise_supplier_row({"id": 1, "product_id": 3, "contact_id": 4, "supplier_name": "Proveedor Sintetico",
                                  "supplier_cif": "A00000000", "purchase_cost_cents": 400, "currency": "EUR"})
    assert "supplier_cif" not in row and "A00000000" not in json.dumps(row, default=str)


def test_strip_sensitive_removes_nested_fields_for_raw_payloads():
    payload = {"data": [raw_movement(), {"supplier_cif": "B1", "x": [{"notes": "a"}]}]}
    out = json.dumps(strip_sensitive(payload))
    assert SECRET_NOTE not in out and "supplier_cif" not in out and '"notes"' not in out
    assert '"has_note": true' in out


def test_quality_issues_never_contain_note_text():
    res = check_movement(raw_movement(reason="sale_shipment", reference_type=None, reference_id=None, reference_number=None))
    assert res.issues and all(SECRET_NOTE not in i.detail for i in res.issues)


def test_money_is_decimal_not_float():
    from decimal import Decimal

    assert normalise_movement(raw_movement()).unit_cost == Decimal("12.345")
    assert isinstance(normalise_movement(raw_movement()).unit_cost, Decimal)
