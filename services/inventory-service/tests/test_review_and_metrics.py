"""T054/T055/T056/T057: review release, data-quality metric, event publishing and the API."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from api import routes
from db.tables import (
    ALL_WAREHOUSES,
    data_quality_metrics,
    demand_observations,
    outbox,
    review_decisions,
    stock_movements,
    stock_snapshots,
    variants,
)
from demand.common import Mov
from demand.publisher import LocalBlobWriter, publish_demand_updated, publish_snapshot_created
from demand.rebuild import rebuild
from fastapi.testclient import TestClient
from mmi_common.bus import validate_envelope, verify_payload
from mmi_common.service import create_service_app
from quality.metrics import UNSPECIFIED_SHARE, unspecified_loss_share
from quality.review import ReviewError, decide, list_open
from sqlalchemy import insert, select

CUT = date(2026, 9, 19)
CID = "7d3b7c3e-1c0e-4f6a-9d58-0c7a1a2b3c4d"


def add(engine, i, reason, qty, ts, quarantined=False, codes=None, variant=1):
    with engine.begin() as c:
        c.execute(insert(stock_movements).values(external_id=i, created_at_utc=ts, created_at_raw=str(ts), variant_id=variant, warehouse_id=1,
                                                 quantity=qty, reason=reason, has_note=False, quarantined=quarantined, quarantine_codes=codes))


def snapshot(engine, variant, day, on_hand):
    with engine.begin() as c:
        c.execute(insert(stock_snapshots).values(variant_id=variant, warehouse_id=ALL_WAREHOUSES, snapshot_date=day, on_hand=on_hand, available=on_hand, reserved=0))


T = lambda d, h=10: datetime(2026, 10, d, h, tzinfo=UTC)  # noqa: E731


def test_quarantined_sale_is_excluded_until_confirmed(engine):
    add(engine, 1, "initial_stock", 10, T(1))
    add(engine, 2, "sale_shipment", -2, T(2))
    add(engine, 3, "sale_shipment", -5, T(3), quarantined=True, codes="unreferenced_sale")
    snapshot(engine, 1, date(2026, 10, 5), 3)
    with engine.begin() as c:
        rebuild(c)
    with engine.connect() as c:
        assert {r.day.day: r.demand_qty for r in c.execute(select(demand_observations)).all()} == {2: 2}
        assert [(i.external_id, i.codes) for i in list_open(c)] == [(3, ["unreferenced_sale"])]
    with engine.begin() as c:
        assert decide(c, [3], "confirm", "buyer-1") == 1
        rebuild(c)
    with engine.connect() as c:
        assert {r.day.day: r.demand_qty for r in c.execute(select(demand_observations)).all()} == {2: 2, 3: 5}
        assert list_open(c) == []
        d = c.execute(select(review_decisions)).one()
        assert (d.decision, d.decided_by) == ("confirm", "buyer-1")


def test_ignore_keeps_it_excluded_and_off_the_open_list(engine):
    add(engine, 3, "sale_shipment", -5, T(3), quarantined=True, codes="unreferenced_sale")
    with engine.begin() as c:
        decide(c, [3], "ignore", "buyer-1")
        assert list_open(c) == []
        assert c.execute(select(stock_movements.c.quarantined)).scalar_one() is True


def test_review_rules(engine):
    add(engine, 1, "sale_shipment", -1, T(1), quarantined=True, codes="x")
    add(engine, 2, "sale_shipment", -1, None, quarantined=True, codes="malformed_record")
    add(engine, 3, "sale_shipment", -1, T(1))
    with engine.begin() as c:
        for ids, dec, err in [([3], "confirm", "open review list"), ([1], "approve", "decision must"), ([2], "confirm", "valid timestamp")]:
            with pytest.raises(ReviewError, match=err):
                decide(c, ids, dec, "b")
        with pytest.raises(ReviewError):
            decide(c, [1, 3], "confirm", "b")
        assert c.execute(select(review_decisions)).all() == []  # all or nothing


def M(reason, day):
    return Mov(1, 1, 1, day, reason, -1, False)


def test_unspecified_loss_share_counts_only_post_cutover():
    ms = [M("adjustment_negative", date(2026, 9, 1)), M("adjustment_negative", date(2026, 9, 20)), M("damage", date(2026, 9, 21)),
          M("theft", date(2026, 9, 22)), M("expiry", date(2026, 9, 23))]
    assert unspecified_loss_share(ms, CUT) == Decimal("0.2500")
    assert unspecified_loss_share([M("adjustment_negative", date(2026, 9, 1))], CUT) is None


def test_metric_is_stored_with_the_rebuild(engine):
    add(engine, 1, "initial_stock", 9, T(1))
    add(engine, 2, "adjustment_negative", -1, datetime(2026, 9, 25, tzinfo=UTC))
    add(engine, 3, "damage", -1, datetime(2026, 9, 26, tzinfo=UTC))
    snapshot(engine, 1, date(2026, 10, 5), 7)
    with engine.begin() as c:
        rebuild(c)
    with engine.connect() as c:
        got = {r.metric: r.value for r in c.execute(select(data_quality_metrics)).all()}
    assert Decimal(str(got[UNSPECIFIED_SHARE])) == Decimal("0.5") and got["quarantined_movements"] == 0


def test_events_are_published_with_valid_envelopes_and_checksums(engine, tmp_path):
    w = LocalBlobWriter(tmp_path)
    with engine.begin() as c:
        publish_snapshot_created(c, w, date(2026, 11, 4), 1000, CID)
        publish_demand_updated(c, w, date(2026, 11, 3), 4200, CID)
    with engine.connect() as c:
        envs = [r.envelope for r in c.execute(select(outbox)).all()]
    assert {e["type"] for e in envs} == {"inventory.snapshot.created.v1", "inventory.demand.updated.v1"}
    for e in envs:
        validate_envelope(e, now=datetime.now(UTC))
        verify_payload(e, Path(e["payload_ref"]["uri"].removeprefix("file://")).read_bytes())


# ---- API ------------------------------------------------------------------------------------------------

class _Validator:
    def validate(self, token, required_roles=()):
        from mmi_common.auth import AuthError, Principal

        roles = {"viewer", "buyer"} if token == "buyer" else {"viewer"}  # noqa: S105 - test token name, not a secret
        if not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        return Principal(subject=f"user-{token}", roles=frozenset(roles), auth_time=None)


@pytest.fixture
def client(engine):
    app = create_service_app("inventory-service", validator=_Validator())
    app.include_router(routes.build_router(app))
    app.dependency_overrides[routes.get_engine] = lambda: engine
    return TestClient(app)


def auth(role="viewer"):
    return {"Authorization": f"Bearer {role}"}


def test_api_requires_authentication_and_the_buyer_role_for_decisions(client, engine):
    assert client.get("/review").status_code == 401
    assert client.post("/review/decisions", json={"ids": [1], "decision": "confirm"}, headers=auth("viewer")).status_code == 403


def test_api_variant_detail_and_review_flow(client, engine):
    with engine.begin() as c:
        c.execute(insert(variants).values(external_id=1, sku="SYN-1", name="Variante", pack_size=1, uom="unit"))
    add(engine, 1, "initial_stock", 10, T(1))
    add(engine, 2, "sale_shipment", -4, T(2))
    add(engine, 3, "sale_shipment", -1, T(3), quarantined=True, codes="unreferenced_sale")
    snapshot(engine, 1, date(2026, 10, 5), 5)
    with engine.begin() as c:
        rebuild(c)
    assert client.get("/variants/999", headers=auth()).status_code == 404
    body = client.get("/variants/1", headers=auth()).json()
    assert body["stock"]["on_hand"] == 5 and [d["qty"] for d in body["demand"]] == [4] and body["history_reconciled"] is True
    assert client.get("/review", headers=auth()).json()["count"] == 1
    assert client.post("/review/decisions", json={"ids": [99], "decision": "confirm"}, headers=auth("buyer")).status_code == 409
    assert client.post("/review/decisions", json={"ids": [3], "decision": "confirm"}, headers=auth("buyer")).json() == {"decided": 1}
    assert [d["qty"] for d in client.get("/variants/1", headers=auth()).json()["demand"]] == [4, 1]
    assert client.get("/review", headers=auth()).json()["count"] == 0
