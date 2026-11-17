"""T043 (FR-014): the proposal API exposes the review notes with the SKU the user sees."""

from db.tables import proposals
from proposal_support import generate, h
from sqlalchemy import update


def test_review_notes_are_listed_with_the_sku_and_empty_otherwise(api, engine):
    c, _ = api
    pid = generate(c)
    assert c.get(f"/proposals/{pid}", headers=h("viewer")).json()["review_notes"] == []
    with engine.begin() as conn:
        conn.execute(update(proposals).where(proposals.c.id == pid).values(flags={"notes": ["no_eligible_supplier:7", "solver_no_solution"]}))
    notes = c.get(f"/proposals/{pid}", headers=h("viewer")).json()["review_notes"]
    assert notes == [{"code": "no_eligible_supplier", "variant_id": 7, "sku": None, "product_name": None}]
