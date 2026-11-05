"""Reader client against the synthetic Siweb mock: pagination, retries, 401, budget."""

import pytest
from client.reader import AuthExpiredError, BudgetExhaustedError, siweb_total
from siweb_mock.state import MockConfig


def test_paginates_all_variants(make_reader):
    reader, app = make_reader()
    rows = [r for _, _, page in reader.pages("/api/public/inventory/variants") for r in page]
    assert len(rows) == len({r["id"] for r in rows}) == len(app.state.mock.data.variants)
    assert reader.requests_made == len(reader.log) and all(e["method"] == "GET" for e in reader.log)


def test_page_size_never_exceeds_200(make_reader):
    reader, app = make_reader()
    list(reader.pages("/api/public/inventory/variants", limit=5000))
    assert all(int(r["query"]["limit"]) <= 200 for r in app.state.mock.request_log if "variants" in r["path"])


def test_retries_a_temporary_500_then_succeeds(make_reader):
    reader, _ = make_reader(MockConfig(missing_pages={2}))
    n = sum(len(rows) for _, _, rows in reader.pages("/api/public/inventory/movements"))
    assert n > 200 and reader.retries == 1


def test_429_is_retried_with_backoff_without_retry_after(make_reader):
    sleeps = []
    reader, _ = make_reader(MockConfig(rate_limit_per_hour=3))
    reader.sleep = sleeps.append
    reader.max_retries = 2
    with pytest.raises(Exception, match="429"):
        for _ in range(10):
            reader.get("/api/public/inventory/warehouses")
    assert sleeps == [1.0, 2.0]  # exponential 2**0, 2**1


def test_retry_after_is_honoured_when_present(make_reader):
    sleeps = []
    reader, _ = make_reader(MockConfig(rate_limit_per_hour=1, send_retry_after=True))
    reader.sleep = sleeps.append
    reader.max_retries = 1
    reader.get("/api/public/inventory/warehouses")
    with pytest.raises(Exception, match="429"):
        reader.get("/api/public/inventory/warehouses")
    assert sleeps == [60.0]


def test_401_stops_the_run(make_reader):
    reader, _ = make_reader(MockConfig(unauthorized_after=1))
    reader.get("/api/public/inventory/warehouses")
    with pytest.raises(AuthExpiredError):
        reader.get("/api/public/inventory/warehouses")


def test_budget_exhaustion_stops_before_sending(make_reader):
    reader, app = make_reader(per_hour=2)
    reader.get("/api/public/inventory/warehouses")
    reader.get("/api/public/inventory/warehouses")
    sent = len(app.state.mock.request_log)
    with pytest.raises(BudgetExhaustedError):
        reader.get("/api/public/inventory/warehouses")
    assert len(app.state.mock.request_log) == sent and reader.bucket.denied == 1


def test_reported_total_for_reconciliation(make_reader):
    reader, app = make_reader()
    body = reader.get("/api/public/inventory/movements", {"limit": 1})
    assert siweb_total(body) == len(app.state.mock.movements)


def test_token_never_appears_in_client_log(make_reader):
    reader, _ = make_reader()
    reader.get("/api/public/inventory/warehouses")
    from siweb_mock.state import TOKEN

    assert TOKEN not in str(reader.log) and "***" in repr(reader.tokens)
