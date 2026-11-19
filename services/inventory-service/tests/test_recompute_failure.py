"""T019a, T095: a recompute that fails half way leaves no partial rows and no "completed" audit record, and a retry is idempotent (FR-022).

There is no recompute button in the web app (it is a gateway call), so there is no screen to show a failure reason on; the gateway turns the 5xx into its error response.
"""

from api import quality as quality_api
from audit import CLASSES_RECOMPUTED
from conftest import auth
from db.tables import anomaly_flags, audit_events, data_quality_snapshot, product_segments
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_quality_api import seed_case

TABLES = (data_quality_snapshot, anomaly_flags, product_segments)


def counts(engine):
    with engine.connect() as c:
        rows = {t.name: c.execute(select(func.count()).select_from(t)).scalar() for t in TABLES}
        rows["completed_audits"] = c.execute(select(func.count()).select_from(audit_events).where(audit_events.c.action == CLASSES_RECOMPUTED)).scalar()
    return rows


def test_a_failed_recompute_leaves_nothing_behind_and_a_retry_completes_once(client, engine, monkeypatch):
    seed_case(engine, "smooth")
    empty = counts(engine)
    written_before_failure = {}

    def fail_after_the_snapshots(conn):                                  # the snapshots are already written in this transaction when the classes step runs
        written_before_failure["snapshots"] = conn.execute(select(func.count()).select_from(data_quality_snapshot)).scalar()
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(quality_api, "compute_segments", fail_after_the_snapshots)
    failing = TestClient(client.app, raise_server_exceptions=False)
    assert failing.post("/quality/recompute", headers=auth("buyer")).status_code == 500
    assert written_before_failure["snapshots"] > 0                       # the failure really came half way, so the next check proves a rollback
    assert counts(engine) == empty                                       # no snapshot, flag, class or "completed" audit record from the failed run

    monkeypatch.undo()
    first = client.post("/quality/recompute", headers=auth("buyer")).json()
    done = counts(engine)
    second = client.post("/quality/recompute", headers=auth("buyer")).json()
    assert first["status"] == "completed" and first["job_id"] == second["job_id"]
    after = counts(engine)
    assert {k: v for k, v in after.items() if k != "completed_audits"} == {k: v for k, v in done.items() if k != "completed_audits"}   # same inputs, no duplicate rows
    assert done["completed_audits"] == 1
