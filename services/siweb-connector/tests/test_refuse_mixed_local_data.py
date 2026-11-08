"""T093 (FR-038, R17): the connector never mixes locally loaded data with the real ERP."""

import pytest
from db.tables import external_mappings, sync_checkpoints
from mixing_guard import (
    LOCAL_MOVEMENT_ID_FLOOR,
    LocalDataPresentError,
    assert_no_local_data,
    local_data_present,
    mark_local_data,
)
from sqlalchemy import insert

REAL = "https://api.example-erp.test"
MOCK = "http://siweb-mock:8089"


def test_an_empty_database_may_talk_to_the_real_erp(engine):
    assert not local_data_present(engine)
    assert_no_local_data(engine, REAL)


def test_the_marker_blocks_the_real_erp_until_it_is_cleared(engine):
    mark_local_data(engine)
    mark_local_data(engine)                                     # idempotent
    assert local_data_present(engine)
    with pytest.raises(LocalDataPresentError) as exc:
        assert_no_local_data(engine, REAL)
    assert exc.value.code == "local_data_present"


def test_a_checkpoint_from_loader_made_movement_ids_also_blocks(engine):
    with engine.begin() as c:
        c.execute(insert(sync_checkpoints).values(kind="movements", last_movement_id=LOCAL_MOVEMENT_ID_FLOOR + 1))
    with pytest.raises(LocalDataPresentError):
        assert_no_local_data(engine, REAL)


def test_real_erp_sized_checkpoints_do_not_block(engine):
    with engine.begin() as c:
        c.execute(insert(sync_checkpoints).values(kind="movements", last_movement_id=250_000))
    assert_no_local_data(engine, REAL)


@pytest.mark.parametrize("base", [MOCK, "http://localhost:8089", "http://127.0.0.1:8089"])
def test_local_data_may_talk_to_the_mock(engine, base):
    mark_local_data(engine)
    assert_no_local_data(engine, base)


def test_the_marker_is_a_plain_mapping_row(engine):
    mark_local_data(engine)
    with engine.connect() as c:
        rows = c.execute(external_mappings.select()).all()
    assert [(r.entity, r.external_id) for r in rows] == [("local_data", "loaded")]


def test_the_job_refuses_before_any_request(engine, monkeypatch, tmp_path):
    import job

    mark_local_data(engine)
    monkeypatch.setenv("MMI_SIWEB_BASE_URL", REAL)
    monkeypatch.setenv("MMI_DATABASE_URL", "sqlite://")
    monkeypatch.setenv("MMI_SIWEB_TOKEN", "synthetic")
    monkeypatch.setenv("MMI_IGNORE_NIGHT_WINDOW", "1")
    monkeypatch.setenv("MMI_BLOB_ROOT", str(tmp_path))
    monkeypatch.setattr(job, "create_engine", lambda _url: engine)
    monkeypatch.setattr(job, "relay_events", lambda *_a, **_k: 0)

    class NoRequests:
        def __init__(self, **_kw):
            pass

        def __getattr__(self, name):
            raise AssertionError(f"no request may be made: {name}")

    monkeypatch.setattr(job, "ReaderClient", NoRequests)
    assert job.run(["movements"]) == 1
