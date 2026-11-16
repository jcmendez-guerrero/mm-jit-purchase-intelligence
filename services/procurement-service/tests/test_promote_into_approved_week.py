"""FR-008 (spec Q1): promoting into a week that already has an approved proposal is refused with a stable 409 code, never a server error, and creates nothing."""


from db.tables import proposals
from sqlalchemy import select, update
from test_scenarios_api import api, body, h  # noqa: F401


def test_promotion_into_an_approved_week_is_a_409_proposal_conflict(api, engine):  # noqa: F811
    sid = api.post("/scenarios", json=body(api.sa), headers=h(**{"Idempotency-Key": "key-appr-001"})).json()["id"]
    week = "2026-W46"
    first = api.post(f"/scenarios/{sid}/promote", json={"week": week}, headers=h())
    assert first.status_code == 201
    with engine.begin() as conn:
        conn.execute(update(proposals).where(proposals.c.id == first.json()["proposal_id"]).values(status="approved"))
    other = api.post("/scenarios", json={"name": "Otro", "disabled_suppliers": []}, headers=h(**{"Idempotency-Key": "key-appr-002"})).json()["id"]
    r = api.post(f"/scenarios/{other}/promote", json={"week": week}, headers=h())
    assert r.status_code == 409 and r.json()["detail"] == "proposal_conflict"
    with engine.connect() as conn:
        assert [p.status for p in conn.execute(select(proposals)).all()] == ["approved"]
