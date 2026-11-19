"""Feature 014 (T006): the live-stack seed loader puts the synthetic reference dataset into a database, once, and only on this machine."""

import importlib.util
from pathlib import Path

import pytest

SEED = Path(__file__).resolve().parents[1] / "live-stack" / "seed.py"


@pytest.fixture(scope="module")
def seed_module():
    spec = importlib.util.spec_from_file_location("live_stack_seed", SEED)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_seeded_database_shows_the_documented_totals(seed_module, tmp_path):
    from dashboard.kpis import compute_summary
    from reference_dataset import TODAY
    from sqlalchemy import create_engine

    url = f"sqlite:///{tmp_path / 'seed.db'}"
    out = seed_module.seed(url, create_tables=True)
    assert out["variants"] == 5 and out["lots"] == 7 and out["aggregate_rows"] > 0
    with create_engine(url).connect() as c:
        s = compute_summary(c, TODAY)
    assert float(s.inventory_value) == 100.0                  # TOTALS.md: stock value for all warehouses
    assert float(s.expiring_value) == 60.0


def test_a_second_run_is_refused_so_the_fixture_never_mixes_with_other_data(seed_module, tmp_path):
    url = f"sqlite:///{tmp_path / 'twice.db'}"
    seed_module.seed(url, create_tables=True)
    with pytest.raises(seed_module.SeedRefused, match="already holds products"):
        seed_module.seed(url)


def test_a_database_that_is_not_on_this_machine_is_refused_before_any_connection(seed_module):
    with pytest.raises(seed_module.SeedRefused, match="this machine"):
        seed_module.seed("postgresql+psycopg://inventory_svc:x@db.example.com:5432/mmi")


def test_the_cli_exits_with_a_message_and_status_2_on_refusal(seed_module, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["seed.py", "--database-url", "postgresql+psycopg://u:x@db.example.com/mmi"])
    assert seed_module.main() == 2
    assert "seed refused" in capsys.readouterr().err
