"""T080 (feature 012, FR-025): the retention commands run as weekly one-replica jobs for inventory and forecast only, inside the cost guardrails."""

import re
from pathlib import Path

BICEP = Path(__file__).resolve().parents[1] / "bicep"
JOBS = (BICEP / "modules" / "serviceJobs.bicep").read_text()
MAIN = (BICEP / "main.bicep").read_text()


def test_the_retention_job_is_weekly_and_runs_the_retention_command_with_a_timeout_cap():
    block = JOBS[JOBS.index("module retention"):]
    assert "param retentionCron string = '0 3 * * 0'" in JOBS
    assert "python -m retention" in block and "cronExpression: retentionCron" in block
    assert int(re.search(r"replicaTimeoutSeconds:\s*(\d+)", block).group(1)) <= 900


def test_only_inventory_and_forecast_get_a_retention_job():
    flagged = re.findall(r"\{ key: '(\w+)'[^\n]*retention: true", MAIN)
    assert flagged == ["inventory", "forecast"]
