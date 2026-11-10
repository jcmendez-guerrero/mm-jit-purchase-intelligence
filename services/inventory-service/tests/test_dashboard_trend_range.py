"""T031 (feature 006): the demand trend follows a date range (`date_from`, `date_to`) with the same validation as every other figure; the forecast is left out
when the range ends before today, because it describes the days after today. Synthetic reference dataset (TOTALS.md): SYN-001 sells 3 a day, SYN-002 1 a day.
"""

from conftest import auth
from reference_dataset import seed_reference


def trend(client, query):
    return client.get(f"/dashboard/demand-trend?{query}", headers=auth("viewer"))


def test_a_past_range_returns_exactly_its_days_and_no_forecast(client, engine):
    seed_reference(engine)
    body = trend(client, "date_from=2026-10-10&date_to=2026-10-19").json()
    assert body["from"] == "2026-10-10" and body["to"] == "2026-10-19"
    assert [p["day"] for p in body["series"]] == [f"2026-10-{d}" for d in range(10, 20)]
    assert sum(p["actual"] for p in body["series"]) == 10 * (3 + 1)
    assert body["estimated"] == [] and body["estimated_basis"]["reason"] == "range_in_past"


def test_without_dates_the_last_days_behave_as_before(client, engine):
    seed_reference(engine)
    body = trend(client, "days=7").json()
    assert len(body["series"]) <= 7 and body["to"] >= body["from"]


def test_a_bad_range_is_refused_like_every_other_filter(client, engine):
    seed_reference(engine)
    for q in ("date_from=2026-10-19&date_to=2026-10-10", "date_from=2026-10-10&date_to=2026-10-12", "date_from=2020-01-01&date_to=2026-10-12", "date_from=nope", "date_to=2026-13-40"):
        assert trend(client, q).status_code == 422, q
