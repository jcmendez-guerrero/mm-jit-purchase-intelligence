"""T027 (MMI 004): loading the synthetic exports through the local loader reconciles end to end.

Static checks always run. The live run needs Docker and runs only with RUN_LOCAL_LOAD_E2E=1; it starts the stack with the
local-data override, loads the committed synthetic files, lets the connector collect them and checks that the platform holds exactly
what the loader reported, that a second load adds nothing, and that the base compose file never enables the loader.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "infra" / "compose.yaml"
OVERRIDE = ROOT / "infra" / "compose.local-data.yaml"
FIXTURES = ROOT / "packages" / "testing" / "fixtures" / "exports"
LIVE = os.environ.get("RUN_LOCAL_LOAD_E2E") == "1"


def test_the_base_compose_never_enables_the_loader():
    text = BASE.read_text()
    assert "MMI_LOCAL_LOADER" not in text and "local-loader" not in text and "export_loader" not in text


def test_the_override_defines_the_loader_and_binds_ports_to_localhost_only():
    doc = yaml.safe_load(OVERRIDE.read_text())
    assert "local-loader" in doc["services"]
    for name, svc in doc["services"].items():
        for port in svc.get("ports", []):
            assert str(port).startswith("127.0.0.1:"), f"{name} publishes {port} beyond localhost"
    for name in ("api-bff", "procurement-service", "siweb-connector"):
        assert doc["services"][name]["environment"]["MMI_LOCAL_LOADER"] == "1"
    assert doc["services"]["local-loader"]["environment"]["MMI_ENV"] == "dev"


def test_the_override_holds_no_credentials_or_real_hosts():
    text = OVERRIDE.read_text()
    assert "siweb360" not in text.lower() and ".azure" not in text.lower() and "password" not in text.lower()


def compose(*args: str, check: bool = True, timeout: int = 1500) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-f", str(BASE), "-f", str(OVERRIDE), *args],
        cwd=ROOT, capture_output=True, text=True, check=check, timeout=timeout,
    )


def inventory_sources() -> dict:
    code = (
        "import json,urllib.request;"
        "t=json.load(urllib.request.urlopen(urllib.request.Request('http://dev-issuer:8090/token',"
        "json.dumps({'subject':'svc-e2e','audience':'api://mmi-inventory-service','roles':['admin','viewer']}).encode(),{'Content-Type':'application/json'})))['access_token'];"
        "r=urllib.request.Request('http://localhost:8000/status/sources',headers={'Authorization':'Bearer '+t});"
        "print(urllib.request.urlopen(r).read().decode())"
    )
    out = compose("exec", "-T", "inventory-service", "python", "-c", code).stdout
    return json.loads(out.strip().splitlines()[-1])


def imported_suppliers() -> int:
    code = (
        "import json,urllib.request;"
        "t=json.load(urllib.request.urlopen(urllib.request.Request('http://dev-issuer:8090/token',"
        "json.dumps({'subject':'svc-e2e','audience':'api://mmi-procurement-service','roles':['viewer']}).encode(),{'Content-Type':'application/json'})))['access_token'];"
        "r=urllib.request.Request('http://localhost:8000/suppliers?classification=unclassified',headers={'Authorization':'Bearer '+t});"
        "rows=json.loads(urllib.request.urlopen(r).read().decode());print(len([s for s in rows if s['origin']=='imported']))"
    )
    return int(compose("exec", "-T", "procurement-service", "python", "-c", code).stdout.strip().splitlines()[-1])


def load_cli() -> subprocess.CompletedProcess:
    env = {**os.environ, "MMI_ENV": "dev", "MMI_DEV_ISSUER_URL": "http://localhost:8090", "MMI_SIWEB_MOCK_URL": "http://localhost:8089",
           "MMI_CONNECTOR_URL": "http://localhost:8092", "MMI_PROCUREMENT_URL": "http://localhost:8093", "MMI_LOADER_STATE_DIR": str(ROOT / "data" / "e2e-loader-state"),
           "PYTHONPATH": str(ROOT / "packages" / "testing" / "src")}
    return subprocess.run(
        [sys.executable, "-m", "export_loader", "load", "--dir", str(FIXTURES), "--accept-interpretation", "--max-review-ratio", "0.5"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=1800, check=False,
    )


@pytest.mark.skipif(not LIVE, reason="needs Docker; set RUN_LOCAL_LOAD_E2E=1")
def test_synthetic_exports_reconcile_end_to_end():
    compose("up", "-d", "--build", "postgres", "azurite", "siweb-mock", "dev-issuer", "siweb-connector", "inventory-service", "inventory-worker", "procurement-service", "local-loader")
    try:
        deadline = time.time() + 300
        while time.time() < deadline:
            ps = compose("ps", "--format", "json", "inventory-service", "procurement-service", check=False).stdout
            if ps.count('"healthy"') >= 2:                      # both run their migrations (including procurement 0011) on PostgreSQL at start
                break
            time.sleep(5)
        first = load_cli()
        assert first.returncode == 0, first.stdout + first.stderr
        lines = {ln.split(":")[0]: ln for ln in first.stdout.splitlines() if ln.startswith(("suppliers:", "inventory:", "movements:"))}
        loaded_movements = int(lines["movements"].split("cargadas ")[1].split(" ")[0])
        assert "Sincronización: correcta" in first.stdout
        sup_line = lines["suppliers"]
        created = int(sup_line.split("cargadas ")[1].split(" ")[0])
        assert created > 0 and imported_suppliers() > 0 and imported_suppliers() <= created
        deadline = time.time() + 240
        seen = {}
        while time.time() < deadline:
            seen = inventory_sources()
            if seen["movements"]["rows"] >= loaded_movements - seen["movements"]["quarantined"] and seen["stock_snapshots"]["rows"] > 0:
                break
            time.sleep(10)
        assert seen["stock_snapshots"]["rows"] > 0 and seen["movements"]["rows"] > 0
        before = seen["movements"]["rows"]
        second = load_cli()
        assert second.returncode == 0, second.stdout + second.stderr
        assert second.stdout.count("cargadas 0 | actualizadas 0") == 3        # suppliers, inventory and movements: nothing new
        time.sleep(30)
        assert inventory_sources()["movements"]["rows"] == before
    finally:
        compose("down", "-v", check=False, timeout=300)
