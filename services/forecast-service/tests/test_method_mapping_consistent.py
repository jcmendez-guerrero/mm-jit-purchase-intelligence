"""T032a, T096: the method of a product is the same in the explanation and in what the proposal reads (FR-008).

The proposal line takes its policy straight from ``GET /forecasts/latest`` (procurement ``inputs.py`` -> ``targets.py``), so that read is compared with the explanation of
the same SKU. The proposal export (supplier, SKU, quantity, cost, delivery date) carries no method column, so it cannot disagree with either.
"""

import api
import pytest
from fastapi.testclient import TestClient
from mmi_common.service import create_service_app
from policies.fallback import NAME as FALLBACK
from runs.runner import run_forecast
from tests_helpers import FakeSource, NullWriter

H = {"Authorization": "Bearer x"}


class _V:
    def validate(self, token, required_roles=()):
        from mmi_common.auth import Principal

        return Principal("svc", frozenset({"viewer"}), None)


@pytest.fixture
def client(engine):
    app = create_service_app("forecast-service", validator=_V())
    app.include_router(api.build_router(app))
    app.dependency_overrides[api.get_engine] = lambda: engine
    return TestClient(app)


def test_every_product_has_the_same_method_in_the_explanation_and_in_the_forecast_the_proposal_reads(client, engine, make_export, tmp_path):
    run_forecast(engine, FakeSource(make_export(seed=3)), NullWriter(tmp_path))
    latest = client.get("/forecasts/latest", headers=H).json()["variants"]
    assert latest
    for variant_id, read in latest.items():
        explained = client.get(f"/forecasts/products/EJ-{variant_id}/explanation", headers=H).json()
        assert explained["method"] == read["policy"], variant_id
        assert (explained["method_reason_code"] == "min_max_fallback") == (read["policy"] == FALLBACK), variant_id        # the reason names the fallback exactly when the line shows min/max
        assert (explained["eligibility"] == "not_eligible") <= (not read["eligible"]), variant_id                         # a not-eligible product is never read as eligible
