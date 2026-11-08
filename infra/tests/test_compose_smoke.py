"""T028: the whole stack boots with zero cloud credentials.

Static checks always run. The live boot runs only with RUN_COMPOSE_SMOKE=1 (needs Docker).
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "infra" / "compose.yaml"
EXPECTED = {"postgres", "azurite", "siweb-mock", "dev-issuer", "siweb-connector", "siweb-cost-writer",
            "inventory-service", "forecast-service", "procurement-service", "api-bff", "web",
            "inventory-worker", "forecast-worker", "procurement-worker", "api-bff-worker"}


def load():
    return yaml.safe_load(COMPOSE.read_text())


def test_all_expected_services_defined():
    assert set(load()["services"]) == EXPECTED


def test_no_cloud_credentials_or_real_hosts_in_compose():
    text = COMPOSE.read_text()
    assert not re.search(r"AZURE_(CLIENT|TENANT|SUBSCRIPTION)|\.azurecr\.io|\.vault\.azure|siweb360\.com", text, re.I)


def test_images_pinned_by_digest():
    for name, svc in load()["services"].items():
        image = svc.get("image")
        if image:
            assert "@sha256:" in image, f"{name} image is not digest-pinned"


def test_each_service_has_own_database_role_and_schema():
    roles = {}
    for name, svc in load()["services"].items():
        url = svc.get("environment", {}).get("MMI_DATABASE_URL")
        if url and not name.endswith("-worker"):
            roles[name] = re.search(r"//([a-z_]+):", url).group(1)
    assert len(set(roles.values())) == len(roles) == 6      # five data services plus the BFF's own `bff` schema


def test_each_worker_runs_as_the_role_of_its_own_service_and_no_other():
    services = load()["services"]
    for name, svc in services.items():
        if name.endswith("-worker"):
            base = name.removesuffix("-worker")
            owner = services[base + "-service" if base + "-service" in services else base]["environment"]["MMI_DATABASE_URL"]
            assert svc["environment"]["MMI_DATABASE_URL"] == owner, f"{name} must use the same schema role as its service"


def test_dockerfiles_run_as_non_root_with_pinned_base():
    for d in [*list((ROOT / "services").glob("*/Dockerfile")), ROOT / "apps/web/Dockerfile", ROOT / "packages/testing/Dockerfile"]:
        text = d.read_text()
        assert re.search(r"^FROM .+@sha256:[0-9a-f]{64}", text, re.M), d
        assert re.search(r"^USER (\d+|app)", text, re.M), f"{d} runs as root"


@pytest.mark.skipif(not (os.environ.get("RUN_COMPOSE_SMOKE") and shutil.which("docker")), reason="live smoke test disabled")
def test_stack_boots_healthy_without_cloud_credentials():
    env = {k: v for k, v in os.environ.items() if not k.startswith(("AZURE_", "ARM_", "AWS_"))}
    base = ["docker", "compose", "-f", str(COMPOSE)]
    try:
        subprocess.run([*base, "up", "-d", "--build", "--wait", "--wait-timeout", "300"], check=True, env=env, cwd=ROOT)
        ps = subprocess.run([*base, "ps", "--format", "json"], check=True, capture_output=True, text=True, env=env, cwd=ROOT)
        rows = [json.loads(line) for line in ps.stdout.splitlines() if line.strip()]
        unhealthy = [r["Service"] for r in rows if r.get("Health") not in ("healthy", "") or r.get("State") != "running"]
        assert not unhealthy, unhealthy
        assert {r["Service"] for r in rows} == EXPECTED
    finally:
        subprocess.run([*base, "down", "-v", "--remove-orphans"], env=env, cwd=ROOT, check=False)
