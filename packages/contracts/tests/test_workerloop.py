from mmi_common import servicetoken
from mmi_common.workerloop import run


def test_one_pass_by_default(monkeypatch):
    monkeypatch.delenv("MMI_WORKER_LOOP_SECONDS", raising=False)
    calls = []
    assert run(lambda: calls.append(1) or 0) == 0 and calls == [1]


def test_loops_until_stopped_and_keeps_going_after_a_failed_pass(monkeypatch):
    monkeypatch.setenv("MMI_WORKER_LOOP_SECONDS", "5")
    codes, sleeps = iter([1, 0, 1]), []
    assert run(lambda: next(codes), sleeps.append, max_passes=3) == 1 and sleeps == [5.0, 5.0]


def test_dev_issuer_tokens_are_requested_once_and_cached(monkeypatch):
    servicetoken._cache.clear()
    monkeypatch.setenv("MMI_DEV_ISSUER_URL", "http://issuer.test")
    monkeypatch.setenv("MMI_ENV", "dev")
    seen = []

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"access_token": "tok-" + str(len(seen))}

    monkeypatch.setattr(servicetoken.httpx, "post", lambda url, json, timeout: seen.append((url, json)) or R())
    a = servicetoken.service_token("api://mmi-inventory-service", "svc-forecast", ["viewer"])
    b = servicetoken.service_token("api://mmi-inventory-service", "svc-forecast", ["viewer"])
    assert a == b == "tok-1" and len(seen) == 1 and seen[0][1] == {"subject": "svc-forecast", "audience": "api://mmi-inventory-service", "roles": ["viewer"]}


def test_the_dev_issuer_is_refused_outside_dev(monkeypatch):
    import pytest

    servicetoken._cache.clear()
    monkeypatch.setenv("MMI_DEV_ISSUER_URL", "http://issuer.test")
    monkeypatch.setenv("MMI_ENV", "prod")
    with pytest.raises(RuntimeError):
        servicetoken.service_token("api://x", "s")
