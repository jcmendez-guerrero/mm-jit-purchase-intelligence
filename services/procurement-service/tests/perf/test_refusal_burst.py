# ruff: noqa: F811
"""T055 (FR-039, SC-013): a burst of refused requests does not delay other users' term saves (p95 under 300 ms)."""

import statistics
import threading
import time

from refusal_support import app, client, engine, h, sid  # noqa: F401
from sqlalchemy.exc import OperationalError
from test_terms_api import BODY

BUDGET_MS = 300.0


def save(client, sid, i):
    """One terms save. SQLite (this test's stand-in for PostgreSQL) refuses a transaction that tries to turn a read into a write while another
    connection has written meanwhile ("database is locked"); PostgreSQL waits on the row lock instead. The retry is counted in the latency."""
    for attempt in range(5):
        try:
            return client.put(f"/suppliers/{sid}/terms", json={**BODY, "lead_time_days": 1 + i % 20, "reason": f"cambio {i}"},
                              headers=h(**({"If-Match": f'"{i}"'} if i else {})))
        except OperationalError:
            if attempt == 4:
                raise
            time.sleep(0.05)


def test_saves_stay_fast_while_two_hundred_refusals_run_alongside(client, sid):
    stop = threading.Event()

    def burst():
        for i in range(200):
            if stop.is_set():
                return
            client.put(f"/suppliers/{sid}/terms", json={**BODY, "delivery_charge": "-1", "reason": f"r{i % 7}"}, headers=h("viewer" if i % 2 else "buyer"))

    thread = threading.Thread(target=burst)
    thread.start()
    saves = []
    for i in range(30):
        start = time.perf_counter()
        res = save(client, sid, i)
        saves.append((time.perf_counter() - start) * 1000)
        assert res.status_code == 200, res.text
    stop.set()
    thread.join()
    assert statistics.quantiles(saves, n=20)[-1] < BUDGET_MS
