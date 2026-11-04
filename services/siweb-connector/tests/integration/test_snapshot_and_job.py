"""Reference-list syncs and the job entrypoint (T045)."""

import job
from db.tables import metadata, outbox, sync_runs
from fastapi.testclient import TestClient
from siweb_mock.app import create_app
from siweb_mock.state import TOKEN
from sqlalchemy import create_engine, select
from sync.snapshot import SnapshotSync


def test_full_lists_reconcile_and_are_announced(make_reader, engine, store):
    reader, app = make_reader()
    data = app.state.mock.data
    expect = {"warehouses": len(data.warehouses), "products": len([p for p in data.products if p["status"] == "active"]),
              "variants": len(data.variants)}
    for kind, n in expect.items():
        res = SnapshotSync(reader, engine, store, kind).run()
        assert res.status == "committed" and res.reconciled and res.fetched == n
    with engine.connect() as c:
        assert len(c.execute(select(outbox)).all()) == 3


def test_partial_list_is_not_announced_or_reconciled(make_reader, engine, store):
    reader, _ = make_reader(per_hour=2)  # 200 variants per page: the list needs more requests than the budget
    res = SnapshotSync(reader, engine, store, "variants").run()
    assert res.status == "partial" and not res.reconciled
    with engine.connect() as c:
        assert c.execute(select(outbox)).all() == []
        assert c.execute(select(sync_runs.c.status)).scalar_one() == "partial"


def test_job_runs_all_kinds_against_the_mock(monkeypatch, tmp_path):
    app = create_app()
    db = tmp_path / "job.db"
    eng = create_engine(f"sqlite:///{db}")
    metadata.create_all(eng)
    monkeypatch.setenv("MMI_SIWEB_BASE_URL", "http://mock.test")
    monkeypatch.setenv("MMI_ALLOW_HTTP", "1")
    monkeypatch.setenv("MMI_DATABASE_URL", f"sqlite:///{db}")
    monkeypatch.setenv("MMI_BLOB_ROOT", str(tmp_path / "blobs"))
    monkeypatch.setenv("MMI_SIWEB_TOKEN", TOKEN)
    monkeypatch.setattr(job.httpx, "Client", lambda **kw: TestClient(app, base_url="http://mock.test"))
    assert job.run(list(job.KINDS), enforce_window=False) == 0
    with eng.connect() as c:
        assert sorted(r.kind for r in c.execute(select(sync_runs)).all()) == ["movements", "products", "variants", "warehouses"]


def test_job_exits_non_zero_when_the_token_is_rejected(monkeypatch, tmp_path):
    app = create_app()
    db = tmp_path / "job.db"
    eng = create_engine(f"sqlite:///{db}")
    metadata.create_all(eng)
    for k, v in {"MMI_SIWEB_BASE_URL": "http://mock.test", "MMI_ALLOW_HTTP": "1", "MMI_DATABASE_URL": f"sqlite:///{db}",
                 "MMI_BLOB_ROOT": str(tmp_path / "b"), "MMI_SIWEB_TOKEN": "wrong"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(job.httpx, "Client", lambda **kw: TestClient(app, base_url="http://mock.test"))
    assert job.run(["warehouses"], enforce_window=False) == 1
    with eng.connect() as c:
        assert c.execute(select(sync_runs.c.status)).scalar_one() == "failed"


def test_job_rejects_unknown_kind():
    assert job.main(["job", "everything"]) == 2


def test_job_logs_the_markers_the_alerts_query(monkeypatch, tmp_path, caplog):
    import logging

    app = create_app()
    db = tmp_path / "m.db"
    metadata.create_all(create_engine(f"sqlite:///{db}"))
    for k, v in {"MMI_SIWEB_BASE_URL": "http://mock.test", "MMI_ALLOW_HTTP": "1", "MMI_DATABASE_URL": f"sqlite:///{db}",
                 "MMI_BLOB_ROOT": str(tmp_path / "b"), "MMI_SIWEB_TOKEN": TOKEN, "MMI_SIWEB_REQUESTS_PER_HOUR": "2"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(job.httpx, "Client", lambda **kw: TestClient(app, base_url="http://mock.test"))
    with caplog.at_level(logging.INFO, logger="siweb-connector.job"):
        job.run(["warehouses", "variants"], enforce_window=False)
    text = caplog.text
    assert "SYNC_OK kind=warehouses" in text and "QUOTA_DENIED kind=variants" in text
    monkeypatch.setenv("MMI_SIWEB_TOKEN", "wrong")
    with caplog.at_level(logging.INFO, logger="siweb-connector.job"):
        job.run(["warehouses"], enforce_window=False)
    assert "SYNC_FAILED" in caplog.text
