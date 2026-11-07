"""T150 (FR-038): the Bicep stays inside the shared-budget guardrails recorded in infra/bicep/guardrails.json."""

import json
import re
from pathlib import Path

BICEP = Path(__file__).resolve().parents[1] / "bicep"
G = json.loads((BICEP / "guardrails.json").read_text())
FILES = {p.name: p.read_text() for p in [BICEP / "main.bicep", *(BICEP / "modules").glob("*.bicep")]}
ALL = "\n".join(FILES.values())


def test_the_guardrail_file_states_the_shared_budget():
    assert G["budget_eur_per_month"] == 120


def test_every_app_scales_to_zero_with_a_replica_cap():
    scales = re.findall(r"scale:\s*\{\s*minReplicas:\s*(\d+),\s*maxReplicas:\s*([^}\s]+)\s*\}", ALL)
    assert scales, "no container app scale rule found"
    for lo, hi in scales:
        assert int(lo) == G["apps"]["min_replicas"]
        assert hi == "maxReplicas"                                     # never a literal that bypasses the capped parameter
    for name, text in FILES.items():
        for m in re.finditer(r"param maxReplicas int = (\d+)", text):
            assert int(m.group(1)) <= G["apps"]["max_replicas_cap"], name
        assert not re.search(r"minReplicas:\s*[1-9]", text), name


def test_callers_do_not_raise_the_replica_cap_above_the_guardrail():
    for name, text in FILES.items():
        for m in re.finditer(r"\bmaxReplicas:\s*(\d+)", text):
            assert int(m.group(1)) <= G["apps"]["max_replicas_cap"], name


def test_jobs_run_one_replica_at_a_time_with_a_timeout_cap():
    job = FILES["containerAppJob.bicep"]
    assert "parallelism: 1" in job and "replicaCompletionCount: 1" in job
    assert not re.search(r"parallelism:\s*[2-9]", ALL) and not re.search(r"replicaCompletionCount:\s*[2-9]", ALL)
    assert int(re.search(r"param replicaTimeoutSeconds int = (\d+)", job).group(1)) <= G["jobs"]["max_replica_timeout_seconds"]
    for m in re.finditer(r"replicaTimeoutSeconds:\s*(\d+)", ALL):
        assert int(m.group(1)) <= G["jobs"]["max_replica_timeout_seconds"]


def test_no_always_on_or_expensive_resource_types():
    types = set(re.findall(r"resource \w+ '([A-Za-z./]+)@", ALL))
    assert not types & set(G["forbidden_resource_types"])


def test_only_the_allowed_extra_storage_containers_exist_and_each_expires():
    storage = FILES["storage.bicep"]
    containers = re.findall(r"resource (\w+) 'Microsoft\.Storage/storageAccounts/blobServices/containers@", storage)
    assert len(containers) <= 1 + len(G["storage"]["extra_private_containers_allowed"])
    extra = [c for c in containers if c != "raw"]
    assert len(extra) <= len(G["storage"]["extra_private_containers_allowed"])
    if G["storage"]["lifecycle_rule_required_for_extra_containers"]:
        for c in extra:
            name_var = re.search(rf"resource {c} '[^']+' = \{{.*?name: (\w+)", storage, re.S).group(1)
            assert f"prefixMatch: ['${{{name_var}}}/']" in storage, f"container {c} has no lifecycle rule"
    assert "publicAccess: 'None'" in storage
