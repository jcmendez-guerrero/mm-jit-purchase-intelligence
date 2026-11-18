"""T059: every distribution adds up to the active product count and every count opens its own list (SC-007)."""

import httpx
import quality_fixtures as qf
from conftest import auth
from test_quality_api import seed_case


class Eligibility:
    def __init__(self, run_id, mapping):
        self.run_id, self.mapping = run_id, mapping

    def fetch(self):
        return self.run_id, self.mapping


class Down:
    def fetch(self):
        raise httpx.ConnectError("forecast-service unreachable")


def seed_all(engine):
    for name in qf.CASES:
        seed_case(engine, name)


def recompute(client, source):
    client.app.state.forecast_eligibility = source
    return client.post("/quality/recompute", headers=auth("buyer")).json()


FORECAST = {"EJ-9101": ("eligible", "alta"), "EJ-9102": ("eligible", "media"), "EJ-9103": ("manual_review_only", "baja"), "EJ-9104": ("not_eligible", None)}


def sums(body):
    return [sum(b["count"] for b in body[k]) for k in ("by_class", "by_eligibility", "by_confidence")]


def test_every_distribution_adds_up_to_the_active_products_and_unforecast_products_are_pending(client, engine):
    seed_all(engine)
    assert recompute(client, Eligibility("run-1", FORECAST))["eligibility"] == "ok"
    body = client.get("/quality/portfolio", headers=auth("viewer")).json()
    assert body["active_products"] == 7 and sums(body) == [7, 7, 7]
    elig = {b["key"]: b["count"] for b in body["by_eligibility"]}
    assert elig == {"eligible": 2, "manual_review_only": 1, "not_eligible": 1, "pending": 3}
    conf = {b["key"]: b["count"] for b in body["by_confidence"]}
    assert conf == {"alta": 1, "media": 1, "baja": 1, "none": 4}


def test_every_count_opens_a_list_with_exactly_that_many_products(client, engine):
    seed_all(engine)
    recompute(client, Eligibility("run-1", FORECAST))
    body = client.get("/quality/portfolio", headers=auth()).json()
    for kind, key in (("class", "by_class"), ("eligibility", "by_eligibility"), ("confidence", "by_confidence")):
        for bucket in body[key]:
            assert bucket["drilldown"] == f"bucket={kind}&key={bucket['key']}"
            page = client.get(f"/quality/portfolio/products?bucket={kind}&key={bucket['key']}", headers=auth()).json()
            assert page["total"] == bucket["count"] == len(page["skus"]) and page["skus"] == sorted(page["skus"])
    pending = client.get("/quality/portfolio/products?bucket=eligibility&key=pending", headers=auth()).json()["skus"]
    assert pending == ["EJ-9105", "EJ-9106", "EJ-9107"]


def test_lists_are_paged(client, engine):
    seed_all(engine)
    recompute(client, None)
    first = client.get("/quality/portfolio/products?bucket=eligibility&key=pending&limit=3", headers=auth()).json()
    rest = client.get("/quality/portfolio/products?bucket=eligibility&key=pending&limit=3&offset=3", headers=auth()).json()
    assert first["total"] == 7 and len(first["skus"]) == 3 and len(rest["skus"]) == 3 and not set(first["skus"]) & set(rest["skus"])


def test_the_forecast_service_being_down_or_without_a_run_never_fails_the_recompute(client, engine):
    seed_all(engine)
    assert recompute(client, Down())["eligibility"] == "unavailable"
    assert {b["key"]: b["count"] for b in client.get("/quality/portfolio", headers=auth()).json()["by_eligibility"]}["pending"] == 7
    assert recompute(client, Eligibility(None, {}))["eligibility"] == "no_run"
    assert recompute(client, None)["eligibility"] == "not_configured"


def test_a_forecast_for_a_product_that_is_not_in_the_catalogue_is_ignored(client, engine):
    seed_all(engine)
    recompute(client, Eligibility("run-1", {**FORECAST, "EJ-0000": ("eligible", "alta")}))
    assert client.get("/quality/portfolio", headers=auth()).json()["active_products"] == 7


def test_an_empty_portfolio_is_valid_and_recompute_is_repeatable(client, engine):
    assert client.get("/quality/portfolio", headers=auth()).json()["active_products"] == 0
    seed_all(engine)
    recompute(client, Eligibility("run-1", FORECAST))
    again = recompute(client, Eligibility("run-1", FORECAST))
    assert again["status"] == "completed" and client.get("/quality/portfolio", headers=auth()).json()["active_products"] == 7


def test_the_worst_quality_list_is_ranked_by_coverage_and_shows_skus_only(client, engine):
    seed_all(engine)
    recompute(client, None)
    worst = client.get("/quality/portfolio", headers=auth()).json()["worst_quality"]
    assert worst and all(set(w) == {"sku", "coverage_ratio", "rejected_share", "anomaly_share"} for w in worst)
    ratios = [float(w["coverage_ratio"]) for w in worst]
    assert ratios == sorted(ratios)


def test_roles_and_bad_input(client, engine):
    seed_all(engine)
    assert client.get("/quality/portfolio").status_code == 401
    assert client.get("/quality/portfolio?category=Z", headers=auth()).json()["detail"] == "request_invalid"
    assert client.get("/quality/portfolio/products?bucket=nope&key=x", headers=auth()).json()["detail"] == "request_invalid"
    assert client.get("/quality/portfolio/products?bucket=class&key=AX&limit=0", headers=auth()).status_code == 422
