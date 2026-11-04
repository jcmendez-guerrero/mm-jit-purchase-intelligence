"""T032: quarantine cases (malformed expiry, missing warehouse, unreferenced sale) from the synthetic dataset."""

from mapping.quality import check_lot, check_movement
from siweb_mock.state import MockConfig


def all_movements(make_reader):
    reader, app = make_reader(MockConfig())
    rows = [r for _, _, page in reader.pages("/api/public/inventory/movements") for r in page]
    return rows, app.state.mock.data.truth


def test_unreferenced_sales_are_quarantined_not_stored(make_reader):
    rows, truth = all_movements(make_reader)
    quarantined = {r["id"] for r in rows if (res := check_movement(r)).movement is None
                   and any(i.code == "unreferenced_sale" for i in res.issues)}
    assert quarantined == set(truth["unreferenced_sale_ids"])


def test_malformed_expiry_is_quarantined(make_reader):
    rows, truth = all_movements(make_reader)
    bad = {r["id"] for r in rows if any(i.code == "malformed_expiry" for i in check_movement(r).issues)}
    assert bad == set(truth["malformed_expiry_ids"])


def test_missing_warehouse_is_stored_as_unassigned_and_flagged(make_reader):
    rows, _ = all_movements(make_reader)
    nulls = [r for r in rows if r["warehouse_id"] is None and r["reason"] != "sale_shipment"]
    assert nulls
    for r in nulls:
        res = check_movement(r)
        flagged = [i for i in res.issues if i.code == "warehouse_unassigned"]
        assert flagged and not flagged[0].blocking
        if res.movement:
            assert res.movement.warehouse_id == 0


def test_no_record_vanishes_every_movement_is_stored_or_has_an_issue(make_reader):
    rows, _ = all_movements(make_reader)
    for r in rows:
        res = check_movement(r)
        assert res.movement is not None or any(i.blocking for i in res.issues)


def test_malformed_lot_expiry_is_flagged():
    assert check_lot({"id": 1, "expiry_date": "31/02/2027x"})[0].code == "malformed_expiry"
    assert check_lot({"id": 1, "expiry_date": "2027-06-20"}) == []
    assert check_lot({"id": 1, "expiry_date": None}) == []
