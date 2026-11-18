"""T014a (forecast, FR-023): explanation and backtest responses carry UTC timestamps, decimal strings and SKUs only; no Siweb variant id appears."""

import json
import re
from datetime import datetime, timedelta

import api
import pytest
from fastapi.testclient import TestClient
from mmi_common.service import create_service_app
from runs.runner import run_forecast
from tests_helpers import FakeSource, NullWriter

H = {"Authorization": "Bearer x"}
SIWEB_ID_KEYS = re.compile(r'"(variant_id|product_id|external_id|contact_id)"')


class _V:
    def validate(self, token, required_roles=()):
        from mmi_common.auth import Principal

        return Principal("svc", frozenset({"viewer", "buyer"}), None)


@pytest.fixture
def client(engine, make_export, tmp_path):
    export = make_export(seed=3)
    app = create_service_app("forecast-service", validator=_V())
    app.include_router(api.build_router(app))
    app.dependency_overrides[api.get_engine] = lambda: engine
    app.state.series_source = FakeSource(export)
    app.state.blob_writer = NullWriter(tmp_path)
    run_forecast(engine, FakeSource(export), NullWriter(tmp_path))
    return TestClient(app)


def _walk(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _bodies(client, engine):
    from db.tables import forecast_explanations
    from sqlalchemy import select

    client.post("/forecasts/backtests", json={"scope": "catalogue"}, headers=H)
    with engine.connect() as c:
        sku = c.execute(select(forecast_explanations.c.sku).where(forecast_explanations.c.sku.is_not(None)).limit(1)).scalar()
    out = [client.get(f"/forecasts/products/{sku}/explanation", headers=H), client.get(f"/forecasts/products/{sku}/backtest", headers=H)]
    assert all(r.status_code == 200 for r in out), [r.text for r in out]
    return sku, [r.json() for r in out]


def test_figures_are_decimal_strings_and_timestamps_are_utc(client, engine):
    _, bodies = _bodies(client, engine)
    seen_stamp = False
    for body in bodies:
        for k, v in _walk(body):
            if k in ("low", "expected", "high", "wape", "bias", "baseline_wape", "baseline_bias") and v is not None:
                assert isinstance(v, str), (k, v)
            if k == "created_at":
                seen_stamp = True
                assert datetime.fromisoformat(v).utcoffset() == timedelta(0)
    assert seen_stamp


def test_users_see_skus_and_no_siweb_ids(client, engine):
    sku, bodies = _bodies(client, engine)
    text = json.dumps(bodies)
    assert sku in text and not SIWEB_ID_KEYS.search(text)
