"""T043 (FR-014, AGENTS rule 6): an input the allocator cannot use is never dropped silently: the rejected offer is named on the line, and a variant with no eligible supplier is named in the proposal notes."""

from builders import flat_forecast, inputs, offer, terms, variant
from conftest import NOW
from db.tables import proposals
from proposals.generate import generate, store
from proposals.model import SupplierTermsIn
from sqlalchemy import select


def sample():
    return inputs([variant(1, [offer("A", "0.10", status="blocked_jump"), offer("B", "1.00")], flat_forecast(1.0)),
                   variant(2, [offer("A", "0.10", status="blocked_jump")], flat_forecast(1.0))], [terms("A"), terms("B")])


def test_a_blocked_cost_is_named_on_the_line_that_used_another_supplier():
    d = generate(sample(), 10)
    assert d.lines[0].explanation["supplier"]["rejected"] == [{"supplier_id": "A", "reason": "cost_blocked"}]


def test_a_needed_variant_with_no_eligible_supplier_is_named_in_the_notes_not_dropped_silently():
    d = generate(sample(), 10)
    assert [ln.variant_id for ln in d.lines] == [1] and "no_eligible_supplier:2" in d.notes


def test_the_note_survives_storage_and_is_deterministic(conn):
    a, b = generate(sample(), 10), generate(sample(), 10)
    assert a.notes == b.notes
    pid = store(conn, a, "buyer-1", "2026-W46", None, NOW)
    assert "no_eligible_supplier:2" in conn.execute(select(proposals.c.flags).where(proposals.c.id == pid)).scalar()["notes"]


def test_a_stocked_product_behind_a_disabled_supplier_raises_no_note_but_one_with_real_need_does():
    """T053 (FR-014): the note is for needed variants only; a product with plenty on hand and a disabled supplier is not a warning."""
    disabled = [SupplierTermsIn("A", disabled=True)]
    stocked = generate(inputs([variant(1, [offer("A", "1.00")], flat_forecast(0.1), on_hand=500)], disabled), 10)
    assert stocked.lines == () and stocked.notes == ()
    needed = generate(inputs([variant(1, [offer("A", "1.00")], flat_forecast(1.0))], disabled), 10)
    assert needed.notes == ("no_eligible_supplier:1",)
