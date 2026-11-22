"""Feature 014 (T063, 006 T069): operational signals of the dashboard: how long a refresh took and how many rows it wrote, how big an export was and why one was refused.

Counts, durations and kinds only. A signal never names a product, a filter value or a cell, and never carries a note or a secret.
"""

import logging

import pytest
from conftest import auth
from dashboard.kpis import refresh_aggregates
from reference_dataset import NOW, TODAY, freeze_clock, seed_reference

LOGGER = "mmi.inventory.dashboard"


@pytest.fixture
def seeded(engine, monkeypatch):
    freeze_clock(monkeypatch)
    seed_reference(engine)
    return engine


def messages(caplog):
    return [r.getMessage() for r in caplog.records if r.name == LOGGER]


def test_a_refresh_says_how_long_it_took_and_how_many_rows_it_wrote(seeded, caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    with seeded.begin() as c:
        written = refresh_aggregates(c, TODAY, None, NOW)
    [line] = [m for m in messages(caplog) if m.startswith("dashboard_refresh")]
    assert f"rows={written}" in line and "seconds=" in line and f"day={TODAY.isoformat()}" in line


def test_an_export_says_its_kind_rows_and_size(client, seeded, caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    res = client.get("/dashboard/export", params={"kind": "drilldown", "drill_kind": "inventory_value", "supplier_id": "sup-a"}, headers=auth("buyer"))
    assert res.status_code == 200
    [line] = [m for m in messages(caplog) if m.startswith("dashboard_export ")]
    assert "kind=drilldown" in line and f"bytes={len(res.content)}" in line and "rows=" in line


def test_a_refused_export_says_why_and_nothing_else(client, seeded, caplog, monkeypatch):
    import dashboard.export as mod

    monkeypatch.setattr(mod, "MAX_ROWS", 2)
    caplog.set_level(logging.INFO, logger=LOGGER)
    assert client.get("/dashboard/export", params={"kind": "drilldown", "drill_kind": "inventory_value"}, headers=auth("buyer")).status_code == 413
    [line] = [m for m in messages(caplog) if m.startswith("dashboard_export_refused")]
    assert "reason=export_too_large" in line and "kind=drilldown" in line


def test_no_signal_names_a_product_a_filter_value_or_a_cell(client, seeded, caplog):
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    client.get("/dashboard/export", params={"kind": "drilldown", "drill_kind": "inventory_value", "supplier_id": "sup-a"}, headers=auth("buyer"))
    client.get("/dashboard/export", params={"kind": "cards"}, headers=auth("buyer"))
    with seeded.begin() as c:
        refresh_aggregates(c, TODAY, None, NOW)
    text = " ".join(messages(caplog))
    for private in ("SYN-0", "sup-a", "Producto", "40,00", "40.00"):
        assert private not in text, private
