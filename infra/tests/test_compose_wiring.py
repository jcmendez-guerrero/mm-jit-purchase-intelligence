"""T168: the forecast API in the Compose stack has what it needs to re-forecast on request and to dry-run an import (it 503s without them)."""

from pathlib import Path

import yaml

COMPOSE = yaml.safe_load((Path(__file__).resolve().parents[1] / "compose.yaml").read_text())["services"]


def env(name):
    e = COMPOSE[name]["environment"]
    return e if isinstance(e, dict) else dict(x.split("=", 1) for x in e)


def test_the_forecast_api_has_a_series_source_and_a_blob_root():
    e = env("forecast-service")
    assert e["MMI_INVENTORY_URL"] == "http://inventory-service:8000"      # main._wire() skips the series source and writer without it
    assert e["MMI_BLOB_ROOT"] == env("forecast-worker")["MMI_BLOB_ROOT"]


def test_the_api_and_the_worker_share_the_blob_volume_so_both_read_the_same_run_files():
    shared = {v.split(":")[0] for v in COMPOSE["forecast-service"]["volumes"]} & {v.split(":")[0] for v in COMPOSE["forecast-worker"]["volumes"]}
    assert "blobs" in shared


def test_every_service_that_calls_another_names_it_by_a_compose_service():
    for name, svc in COMPOSE.items():
        for key, value in (svc.get("environment") or {}).items() if isinstance(svc.get("environment"), dict) else []:
            if key.startswith("MMI_") and key.endswith("_URL") and value.startswith("http://") and "localhost" not in value:
                host = value.split("//")[1].split(":")[0]
                assert host in COMPOSE, f"{name}: {key} points at unknown service {host}"
