"""MMI-16 (spec 014): product-supplier terms are read and saved by SKU; the Siweb variant id is resolved here and never returned, audited or logged."""

from __future__ import annotations

import json
import logging

import jsonschema
import pytest
from audit.chain import verify_chain
from conftest import add_product, add_supplier, auth
from db.tables import audit_events, outbox
from sqlalchemy import select
from terms.overrides import current_override_version

VARIANT = 9001
SKU = "SYN-0001"
VIEW_SCHEMA = json.loads((__import__("pathlib").Path(__file__).resolve().parents[3] / "packages/contracts/dto/override_terms_view.v1.schema.json").read_text())


@pytest.fixture
def sid(engine):
    with engine.begin() as c:
        s = add_supplier(c, 1, "Proveedor Sintético A")
        add_product(c, VARIANT, 10, sku=SKU)
        add_product(c, 9002, 11, sku="syn-dup")
        add_product(c, 9003, 12, sku="SYN-DUP ")
        add_product(c, 9004, 14, sku="SYN/áño-1")                 # a slash and accents (SQLite lower() is ASCII-only, so the accents are lower case here)
        add_product(c, 9005, 15, sku="SYN-" + "L" * 36)           # 40 characters: longer than the audit column leaves room for
        add_product(c, 9_000_001, 13, sku="LOCAL-1")            # a surrogate id from the reserved range (local load)
    return s


def url(sku, sid):
    return f"/product-suppliers/{sku}/{sid}/terms"


def put(client, sku, sid, body=None, role="buyer", **headers):
    return client.put(url(sku, sid), json=body if body is not None else {"lead_time_days": 5}, headers={**auth(role), **headers})


def test_reading_by_sku_answers_the_sku_and_never_the_variant_id(client, sid):
    view = client.get(url(SKU, sid), headers=auth()).json()
    assert view["sku"] == SKU and view["supplier_id"] == sid and view["override"] is None and view["version"] == 0
    assert "variant_id" not in json.dumps(view) and str(VARIANT) not in json.dumps(view)
    jsonschema.validate(view, VIEW_SCHEMA)


def test_a_saved_override_is_read_back_and_matches_the_contract(client, sid):
    assert put(client, SKU, sid, {"lead_time_days": 5, "pack_multiple": 12, "reason": "caja de 12"}).json() == {"version": 1}
    view = client.get(url(SKU, sid), headers=auth()).json()
    assert view["override"]["pack_multiple"] == 12 and view["version"] == 1 and view["effective"]["lead_time_days"] == 5
    assert view["effective"]["sources"]["lead_time_days"] == "override" and len(view["history"]) == 1
    jsonschema.validate(view, VIEW_SCHEMA)


def test_the_sku_is_matched_trimmed_and_ignoring_case(client, sid):
    put(client, SKU, sid)
    assert client.get(url("%20syn-0001%20", sid), headers=auth()).json()["version"] == 1
    assert client.get(url("syn-0001", sid), headers=auth()).json()["sku"] == "syn-0001"


def test_a_sku_with_a_slash_and_accents_is_matched_exactly(client, sid):
    from urllib.parse import quote

    encoded = quote("SYN/áño-1", safe="")
    assert put(client, encoded, sid).json() == {"version": 1}
    view = client.get(url(encoded, sid), headers=auth()).json()
    assert view["sku"] == "SYN/áño-1" and view["version"] == 1
    assert client.get(url(quote("SYN/OTRO", safe=""), sid), headers=auth()).json() == {"detail": "sku_unknown"}


def test_as_of_works_and_a_bad_value_is_refused(client, sid):
    put(client, SKU, sid)
    assert client.get(url(SKU, sid) + "?as_of=2000-01-01T00:00:00Z", headers=auth()).json()["override"] is None
    assert client.get(url(SKU, sid) + "?as_of=ayer", headers=auth()).status_code == 400


@pytest.mark.parametrize(("sku", "code"), [("SYN-NO-EXISTE", "sku_unknown"), ("%20", "sku_unknown"), ("SYN-DUP", "sku_ambiguous")])
def test_an_unknown_empty_or_ambiguous_sku_is_refused_on_read_and_save(client, engine, sid, sku, code):
    for res in (client.get(url(sku, sid), headers=auth()), put(client, sku, sid)):
        assert res.status_code == 422 and res.json() == {"detail": code}
    with engine.begin() as c:
        assert c.execute(select(outbox)).all() == []


def test_nothing_is_stored_for_an_unknown_sku(client, engine, sid):
    put(client, "SYN-NO-EXISTE", sid)
    with engine.begin() as c:
        assert current_override_version(c, VARIANT, sid) == 0
        assert [r for r in c.execute(select(audit_events.c.action)).all() if r[0] == "terms.override_saved"] == []


def test_a_surrogate_id_product_resolves_and_the_id_is_not_returned(client, sid):
    assert put(client, "LOCAL-1", sid).json() == {"version": 1}
    assert "9000001" not in json.dumps(client.get(url("LOCAL-1", sid), headers=auth()).json())


def test_a_supplier_with_no_terms_gives_the_empty_view(client, sid):
    view = client.get(url(SKU, sid), headers=auth()).json()
    assert view["history"] == [] and view["override"] is None


def test_the_precondition_idempotency_and_roles_work_as_before(client, sid):
    assert put(client, SKU, sid, **{"Idempotency-Key": "k-1"}).json() == {"version": 1}
    replay = put(client, SKU, sid, **{"Idempotency-Key": "k-1"})
    assert replay.json() == {"version": 1} and replay.headers["idempotent-replay"] == "true"
    assert put(client, SKU, sid).status_code == 428
    stale = put(client, SKU, sid, **{"If-Match": '"0"'})
    assert stale.status_code == 412 and stale.json()["current_version"] == 1
    assert put(client, SKU, sid, {"lead_time_days": 6}, **{"If-Match": '"1"'}).json() == {"version": 2}
    refused = put(client, SKU, sid, role="viewer")
    assert refused.status_code == 403 and refused.json() == {"detail": "auth_forbidden_role"}


def test_the_stored_pair_stays_keyed_by_the_variant_id_internally(client, engine, sid):
    put(client, SKU, sid)
    with engine.begin() as c:
        assert current_override_version(c, VARIANT, sid) == 1


def test_the_saved_audit_entry_shows_the_sku_and_not_the_variant_id(client, engine, sid):
    put(client, SKU, sid)
    with engine.begin() as c:
        rows = c.execute(select(audit_events.c.action, audit_events.c.entity_id, audit_events.c.before, audit_events.c.after)).all()
        assert verify_chain(c)
    assert [r[1] for r in rows if r[0] == "terms.override_saved"] == [f"{SKU}:{sid}"[:60]]
    assert str(VARIANT) not in json.dumps([[str(v) for v in r] for r in rows])
    # the refused-request entry is covered in test_terms_refusal_audit.py (it needs the two-connection engine)


def test_a_long_sku_is_cut_in_the_audit_entry_not_the_supplier_id(client, engine, sid):
    long_sku = "SYN-" + "L" * 36
    assert put(client, long_sku, sid).json() == {"version": 1}
    with engine.begin() as c:
        label = c.execute(select(audit_events.c.entity_id).where(audit_events.c.action == "terms.override_saved")).scalar_one()
    assert len(label) == 60 and label.endswith(f":{sid}") and label.startswith("SYN-LLL")


def test_logs_hold_no_variant_id(client, sid, caplog):
    with caplog.at_level(logging.DEBUG):
        put(client, SKU, sid)
        put(client, SKU, sid)
        client.get(url("SYN-NO-EXISTE", sid), headers=auth())
    assert str(VARIANT) not in caplog.text


def test_the_change_event_key_is_internal_and_unchanged(client, engine, sid, tmp_path):
    class Blob:
        def put(self, name, data):
            p = tmp_path / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            return p.as_uri()

    client.app.state.blob_writer = Blob()
    put(client, SKU, sid)
    payload = json.loads(next(tmp_path.rglob("*.json")).read_text())
    assert payload["scope"] == "product_supplier_terms" and payload["key"] == f"{VARIANT}:{sid}"


def test_the_old_variant_id_path_is_gone(client, sid):
    # a number is just a SKU now: it is refused as unknown instead of being read as a variant id
    assert client.get(url(str(VARIANT), sid), headers=auth()).json() == {"detail": "sku_unknown"}
