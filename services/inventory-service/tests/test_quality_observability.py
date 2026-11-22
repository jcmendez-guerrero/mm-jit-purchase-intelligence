"""T067 (inventory): the recompute reports its duration and outcome in the log, without SKUs, names or secrets."""

import logging

from conftest import auth
from test_quality_api import seed_case


def test_recompute_logs_job_products_state_and_duration(client, engine, caplog):
    sku, _ = seed_case(engine, "smooth")
    with caplog.at_level(logging.INFO, logger="inventory.quality"):
        assert client.post("/quality/recompute", headers=auth("buyer")).status_code == 200
    done = [r.getMessage() for r in caplog.records if r.getMessage().startswith("QUALITY_RECOMPUTE_DONE")]
    assert len(done) == 1 and "products=1" in done[0] and "duration_ms=" in done[0] and "eligibility=not_configured" in done[0]
    assert sku not in done[0]
