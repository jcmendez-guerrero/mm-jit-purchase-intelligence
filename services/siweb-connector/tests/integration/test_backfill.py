"""T031 backfill resumes across nights without gaps or duplicates and respects the request budget.
Also covers T038 (frozen date_to, dedupe, reconciliation), T041 (raw payload) and T042 (outbox event)."""

import json
from datetime import UTC, datetime

from db.tables import import_errors, outbox, raw_payload_index, sync_checkpoints, sync_runs
from siweb_mock.state import MockConfig
from sqlalchemy import select
from sync.runner import MovementSync

NOW = datetime(2026, 12, 31, 3, 0, tzinfo=UTC)  # after every synthetic movement


def night(make_reader, engine, store, budget, config=None, app=None, clock=NOW):
    reader, app2 = make_reader(config, per_hour=budget)
    return MovementSync(reader, engine, store, clock=lambda: clock, page_size=200), reader, app2


def expected_ids(app, date_to):
    return {m["id"] for m in app.state.mock.movements if m["created_at"][:10] <= date_to}


def test_backfill_resumes_across_nights_without_gaps_or_duplicates(make_reader, engine, store):
    results, app = [], None
    for _ in range(20):
        sync, reader, app = night(make_reader, engine, store, budget=8)
        res = sync.run()
        assert res.requests_used <= 8 and reader.bucket.used <= 8  # never exceeds the nightly budget
        results.append(res)
        if res.status == "committed":
            break
    assert len(results) >= 2 and results[-1].status == "committed"
    assert [r.status for r in results[:-1]] == ["partial"] * (len(results) - 1)
    all_ids = [i for r in results for i in r.record_ids]
    assert len(all_ids) == len(set(all_ids))  # no duplicates
    assert set(all_ids) == expected_ids(app, "2026-12-30")  # no gaps
    assert results[-1].reconciled and results[-1].siweb_total == len(all_ids)
    with engine.connect() as c:
        cp = c.execute(select(sync_checkpoints)).one()
        assert cp.last_movement_id == max(all_ids) and cp.backfill_cursor is None  # newest across ALL nights
        assert c.execute(select(sync_runs.c.status)).scalars().all().count("partial") == len(results) - 1


def test_incremental_run_fetches_only_new_movements(make_reader, engine, store):
    sync, _, _ = night(make_reader, engine, store, budget=10_000)
    first = sync.run()
    assert first.status == "committed" and first.reconciled
    sync2, _, _ = night(make_reader, engine, store, budget=10_000)
    second = sync2.run()
    assert second.record_ids == [] and second.fetched == second.known and second.reconciled


def test_frozen_date_to_ignores_movements_inserted_mid_run(make_reader, engine, store):
    now = datetime.now(UTC)  # inserted movements are stamped "today"; the frozen window ends yesterday
    sync, _, app = night(make_reader, engine, store, budget=10_000,
                              config=MockConfig(insert_after_movement_requests=1, insert_count=7), clock=now)
    res = sync.run()
    assert len(res.record_ids) == len(set(res.record_ids))
    today = now.astimezone().date().isoformat()
    inserted = [m["id"] for m in app.state.mock.movements if m["created_at"][:10] >= today]
    assert inserted and not set(inserted) & set(res.record_ids)
    assert res.reconciled


def test_temporary_page_failure_is_retried_without_gaps(make_reader, engine, store):
    sync, reader, app = night(make_reader, engine, store, budget=10_000, config=MockConfig(missing_pages={2}))
    res = sync.run()
    assert reader.retries == 1 and set(res.record_ids) == expected_ids(app, "2026-12-30") and res.reconciled


def test_raw_payload_is_stripped_indexed_with_retention_and_announced(make_reader, engine, store):
    sync, _, _ = night(make_reader, engine, store, budget=10_000)
    res = sync.run()
    with engine.connect() as c:
        idx = c.execute(select(raw_payload_index)).one()
        ob = c.execute(select(outbox)).one()
        run = c.execute(select(sync_runs)).one()
    blob = store.get(idx.blob_uri)
    doc = json.loads(blob)
    assert b'"notes"' not in blob and b"supplier_cif" not in blob and "IGNORE PREVIOUS" not in blob.decode()
    assert doc["reconciled"] is True and len(doc["records"]) == res.fetched
    assert (idx.expires_at - idx.fetched_at.replace(tzinfo=idx.expires_at.tzinfo)).days == 90
    env = ob.envelope
    assert env["type"] == "siweb.sync.completed.v1" and env["resource_id"] == run.id
    assert env["payload_ref"]["uri"] == idx.blob_uri and env["payload_ref"]["sha256"] == idx.sha256
    from mmi_common.bus import validate_envelope

    validate_envelope(env, now=datetime.now(UTC))


def test_quarantine_is_recorded_once_and_survives_resync(make_reader, engine, store):
    sync, _, app = night(make_reader, engine, store, budget=10_000)
    res = sync.run()
    truth = app.state.mock.data.truth
    with engine.connect() as c:
        rows = c.execute(select(import_errors)).all()
    blocking = {int(r.external_id) for r in rows if r.blocking}
    assert blocking == set(truth["unreferenced_sale_ids"]) | set(truth["malformed_expiry_ids"])
    assert res.errors == len(blocking) and res.stored + res.errors == res.fetched - res.known
    assert len({(r.external_id, r.error_code) for r in rows}) == len(rows)
