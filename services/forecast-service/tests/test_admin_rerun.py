"""T149 (forecast part): permitted re-runs are idempotent, restricted to buyer/admin and audited."""

from datetime import UTC, datetime

import pytest
import seed_fixtures as sf
from conftest import KNOWN, FileStore, export_series
from db.tables import audit_events, forecast_runs, import_jobs
from fastapi.testclient import TestClient
from imports_api import build_router, get_engine
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app
from seeds.jobs import enqueue_validation, rerun_job
from seeds.lifecycle import LifecycleError, register_upload
from sqlalchemy import func, select, update
from tests_helpers import FakeSource, NullWriter
from upload_settings import ParseLimits

L = ParseLimits()
NOW = datetime(2026, 11, 9, 9, tzinfo=UTC)


def failed_job(engine, store):
    with engine.begin() as c:
        up = register_upload(c, store, "datos.csv", sf.static("valid.csv"), "Hoja", "buyer-1", L, NOW)
        jid = enqueue_validation(c, up["id"], up["suggested_mapping"], "buyer-1", now=NOW)["job_id"]
        c.execute(update(import_jobs).where(import_jobs.c.id == jid).values(state="failed", error_key="import_failed"))
    return jid


def audit_actions(engine):
    with engine.connect() as c:
        return [r.action for r in c.execute(select(audit_events).order_by(audit_events.c.id)).all()]


def test_a_failed_job_is_requeued_once_with_its_inputs_and_the_second_call_reuses_it(engine, store):
    jid = failed_job(engine, store)
    with engine.begin() as c:
        before = c.execute(select(func.count()).select_from(import_jobs)).scalar_one()
        a = rerun_job(c, jid, "admin-1", now=NOW)
    with engine.begin() as c:
        b = rerun_job(c, jid, "admin-1", now=NOW)
        n = c.execute(select(func.count()).select_from(import_jobs)).scalar_one() - before
        queued = c.execute(select(import_jobs).where(import_jobs.c.id == a["job_id"])).one()
    assert a["reused"] is False and b["reused"] is True and a["job_id"] == b["job_id"] and n == 1
    assert queued.params["column_map"] and queued.requested_by == "admin-1"
    assert audit_actions(engine).count("import.job_rerun") == 1


def test_only_failed_validation_jobs_can_be_rerun(engine, store):
    jid = failed_job(engine, store)
    with engine.begin() as c:
        c.execute(update(import_jobs).where(import_jobs.c.id == jid).values(state="done", error_key=None))
        with pytest.raises(LifecycleError) as e:
            rerun_job(c, jid, "admin-1")
        assert e.value.code == "import_job_not_rerunnable"
        with pytest.raises(LifecycleError) as e2:
            rerun_job(c, "nope", "admin-1")
        assert e2.value.code == "import_unknown_job"


class V:
    def validate(self, token, required_roles=()):
        roles = {"admin": {"viewer", "admin"}, "buyer": {"viewer", "buyer"}}.get(token, {"viewer"})
        if not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        return Principal(f"user-{token}", frozenset(roles), None)


@pytest.fixture
def api(engine, tmp_path):
    from api import build_router as run_router
    from api import get_engine as run_engine

    app = create_service_app("forecast-service", validator=V())
    app.include_router(build_router(app))
    app.include_router(run_router(app))
    app.state.series_source = FakeSource({"series": [export_series(v, [1] * 20, "new", False, ["new"]) for v in sorted(KNOWN)]})
    app.state.blob_writer = NullWriter(tmp_path)
    app.state.seed_store = FileStore(tmp_path)
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[run_engine] = lambda: engine
    return TestClient(app)


def h(role):
    return {"Authorization": f"Bearer {role}"}


def test_job_rerun_route_is_for_buyers_and_admins_only(api, engine, store):
    jid = failed_job(engine, store)
    assert api.post(f"/imports/jobs/{jid}/rerun", headers=h("viewer")).status_code == 403
    ok = api.post(f"/imports/jobs/{jid}/rerun", headers=h("admin"))
    assert ok.status_code == 202 and ok.json()["reused"] is False
    assert api.post("/imports/jobs/zzz/rerun", headers=h("admin")).json() == {"detail": "import_unknown_job"}


def test_an_admin_can_rerun_the_forecast_and_the_second_call_reuses_the_run(api, engine):
    assert api.post("/runs", headers=h("viewer")).status_code == 403
    first = api.post("/runs", headers=h("admin"))
    again = api.post("/runs", headers=h("admin"))
    assert first.status_code == again.status_code == 202 and again.json()["reused"] is True and first.json()["run_id"] == again.json()["run_id"]
    with engine.connect() as c:
        assert c.execute(select(func.count()).select_from(forecast_runs)).scalar_one() == 1
    assert audit_actions(engine).count("forecast.rerun") == 2
