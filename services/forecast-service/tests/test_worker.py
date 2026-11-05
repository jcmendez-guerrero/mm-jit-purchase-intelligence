"""T146 / T148: forecast-in consumption, the read API and the worker pass."""

import json
import uuid

import api
import pytest
from conftest import export_series
from db.tables import forecast_runs, outbox
from fastapi.testclient import TestClient
from mmi_common.bus import POISON_SUFFIX, InMemoryBus, new_envelope
from mmi_common.service import create_service_app
from runs.consumer import consume_once
from runs.sources import LocalBlobWriter
from sqlalchemy import func, select
from tests_helpers import FakeSource
from worker import FileBlobs, run_once


def announce(bus, tmp_path, type_="inventory.demand.updated.v1", body=None):
    data = json.dumps(body or {"through_day": "2026-10-31", "series_count": 5}).encode()
    p = tmp_path / f"{uuid.uuid4()}.json"
    p.write_bytes(data)
    env = new_envelope(type_, "2026-10-31", data, p.as_uri(), str(uuid.uuid4()))
    bus.send("forecast-in", env)
    return env


def test_a_demand_update_starts_a_forecast_run_and_the_result_is_relayed(engine, make_export, tmp_path):
    bus = InMemoryBus()
    announce(bus, tmp_path)
    out = run_once(engine, bus, FileBlobs(), FakeSource(make_export()), LocalBlobWriter(tmp_path / "ev"))
    assert out["applied"] == 1 and out["relayed"] == 1 and out["failed"] == 0
    assert bus.depth("procurement-in") == 1 and bus.receive("procurement-in", 1)[0].body["type"] == "forecast.completed.v1"
    with engine.connect() as c:
        assert c.execute(select(func.count()).select_from(forecast_runs)).scalar_one() == 1
        assert all(r.status == "sent" for r in c.execute(select(outbox)).all())


def test_repeated_triggers_with_identical_inputs_do_not_repeat_the_run(engine, make_export, tmp_path):
    bus = InMemoryBus()
    for _ in range(3):
        announce(bus, tmp_path)
    run_once(engine, bus, FileBlobs(), FakeSource(make_export()), LocalBlobWriter(tmp_path / "ev"))
    with engine.connect() as c:
        assert c.execute(select(func.count()).select_from(forecast_runs)).scalar_one() == 1 and c.execute(select(func.count()).select_from(outbox)).scalar_one() == 1


def test_snapshot_events_are_acknowledged_without_a_run_and_other_types_are_poisoned(engine, make_export, tmp_path):
    bus = InMemoryBus()
    announce(bus, tmp_path, "inventory.snapshot.created.v1", {"snapshot_date": "2026-11-01", "variant_count": 3})
    announce(bus, tmp_path, "procurement.proposal.generated.v1", {"proposal_id": "p", "week": "2026-W45", "version": 1})
    stats = consume_once(engine, bus, FileBlobs(), FakeSource(make_export()), LocalBlobWriter(tmp_path / "ev"))
    assert stats.applied == 1 and stats.rejected == 1 and bus.depth("forecast-in" + POISON_SUFFIX) == 1
    with engine.connect() as c:
        assert c.execute(select(func.count()).select_from(forecast_runs)).scalar_one() == 0


def test_a_failing_inventory_export_leaves_the_trigger_for_retry(engine, tmp_path):
    class Down:
        def fetch(self):
            raise ConnectionError("inventory-service unavailable")

    bus = InMemoryBus()
    announce(bus, tmp_path)
    stats = consume_once(engine, bus, FileBlobs(), Down(), LocalBlobWriter(tmp_path / "ev"))
    assert stats.failed == 1 and bus.depth("forecast-in") == 1


class _V:
    def validate(self, token, required_roles=()):
        from mmi_common.auth import Principal

        return Principal("svc", frozenset({"viewer"}), None)


@pytest.fixture
def client(engine):
    app = create_service_app("forecast-service", validator=_V())
    app.include_router(api.build_router(app))
    app.dependency_overrides[api.get_engine] = lambda: engine
    return TestClient(app)


def test_latest_forecast_api_returns_values_per_variant_and_horizon(client, engine, make_export, tmp_path):
    assert client.get("/forecasts/latest", headers={"Authorization": "Bearer x"}).status_code == 404
    bus = InMemoryBus()
    announce(bus, tmp_path)
    run_once(engine, bus, FileBlobs(), FakeSource(make_export(n_smooth=2)), LocalBlobWriter(tmp_path / "ev"))
    body = client.get("/forecasts/latest", headers={"Authorization": "Bearer x"}).json()
    assert body["total"] == 4 and body["eligible"] == 2 and set(body["variants"]) == {"1", "2", "100", "101"}
    ok, bad = body["variants"]["1"], body["variants"]["100"]
    assert ok["eligible"] and ok["horizons"]["14"]["mean"] > 0 and "0.95" in ok["horizons"]["14"]["quantiles"]
    assert not bad["eligible"] and bad["reasons"] == ["new"] and bad["horizons"]["14"]["mean"] is None and set(bad["horizons"]["14"]["quantiles"]) == {"min", "max"}
    assert export_series  # builder re-exported for parity with the other tests
