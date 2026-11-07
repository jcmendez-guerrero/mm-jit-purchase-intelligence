"""T146 / T152: the whole pipeline in real containers: Siweb mock -> connector -> inventory -> forecast -> procurement -> proposal.

Runs the Compose stack under its own project name with no published ports, so it can sit beside a stack that is already up.
It needs Docker, builds the images (minutes) and about 1.5 GiB of memory: skipped unless RUN_E2E=1 (a CI job sets it).
"""

import os
import shutil
import subprocess
import tempfile
import textwrap
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROJECT = f"mmi-e2e-{os.getpid()}"
pytestmark = pytest.mark.skipif(not (os.environ.get("RUN_E2E") and shutil.which("docker")), reason="needs Docker and RUN_E2E=1")
CORE = ["postgres", "azurite", "siweb-mock", "dev-issuer", "inventory-service", "forecast-service", "procurement-service"]
WORKERS = ["inventory-worker", "forecast-worker", "procurement-worker"]


@pytest.fixture(scope="module")
def dc():
    override = Path(tempfile.mkdtemp()) / "no-ports.yml"
    override.write_text(textwrap.dedent("""
        services:
          siweb-mock: { ports: !reset [] }
          api-bff: { ports: !reset [] }
          web: { ports: !reset [] }
    """))
    base = ["docker", "compose", "-p", PROJECT, "-f", str(ROOT / "infra/compose.yaml"), "-f", str(override)]

    def run(*args: str, timeout: int = 900, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run([*base, *args], capture_output=True, text=True, timeout=timeout, check=check, cwd=ROOT / "infra")

    try:
        run("up", "-d", "--build", "--wait", "--wait-timeout", "600", *CORE, timeout=1500)
        yield run
    finally:
        run("down", "-v", "--remove-orphans", check=False, timeout=300)


def sql(dc, query: str) -> str:
    return dc("exec", "-T", "postgres", "psql", "-U", "mmi_admin", "-d", "mmi", "-tAc", query).stdout.strip()


def wait_for(dc, query: str, want: str, seconds: int = 240) -> str:
    deadline, last = time.time() + seconds, ""
    while time.time() < deadline:
        last = sql(dc, query)
        if last == want:
            return last
        time.sleep(5)
    pytest.fail(f"{query!r} stayed at {last!r}, wanted {want!r}")


def test_a_sync_reaches_a_proposal_through_every_service(dc):
    dc("up", "-d", *WORKERS)
    job = dc("run", "--rm", "-T", "siweb-connector", "sh", "-c", "cd /app/services/siweb-connector && alembic upgrade head >/dev/null 2>&1 && python -m job all", timeout=900)
    assert job.stdout.count("SYNC_OK") == 6 and "SYNC_FAILED" not in job.stdout and "PURGE_OK" in job.stdout

    wait_for(dc, "select (select count(*) from inventory.stock_movements) > 6000 and (select count(*) from inventory.product_segments) > 700 and (select count(*) from inventory.stock_lots) > 1000", "t")
    wait_for(dc, "select count(*) from forecasting.forecast_runs where status = 'completed'", "1")
    wait_for(dc, "select count(*) from procurement.forecast_runs_seen", "1")
    assert int(sql(dc, "select count(*) from procurement.supplier_costs")) > 500                      # ERP supplier rows reached procurement
    assert sql(dc, "select count(*) from integration.outbox where status <> 'sent'") == "0"          # every event left the connector
    assert sql(dc, "select count(*) from inventory.outbox where status <> 'sent'") == "0"
    assert sql(dc, "select count(*) from forecasting.outbox where status <> 'sent'") == "0"

    probe = textwrap.dedent("""
        import os, httpx
        r = httpx.post(os.environ["MMI_DEV_ISSUER_URL"] + "/token", json={"subject": "dev-buyer-1", "audience": "api://mmi-procurement-service", "roles": ["viewer", "buyer"]}, timeout=10)
        h = {"Authorization": "Bearer " + r.json()["access_token"]}
        g = httpx.post("http://localhost:8000/proposals", headers=h, timeout=300)
        p = httpx.get("http://localhost:8000/proposals/" + g.json()["id"], headers=h, timeout=60).json()
        print("RESULT", g.status_code, p["status"], len(p["lines"]), p["solver_status"])
    """)
    out = dc("exec", "-T", "procurement-service", "python", "-c", probe, timeout=600).stdout
    status, state, lines, solver = out.split("RESULT", 1)[1].split()
    assert (status, state, solver) == ("202", "draft", "optimal") and int(lines) > 0


def test_an_admin_can_re_forecast_and_unchanged_inputs_reuse_the_run(dc):
    """T168: the forecast API holds a series source in Compose, so a re-run on request answers 202 and reuses the existing run."""
    probe = textwrap.dedent("""
        import os, httpx
        r = httpx.post(os.environ["MMI_DEV_ISSUER_URL"] + "/token", json={"subject": "dev-admin-1", "audience": "api://mmi-forecast-service", "roles": ["viewer", "admin"]}, timeout=10)
        h = {"Authorization": "Bearer " + r.json()["access_token"]}
        g = httpx.post("http://localhost:8000/runs", headers=h, timeout=600)
        print("RESULT", g.status_code, g.json().get("reused"))
    """)
    out = dc("exec", "-T", "forecast-service", "python", "-c", probe, timeout=900).stdout
    status, reused = out.split("RESULT", 1)[1].split()
    assert (status, reused) == ("202", "True")
