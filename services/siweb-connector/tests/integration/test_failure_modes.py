"""T121: Integration tests for connector failure modes: quota denials back off and alert, no partial data promoted."""


import job
from db.tables import metadata, outbox, sync_runs
from fastapi.testclient import TestClient
from siweb_mock.app import create_app
from siweb_mock.state import TOKEN
from sqlalchemy import create_engine, select
from sync.snapshot import SnapshotSync


def test_quota_denial_backs_off_and_logs_marker(make_reader, engine, store, caplog):
    # Set a very low budget (1 request) so quota denial is triggered
    reader, _app = make_reader(per_hour=1)
    res = SnapshotSync(reader, engine, store, "variants").run()

    # Must be marked partial, not reconciled
    assert res.status == "partial"
    assert not res.reconciled

    # Outbox must remain empty (no downstream event announced)
    with engine.connect() as c:
        assert c.execute(select(outbox)).all() == []
        assert c.execute(select(sync_runs.c.status)).scalar_one() == "partial"


def test_failed_sync_promotes_no_data_and_logs_sync_failed(monkeypatch, tmp_path, caplog):
    import client.reader as reader_mod
    monkeypatch.setattr(reader_mod.time, "sleep", lambda s: None)

    app = create_app()
    db = tmp_path / "failure_job.db"
    eng = create_engine(f"sqlite:///{db}")
    metadata.create_all(eng)

    for k, v in {
        "MMI_SIWEB_BASE_URL": "http://mock.test",
        "MMI_ALLOW_HTTP": "1",
        "MMI_DATABASE_URL": f"sqlite:///{db}",
        "MMI_BLOB_ROOT": str(tmp_path / "b"),
        "MMI_SIWEB_TOKEN": TOKEN,
    }.items():
        monkeypatch.setenv(k, v)

    # Injected 500 error on reader client
    def failing_client(**kw):
        tc = TestClient(app, base_url="http://mock.test")
        original_get = tc.get

        def mock_get(url, **get_kw):
            if "warehouses" in url:
                from httpx import Response
                return Response(500, request=None, text="Internal Server Error")
            return original_get(url, **get_kw)

        tc.get = mock_get  # type: ignore
        return tc

    monkeypatch.setattr(job.httpx, "Client", failing_client)

    exit_code = job.run(["warehouses"], enforce_window=False)
    assert exit_code != 0, "Job must exit with non-zero status on error"
    assert "SYNC_FAILED" in caplog.text

    # Verify no events promoted in outbox
    with eng.connect() as c:
        assert c.execute(select(outbox)).all() == []
