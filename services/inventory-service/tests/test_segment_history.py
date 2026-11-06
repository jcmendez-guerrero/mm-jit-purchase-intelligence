"""T077: the category is recomputed on every demand update; history keeps the reasons; criticality is never inferred."""

from datetime import date

from classification.criticality import set_critical
from classification.run import compute_segments, history_for
from conftest import auth
from db.tables import products, variants
from demand.rebuild import rebuild
from sqlalchemy import insert
from test_review_and_metrics import T, add, snapshot


def seed(engine):
    with engine.begin() as c:
        c.execute(insert(products).values(external_id=5, name="P", status="active", missed_syncs=0))
        c.execute(insert(variants).values(external_id=1, product_id=5, sku="SYN-1", name="V", pack_size=1, uom="unit"))
    add(engine, 1, "initial_stock", 100, T(1))
    for i in range(2, 7):
        add(engine, 10 + i, "sale_shipment", -3, T(i))
    snapshot(engine, 1, date(2026, 10, 8), 85)
    with engine.begin() as c:
        rebuild(c)
        compute_segments(c)


def test_the_first_classification_is_recorded_with_its_reason(engine):
    seed(engine)
    with engine.connect() as c:
        h = history_for(c, 1)
    assert [x["reason_key"] for x in h] == ["first_classification"] and h[0]["critical"] is False


def test_an_unchanged_category_adds_no_history_row(engine):
    seed(engine)
    with engine.begin() as c:
        compute_segments(c)
        compute_segments(c)
        assert len(history_for(c, 1)) == 1


def test_a_category_change_is_recorded_with_which_part_changed(engine):
    from datetime import UTC, datetime

    from classification.run import record_history

    seed(engine)
    base = {"variant_id": 1, "abc": "C", "xyz": "X", "pattern": "new"}
    now = datetime(2026, 11, 9, tzinfo=UTC)
    with engine.begin() as c:
        assert record_history(c, [{**base, "abc": "B"}], "run-2", now) == 1
        assert record_history(c, [{**base, "abc": "B", "xyz": "Y"}], "run-3", now) == 1
        assert record_history(c, [{**base, "abc": "A", "xyz": "Z", "pattern": "smooth"}], "run-4", now) == 1
        assert record_history(c, [{**base, "abc": "A", "xyz": "Z", "pattern": "smooth"}], "run-5", now) == 0
        rows = history_for(c, 1)
    assert [r["reason_key"] for r in rows] == ["first_classification", "abc_changed", "xyz_changed", "multiple_changed"]


def test_criticality_is_only_ever_the_manual_flag(engine):
    seed(engine)
    with engine.begin() as c:
        set_critical(c, 5, True, "buyer-1")
        compute_segments(c)
        rows = history_for(c, 1)
    assert rows[-1]["critical"] is True and rows[-1]["reason_key"] == "criticality_changed"


def test_the_history_is_exposed_by_the_api(client, engine):
    seed(engine)
    assert client.get("/segments/1/history", headers=auth()).json()["history"][0]["reason_key"] == "first_classification"
    assert client.get("/segments/1/history").status_code == 401
