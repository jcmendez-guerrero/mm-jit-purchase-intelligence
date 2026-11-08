"""T114: large files are validated in the background; the buyer is told, can check the status, and a re-run is safe."""

from datetime import UTC, datetime, timedelta

import pytest
import seed_fixtures as sf
from conftest import KNOWN, FileStore, export_series
from db.tables import import_jobs, seed_datasets
from fastapi.testclient import TestClient
from imports_api import build_router, get_engine
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app
from seeds import jobs as jobs_mod
from seeds.jobs import enqueue_validation, list_jobs, process_queued
from seeds.lifecycle import register_upload
from sqlalchemy import select, update
from tests_helpers import FakeSource
from upload_settings import ParseLimits

L = ParseLimits()
NOW = datetime(2026, 11, 9, 9, tzinfo=UTC)


def upload(conn, store, data=None):
    return register_upload(conn, store, "datos.csv", data or sf.static("valid.csv"), "Hoja", "buyer-1", L, NOW)


def test_the_upload_records_the_row_count(conn, store):
    up = upload(conn, store)
    assert conn.execute(select(seed_datasets.c.row_count)).scalar() == up["row_count"] == 5


def test_enqueue_is_idempotent_while_a_job_is_queued_or_running(conn, store):
    up = upload(conn, store)
    a = enqueue_validation(conn, up["id"], up["suggested_mapping"], "buyer-1", now=NOW)
    b = enqueue_validation(conn, up["id"], up["suggested_mapping"], "buyer-1", now=NOW)
    assert a["job_id"] == b["job_id"] and b["reused"] is True and a["state"] == "queued"


def test_the_worker_validates_the_file_and_records_the_job_without_file_content(engine, store):
    with engine.begin() as c:
        up = upload(c, store)
        enqueue_validation(c, up["id"], up["suggested_mapping"], "buyer-1", now=NOW)
    out = process_queued(engine, store, KNOWN, L, now=NOW)
    assert out == {"processed": 1, "done": 1, "failed": 0}
    with engine.connect() as c:
        ds = c.execute(select(seed_datasets)).one()
        job = c.execute(select(import_jobs).where(import_jobs.c.stage == "validate")).one()
    assert ds.status == "validated" and ds.accepted_count == 5 and job.state == "done" and job.error_key is None and job.finished_at is not None
    assert "9001" not in str(job.params) and set(job.params) == {"column_map", "mapping_id"}
    assert process_queued(engine, store, KNOWN, L, now=NOW)["processed"] == 0                  # nothing left; running it again does nothing


def test_a_failing_job_is_recorded_with_its_code_and_does_not_block_the_next(engine, store):
    with engine.begin() as c:
        bad = upload(c, store, sf.static("mixed_origin.csv"))
        good = upload(c, store, sf.static("valid.csv").replace(b"2026-01-05", b"2026-01-06"))
        enqueue_validation(c, bad["id"], bad["suggested_mapping"], "buyer-1", now=NOW)
        enqueue_validation(c, good["id"], good["suggested_mapping"], "buyer-1", now=NOW + timedelta(seconds=1))
    out = process_queued(engine, store, KNOWN, L, now=NOW)
    assert out == {"processed": 2, "done": 1, "failed": 1}
    with engine.connect() as c:
        jobs = {j["dataset_id"]: j for j in list_jobs(c) if j["stage"] == "validate"}
    assert jobs[bad["id"]]["state"] == "failed" and jobs[bad["id"]]["error_key"] == "import_mixed_origin" and jobs[good["id"]]["state"] == "done"


def test_a_job_left_running_is_picked_up_again_and_a_failed_one_can_be_requeued(engine, store):
    with engine.begin() as c:
        up = upload(c, store)
        jid = enqueue_validation(c, up["id"], up["suggested_mapping"], "buyer-1", now=NOW)["job_id"]
        c.execute(update(import_jobs).where(import_jobs.c.id == jid).values(state="running", started_at=NOW - timedelta(hours=1)))
    assert process_queued(engine, store, KNOWN, L, now=NOW)["done"] == 1
    with engine.begin() as c:
        c.execute(update(import_jobs).where(import_jobs.c.id == jid).values(state="failed", error_key="import_failed"))
        again = enqueue_validation(c, up["id"], up["suggested_mapping"], "buyer-1", now=NOW)
    assert again["reused"] is False and again["job_id"] != jid                                  # a failed job is not reused: a new one is queued


class V:
    def validate(self, token, required_roles=()):
        roles = {"buyer": {"viewer", "buyer"}}.get(token, {"viewer"})
        if not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        return Principal(f"user-{token}", frozenset(roles), None)


@pytest.fixture
def api(engine, tmp_path):
    app = create_service_app("forecast-service", validator=V())
    app.include_router(build_router(app))
    app.state.series_source = FakeSource({"series": [export_series(v, [1] * 20, "new", False, ["new"]) for v in sorted(KNOWN)]})
    app.state.seed_store = FileStore(tmp_path)
    app.dependency_overrides[get_engine] = lambda: engine
    return TestClient(app)


def h(role="buyer"):
    return {"Authorization": f"Bearer {role}"}


def test_a_small_file_validates_in_the_request_a_large_one_returns_202_and_a_job(api, monkeypatch, engine):
    import io

    small = api.post("/imports", files={"file": ("a.csv", io.BytesIO(sf.static("valid.csv")))}, headers=h()).json()
    ok = api.post(f"/imports/{small['id']}/validate", json={"column_map": small["suggested_mapping"]}, headers=h())
    assert ok.status_code == 200 and ok.json()["accepted"] == 5
    monkeypatch.setattr("imports_api.SYNC_ROWS", 3)
    big = api.post("/imports", files={"file": ("b.csv", io.BytesIO(sf.static("valid.csv").replace(b"2026-01-05", b"2026-01-07")))}, headers=h()).json()
    queued = api.post(f"/imports/{big['id']}/validate", json={"column_map": big["suggested_mapping"]}, headers=h())
    assert queued.status_code == 202 and queued.json()["queued"] is True and queued.json()["rows"] == 5
    again = api.post(f"/imports/{big['id']}/validate", json={"column_map": big["suggested_mapping"]}, headers=h())
    assert again.json()["job_id"] == queued.json()["job_id"]
    status = api.get("/imports/jobs", headers=h("viewer")).json()
    validate = [j for j in status["jobs"] if j["stage"] == "validate" and j["dataset_id"] == big["id"]]
    assert validate[0]["state"] == "queued" and validate[0]["rows"] == 5
    assert api.get("/imports/jobs").status_code == 401
    process_queued(engine, api.app.state.seed_store, KNOWN, L)
    assert [j["state"] for j in api.get("/imports/jobs", headers=h("viewer")).json()["jobs"] if j["stage"] == "validate" and j["dataset_id"] == big["id"]] == ["done"]
    assert jobs_mod.SYNC_ROWS == 10_000


def test_queueing_still_refuses_a_bad_mapping_and_a_viewer(api, monkeypatch):
    import io

    monkeypatch.setattr("imports_api.SYNC_ROWS", 1)
    d = api.post("/imports", files={"file": ("a.csv", io.BytesIO(sf.static("valid.csv")))}, headers=h()).json()
    assert api.post(f"/imports/{d['id']}/validate", json={"column_map": {"Fecha": "day"}}, headers=h()).json()["detail"] == "import_missing_column"
    assert api.post(f"/imports/{d['id']}/validate", json={"column_map": d["suggested_mapping"]}, headers=h("viewer")).status_code == 403
