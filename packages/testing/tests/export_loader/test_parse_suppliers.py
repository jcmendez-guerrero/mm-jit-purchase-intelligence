"""T057 (FR-009, FR-019): the supplier export: customers excluded, sensitive columns dropped, payment terms parsed, nothing guessed."""

from __future__ import annotations

import csv
import io

import pytest
from export_loader import formats
from export_loader.parse_suppliers import parse_payment_terms, parse_suppliers
from export_loader.validate_file import Limits, LoaderFileError
from generator.exports import write_exports

LIMITS = Limits()


@pytest.fixture(scope="module")
def parsed(tmp_path_factory):
    d = tmp_path_factory.mktemp("sup")
    data = write_exports(d, seed=42)
    return parse_suppliers((d / "proveedores.csv").read_bytes(), "proveedores.csv", LIMITS), data


def csv_bytes(rows: list[dict[str, str]]) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=formats.SUPPLIERS_HEADERS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({h: r.get(h, "") for h in formats.SUPPLIERS_HEADERS})
    return buf.getvalue().encode("utf-8")


def row(**kw) -> dict[str, str]:
    base = {"ID": "9100001", "Nombre Empresa": "Proveedor Sintetico", "Tipo Fiscal": "nacional", "País": "España", "Tipo Relación": "Proveedor", "Moneda Habitual": "EUR"}
    base.update(kw)
    return base


def test_every_row_is_accounted_for(parsed):
    out, data = parsed
    r = out.report
    assert r.loaded + r.updated + r.unchanged + r.quarantined + r.excluded + r.services == r.rows or out.ok_rows + r.quarantined + r.excluded == r.rows
    assert r.excluded == data.truth["customer_rows"] and r.quarantined == 0 and out.ok_rows == r.rows - r.excluded


def test_customers_are_excluded_and_never_returned(parsed):
    out, _ = parsed
    assert all("Cliente" not in s.name for s in out.suppliers)


def test_the_supplier_id_is_kept_as_the_erp_reference(parsed):
    out, data = parsed
    ids = {s.external_id for s in out.suppliers}
    assert ids <= {int(r["ID"]) for r in data.suppliers} and all(i in formats.SYNTHETIC_SUPPLIER_IDS for i in ids)


def test_nothing_sensitive_survives_parsing(parsed):
    out, data = parsed
    blob = repr(out.suppliers)
    for r in data.suppliers:
        assert not r["CIF"] or r["CIF"] not in blob
        assert not r["Notas"] or r["Notas"] not in blob
        assert not r["Email General"] or r["Email General"] not in blob
    assert set(out.suppliers[0].__dataclass_fields__) == {"row", "external_id", "name", "fiscal_type", "country", "currency", "payment_terms_days", "terms_unparsed", "has_note"}


def test_notes_become_a_flag(parsed):
    out, data = parsed
    assert sum(s.has_note for s in out.suppliers) == sum(1 for r in data.suppliers if r["Notas"] and r["Tipo Relación"] == "Proveedor")


def test_fiscal_type_country_and_currency_are_normalised(parsed):
    out, _ = parsed
    by = {s.name: s for s in out.suppliers}
    foreign = by["Proveedor Sintetico Extranjero 01 Ltd"]
    assert (foreign.fiscal_type, foreign.country, foreign.currency) == ("foreign", "US", "USD")
    assert by["Proveedor Sintetico Comunitario 01 Ltd"].fiscal_type == "intracommunity" and by["Proveedor Sintetico Comunitario 01 Ltd"].country == "IE"
    assert {s.country for s in out.suppliers} >= {"ES", "US", "IE"}


@pytest.mark.parametrize(("text", "days", "unparsed"), [
    ("7 días", 7, False), ("30", 30, False), ("30 días", 30, False), (" 60 dias ", 60, False), ("0", 0, False), ("", None, False),
    ("a convenir", None, True), ("30/60/90", None, True), ("1000", None, True), ("-5", None, True),
])
def test_payment_terms(text, days, unparsed):
    assert parse_payment_terms(text) == (days, unparsed)


def test_unparsed_terms_are_counted_not_guessed(parsed):
    out, data = parsed
    expected = sum(1 for r in data.suppliers if r["Tipo Relación"] == "Proveedor" and r["Condiciones Pago"] and parse_payment_terms(r["Condiciones Pago"])[1])
    assert sum(s.terms_unparsed for s in out.suppliers) == expected > 0
    assert all(s.payment_terms_days is None for s in out.suppliers if s.terms_unparsed)


def test_currency_defaults_to_eur_and_must_be_three_letters():
    ok = parse_suppliers(csv_bytes([row(**{"Moneda Habitual": ""})]), "s.csv", LIMITS)
    assert ok.suppliers[0].currency == "EUR"
    bad = parse_suppliers(csv_bytes([row(**{"Moneda Habitual": "euro"})]), "s.csv", LIMITS)
    assert bad.report.quarantined == 1 and bad.report.reviews[0]["code"] == "invalid_currency"


def test_bad_rows_are_quarantined_with_a_code():
    out = parse_suppliers(csv_bytes([row(ID="abc"), row(ID="", **{"Nombre Empresa": "X"}), row(ID="5", **{"Nombre Empresa": " "}), row(ID="6", **{"País": "Narnia"}),
                                     row(ID="7", **{"Tipo Fiscal": "raro"})]), "s.csv", LIMITS)
    assert out.report.quarantined == 5 and out.ok_rows == 0
    assert [r["code"] for r in out.report.reviews] == ["invalid_id", "invalid_id", "missing_name", "unknown_country", "unknown_fiscal_type"]


def test_a_repeated_id_is_quarantined_after_the_first():
    out = parse_suppliers(csv_bytes([row(ID="9100001"), row(ID="9100001", **{"Nombre Empresa": "Otro"})]), "s.csv", LIMITS)
    assert out.ok_rows == 1 and out.report.reviews[0]["code"] == "duplicate_id"


def test_a_blank_fiscal_type_is_inferred_from_the_country():
    out = parse_suppliers(csv_bytes([row(ID="1", **{"Tipo Fiscal": ""}), row(ID="2", **{"Tipo Fiscal": "", "País": "China"})]), "s.csv", LIMITS)
    assert [s.fiscal_type for s in out.suppliers] == ["national", "foreign"]


def test_relation_matching_ignores_case_and_accents():
    out = parse_suppliers(csv_bytes([row(ID="1", **{"Tipo Relación": " CLIENTE "}), row(ID="2", **{"Tipo Relación": ""})]), "s.csv", LIMITS)
    assert out.report.excluded == 1 and out.ok_rows == 1


def test_wrong_headers_are_rejected():
    with pytest.raises(LoaderFileError) as exc:
        parse_suppliers(b"ID,Nombre\n1,x\n", "s.csv", LIMITS)
    assert exc.value.code == "local_load_signature_mismatch"
