"""T060a: the pull of eligibility and confidence from forecast-service - the mapping, the no-run case, failures, and the token kept out of sight."""

import httpx
import pytest
from quality.eligibility_source import HttpForecastEligibility


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_the_listing_is_mapped_by_sku_with_the_run_id_and_the_token_is_sent_as_a_bearer():
    seen = {}

    def handler(request):
        seen["auth"], seen["path"] = request.headers["Authorization"], request.url.path
        return httpx.Response(200, json={"run_id": "r1", "variants": [{"sku": "EJ-1", "eligibility": "eligible", "confidence": "alta"}, {"sku": "EJ-2", "eligibility": "not_eligible", "confidence": None}]})

    src = HttpForecastEligibility("http://forecast/", lambda: "tok", client_for(handler))
    assert src.fetch() == ("r1", {"EJ-1": ("eligible", "alta"), "EJ-2": ("not_eligible", None)})
    assert seen == {"auth": "Bearer tok", "path": "/forecasts/eligibility"}


def test_no_run_yet_is_an_empty_answer_not_an_error():
    src = HttpForecastEligibility("http://forecast", "tok", client_for(lambda r: httpx.Response(404, json={"detail": "no_forecast_run"})))
    assert src.fetch() == (None, {})


def test_a_server_error_is_raised_so_the_caller_can_report_unavailable():
    src = HttpForecastEligibility("http://forecast", "tok", client_for(lambda r: httpx.Response(503)))
    with pytest.raises(httpx.HTTPStatusError):
        src.fetch()


def test_the_token_never_appears_in_the_repr():
    assert "secret-token" not in repr(HttpForecastEligibility("http://forecast", "secret-token"))
