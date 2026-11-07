"""T055: a saved terms version is announced through the transactional outbox with references only, never with the values."""

import json

from conftest import add_supplier, auth
from db.tables import outbox
from sqlalchemy import select

BODY = {"lead_time_days": 3, "delivery_charge": "9.50", "payment_terms_days": 30}


class Blob:
    def __init__(self, tmp):
        self.tmp, self.names = tmp, []

    def put(self, name, data):
        p = self.tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        self.names.append(name)
        return p.as_uri()


def sid_of(engine):
    with engine.begin() as c:
        return add_supplier(c, 1, "Proveedor Sintético A")


def events(engine):
    with engine.connect() as c:
        return [r for r in c.execute(select(outbox)).all()]


def test_saving_supplier_terms_queues_one_event_with_references_only(client, engine, tmp_path):
    client.app.state.blob_writer = Blob(tmp_path)
    sid = sid_of(engine)
    assert client.put(f"/suppliers/{sid}/terms", json=BODY, headers=auth("buyer")).json() == {"version": 1}
    rows = events(engine)
    assert len(rows) == 1 and rows[0].type == "procurement.terms.changed.v1"
    payload = json.loads(next(tmp_path.rglob("*.json")).read_text())
    assert payload == {"scope": "supplier_terms", "key": sid, "version": 1}
    assert "9.50" not in json.dumps(payload) and "lead_time" not in json.dumps(payload)


def test_saving_a_product_override_queues_an_event_with_the_pair_as_key(client, engine, tmp_path):
    client.app.state.blob_writer = Blob(tmp_path)
    sid = sid_of(engine)
    client.put(f"/product-suppliers/9001/{sid}/terms", json={"pack_multiple": 12}, headers=auth("buyer"))
    payload = json.loads(next(tmp_path.rglob("*.json")).read_text())
    assert payload == {"scope": "product_supplier_terms", "key": f"9001:{sid}", "version": 1}


def test_a_refused_save_queues_nothing(client, engine, tmp_path):
    client.app.state.blob_writer = Blob(tmp_path)
    sid = sid_of(engine)
    assert client.put(f"/suppliers/{sid}/terms", json={"delivery_charge": "-1"}, headers=auth("buyer")).status_code == 422
    assert events(engine) == []


def test_without_a_blob_writer_the_save_still_succeeds_and_no_event_is_queued(client, engine):
    sid = sid_of(engine)
    assert client.put(f"/suppliers/{sid}/terms", json=BODY, headers=auth("buyer")).status_code == 200
    assert events(engine) == []
