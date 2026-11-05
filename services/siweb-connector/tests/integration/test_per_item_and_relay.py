"""T146 / T149: lots and supplier-cost collection across nights, and the connector relaying its events."""

import json

import job
from db.tables import metadata, outbox, sync_checkpoints, sync_runs
from fastapi.testclient import TestClient
from mmi_common.bus import InMemoryBus
from siweb_mock.app import create_app
from siweb_mock.state import TOKEN
from sqlalchemy import create_engine, select
from sync.per_item import PerItemSync


def run_night(make_reader, engine, store, kind, budget, app_holder=None):
    reader, app = make_reader(per_hour=budget)
    return PerItemSync(reader, engine, store, kind).run(), reader, app


def payload(store, engine):
    from db.tables import raw_payload_index

    with engine.connect() as c:
        return [json.loads(store.get(r.blob_uri)) for r in c.execute(select(raw_payload_index).order_by(raw_payload_index.c.fetched_at)).all()]


def test_lots_are_collected_across_nights_without_gaps_and_the_cycle_reconciles(make_reader, engine, store):
    results, seen = [], []
    for _ in range(40):
        res, _reader, app = run_night(make_reader, engine, store, "lots", budget=60)
        assert res.requests_used <= 60
        results.append(res)
        seen += res.record_ids
        if res.status == "committed":
            break
    all_variants = {v["id"] for v in app.state.mock.data.variants}
    assert len(results) >= 3 and results[-1].reconciled and [r.status for r in results[:-1]] == ["partial"] * (len(results) - 1)
    assert sorted(seen) == sorted(all_variants) and len(seen) == len(set(seen))
    docs = payload(store, engine)
    assert all(d["kind"] == "lots" for d in docs) and sum(len(d["records"]) for d in docs) >= len(all_variants)
    with engine.connect() as c:
        assert c.execute(select(sync_checkpoints.c.backfill_cursor).where(sync_checkpoints.c.kind == "lots")).scalar_one() is None      # next cycle starts fresh


def test_variants_without_lots_are_reported_so_inventory_can_clear_old_ones(make_reader, engine, store):
    res, _, app = run_night(make_reader, engine, store, "lots", budget=100_000)
    docs = payload(store, engine)
    with_lots = {lot["variant_id"] for lot in app.state.mock.data.lots}
    marked = {r["variant_id"] for r in docs[0]["records"] if r.get("quantity") == 0 and "batch_number" not in r}
    assert marked == {v["id"] for v in app.state.mock.data.variants} - with_lots and res.reconciled


def test_supplier_rows_are_collected_with_the_tax_identifier_stripped_before_storage(make_reader, engine, store):
    reader, app = make_reader(per_hour=100_000)
    app.state.mock.suppliers[1] = [{"id": 1, "product_id": 1, "contact_id": 9, "supplier_name": "Proveedor Sintetico", "supplier_cif": "A00000000",
                                    "purchase_cost_cents": 1000, "currency": "EUR", "lead_time_days": 3, "min_order_qty": 2, "is_preferred": True}]
    res = PerItemSync(reader, engine, store, "supplier_costs").run()
    blob = json.dumps(payload(store, engine))
    assert res.status == "committed" and "supplier_cif" not in blob and "A00000000" not in blob and '"contact_id": 9' in blob and '"product_id": 1' in blob


def test_a_second_cycle_starts_again_from_the_beginning(make_reader, engine, store):
    first, _, _ = run_night(make_reader, engine, store, "supplier_costs", budget=100_000)
    second, _, _ = run_night(make_reader, engine, store, "supplier_costs", budget=100_000)
    assert first.record_ids == second.record_ids and second.reconciled


def test_the_job_relays_committed_events_to_every_subscriber(monkeypatch, tmp_path):
    app = create_app()
    db = tmp_path / "j.db"
    eng = create_engine(f"sqlite:///{db}")
    metadata.create_all(eng)
    for k, v in {"MMI_SIWEB_BASE_URL": "http://mock.test", "MMI_ALLOW_HTTP": "1", "MMI_DATABASE_URL": f"sqlite:///{db}", "MMI_BLOB_ROOT": str(tmp_path / "b"),
                 "MMI_SIWEB_TOKEN": TOKEN, "MMI_IGNORE_NIGHT_WINDOW": "1"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(job.httpx, "Client", lambda **kw: TestClient(app, base_url="http://mock.test"))
    bus = InMemoryBus()
    assert job.run(["warehouses", "products"], enforce_window=False, bus=bus) == 0
    assert bus.depth("inventory-in") == 2 and bus.depth("procurement-in") == 2
    with eng.connect() as c:
        assert all(r.status == "sent" for r in c.execute(select(outbox)).all()) and len(c.execute(select(sync_runs)).all()) == 2
    assert {m.body["type"] for m in bus.receive("inventory-in", 10)} == {"siweb.sync.completed.v1"}


def test_without_a_queue_the_events_stay_in_the_outbox_and_the_skip_is_logged(monkeypatch, tmp_path, caplog):
    import logging

    app = create_app()
    db = tmp_path / "k.db"
    eng = create_engine(f"sqlite:///{db}")
    metadata.create_all(eng)
    for k, v in {"MMI_SIWEB_BASE_URL": "http://mock.test", "MMI_ALLOW_HTTP": "1", "MMI_DATABASE_URL": f"sqlite:///{db}", "MMI_BLOB_ROOT": str(tmp_path / "b"),
                 "MMI_SIWEB_TOKEN": TOKEN}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("MMI_QUEUE_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("MMI_QUEUE_URL", raising=False)
    monkeypatch.setattr(job.httpx, "Client", lambda **kw: TestClient(app, base_url="http://mock.test"))
    with caplog.at_level(logging.WARNING, logger="siweb-connector.job"):
        job.run(["warehouses"], enforce_window=False)
    assert "RELAY_SKIPPED" in caplog.text
    with eng.connect() as c:
        assert [r.status for r in c.execute(select(outbox)).all()] == ["pending"]


def test_the_purge_kind_deletes_expired_payloads_without_any_erp_request(monkeypatch, tmp_path):
    from datetime import UTC, datetime, timedelta

    from db.tables import raw_payload_index
    from sqlalchemy import insert
    from storage.blob import LocalBlobStore

    app = create_app()
    db = tmp_path / "p.db"
    eng = create_engine(f"sqlite:///{db}")
    metadata.create_all(eng)
    store = LocalBlobStore(tmp_path / "blobs")
    now = datetime.now(UTC)
    uris = {}
    for rid, age in (("old", 120), ("new", 5)):
        fetched = now - timedelta(days=age)
        uris[rid] = store.put(f"raw/x/{rid}.json", b"{}", fetched + timedelta(days=90))
        with eng.begin() as c:
            c.execute(insert(sync_runs).values(id=rid, kind="x", status="committed", started_at=fetched))
            c.execute(insert(raw_payload_index).values(blob_uri=uris[rid], run_id=rid, sha256="0" * 64, fetched_at=fetched, expires_at=fetched + timedelta(days=90)))
    for k, v in {"MMI_SIWEB_BASE_URL": "http://mock.test", "MMI_ALLOW_HTTP": "1", "MMI_DATABASE_URL": f"sqlite:///{db}", "MMI_BLOB_ROOT": str(tmp_path / "blobs"),
                 "MMI_SIWEB_TOKEN": TOKEN}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(job.httpx, "Client", lambda **kw: TestClient(app, base_url="http://mock.test"))
    assert job.run(["purge"], enforce_window=False, bus=InMemoryBus()) == 0
    assert not store.exists(uris["old"]) and store.exists(uris["new"]) and app.state.mock.request_log == []
