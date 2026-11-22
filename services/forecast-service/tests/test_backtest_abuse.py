"""T068 (forecast): hostile SKUs, scopes and bodies on the explanation and backtest endpoints are refused cleanly; no free text is stored."""

import api
import pytest
from db.tables import audit_events, backtest_jobs, product_backtest
from fastapi.testclient import TestClient
from mmi_common.service import create_service_app
from runs.runner import run_forecast
from sqlalchemy import func, select
from tests_helpers import FakeSource, NullWriter

H = {"Authorization": "Bearer x"}
HOSTILE_SKUS = ["x' OR '1'='1", "a; DROP TABLE product_backtest;--", "../../etc/passwd", "%00", "A" * 5000, "<script>alert(1)</script>"]


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


def _count(engine, table):
    with engine.connect() as c:
        return c.execute(select(func.count()).select_from(table)).scalar()


@pytest.mark.parametrize("sku", HOSTILE_SKUS)
def test_hostile_skus_are_refused_and_nothing_is_stored(client, engine, sku):
    assert client.get(f"/forecasts/products/{sku}/explanation", headers=H).status_code in (404, 422)
    assert client.get(f"/forecasts/products/{sku}/backtest", headers=H).status_code in (404, 422)
    assert client.post("/forecasts/backtests", json={"scope": "product", "sku": sku}, headers=H).status_code in (404, 422)
    assert _count(engine, product_backtest) == 0


@pytest.mark.parametrize("body", [{}, {"scope": "everything"}, {"scope": "product"}, {"scope": 5}, {"scope": "catalogue", "sku": ["a"]}, ["x"]])
def test_malformed_backtest_bodies_are_validation_errors(client, body):
    assert client.post("/forecasts/backtests", json=body, headers=H).status_code == 422


def test_unparseable_and_oversized_bodies_are_refused(client):
    assert client.post("/forecasts/backtests", content=b"{nope", headers={**H, "Content-Type": "application/json"}).status_code == 422
    assert client.post("/forecasts/backtests", json={"scope": "product", "sku": "S" * 100000}, headers=H).status_code in (404, 413, 422)


def test_free_text_and_tax_id_fields_are_ignored_and_never_stored(client, engine):
    client.post("/forecasts/backtests", json={"scope": "catalogue", "note": "texto libre secreto", "supplier_cif": "B12345678"}, headers=H)
    with engine.connect() as c:
        stored = " ".join(str(v) for t in (backtest_jobs, product_backtest, audit_events) for r in c.execute(select(t)).all() for v in r)
    assert "texto libre secreto" not in stored and "B12345678" not in stored
