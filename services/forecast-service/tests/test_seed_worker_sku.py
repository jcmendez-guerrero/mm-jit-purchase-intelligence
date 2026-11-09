"""MMI-7 T060: the worker builds the SKU map from the inventory series (`sku` per item) and validates a queued SKU file with it."""

import seed_fixtures as sf
from conftest import KNOWN, export_series
from db.tables import seed_datasets
from seeds.jobs import enqueue_validation
from seeds.lifecycle import register_upload
from sqlalchemy import select
from tests_helpers import FakeSource
from upload_settings import ParseLimits
from worker import process_imports

L = ParseLimits()


def queue(engine, store):
    with engine.begin() as c:
        up = register_upload(c, store, "datos.csv", sf.static("valid.csv"), "Hoja", "buyer-1", L)
        enqueue_validation(c, up["id"], up["suggested_mapping"], "buyer-1")
    return up["id"]


def test_the_worker_resolves_skus_from_the_series_the_inventory_service_exports(engine, store, monkeypatch):
    monkeypatch.setattr("seeds.store.make_seed_store", lambda: store)
    dataset = queue(engine, store)
    source = FakeSource({"series": [export_series(v, [1] * 20, "new", False, ["new"]) for v in sorted(KNOWN)]})         # each item carries sku = EJ-<variant>
    assert process_imports(engine, source)["done"] == 1
    with engine.connect() as c:
        ds = c.execute(select(seed_datasets).where(seed_datasets.c.id == dataset)).one()
    assert ds.status == "validated" and ds.accepted_count == 5 and ds.quarantined_count == 0


def test_without_a_sku_in_the_series_every_row_is_quarantined_not_guessed(engine, store, monkeypatch):
    monkeypatch.setattr("seeds.store.make_seed_store", lambda: store)
    dataset = queue(engine, store)
    items = [{k: v for k, v in export_series(v, [1] * 20, "new", False, ["new"]).items() if k != "sku"} for v in sorted(KNOWN)]
    assert process_imports(engine, FakeSource({"series": items}))["done"] == 1
    with engine.connect() as c:
        ds = c.execute(select(seed_datasets).where(seed_datasets.c.id == dataset)).one()
    assert ds.accepted_count == 0 and ds.quarantined_count == 5


def test_an_empty_queue_does_not_ask_inventory_for_its_export(engine):
    class Boom:
        def fetch(self):
            raise AssertionError("inventory must not be called")

    assert process_imports(engine, Boom()) == {"processed": 0, "done": 0, "failed": 0, "deferred": 0}


def test_a_queued_job_still_waits_when_inventory_is_unavailable(engine, store):
    queue(engine, store)

    class Down:
        def fetch(self):
            raise RuntimeError("down")

    assert process_imports(engine, Down())["deferred"] == 1
