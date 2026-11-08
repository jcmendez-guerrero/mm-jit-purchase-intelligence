"""T105/T037 (FR-011, FR-023, FR-039): the BFF routes of the local loader: roles, idempotency, limits, stable codes, hidden when disabled."""

import httpx
import pytest
from fastapi.testclient import TestClient
from tests_support import headers_for

LOCAL_ENV = {"MMI_LOCAL_LOADER": "1", "MMI_ENV": "dev"}
RESULT = {"run_id": "r1", "kind": "inventory", "file_sha256": "a" * 64, "rows": 3, "loaded": 3, "updated": 0, "unchanged": 0,
          "quarantined": 0, "excluded": 0, "services": 0, "differences": 0, "review": []}


class FakeLoader:
    def __init__(self, healthy=True, status=200, body=None):
        self.healthy, self.status, self.body = healthy, status, body if body is not None else RESULT
        self.calls: list[tuple] = []

    async def health(self) -> bool:
        return self.healthy

    async def request(self, method, path, **kw):
        self.calls.append((method, path, kw))
        if isinstance(self.body, Exception):
            raise self.body
        return self.status, self.body


def app_with(loader, env=None):
    from fastapi import FastAPI
    from routes import local_load
    app = FastAPI()
    app.include_router(local_load.router, prefix="/api")
    app.dependency_overrides[local_load.get_loader_client] = lambda: loader
    return app


def buyer():
    return headers_for("buyer-1", ["viewer", "buyer"])


def viewer():
    return headers_for("viewer-9", ["viewer"])


def files(name="inventario.csv", content=b"SKU,Nombre\nA,B\n"):
    return {"file": (name, content, "text/csv")}


def test_enabled_only_for_the_local_environment():
    from routes.local_load import enabled

    assert enabled(LOCAL_ENV)
    assert not enabled({"MMI_ENV": "dev"})
    assert not enabled({**LOCAL_ENV, "MMI_ENV": "prod"}) and not enabled({**LOCAL_ENV, "MMI_ENV": "staging"})


def test_the_main_app_does_not_expose_the_routes_without_the_flag(monkeypatch):
    monkeypatch.delenv("MMI_LOCAL_LOADER", raising=False)
    import main

    paths = set(main.app.openapi()["paths"])
    assert "/api/costs" in paths or paths, "the main app is up"
    assert not any(p.startswith("/api/local-load") for p in paths)


def test_capability_reports_the_loader_health():
    c = TestClient(app_with(FakeLoader(healthy=True)))
    assert c.get("/api/local-load/capability", headers=buyer()).json() == {"enabled": True}
    c = TestClient(app_with(FakeLoader(healthy=False)))
    assert c.get("/api/local-load/capability", headers=buyer()).json() == {"enabled": False}


def test_capability_is_false_when_the_loader_is_unreachable():
    class Down(FakeLoader):
        async def health(self):
            raise httpx.ConnectError("down")

    assert TestClient(app_with(Down())).get("/api/local-load/capability", headers=buyer()).json() == {"enabled": False}


def test_viewers_and_anonymous_users_are_refused():
    c = TestClient(app_with(FakeLoader()))
    assert c.get("/api/local-load/runs").status_code == 401
    assert c.get("/api/local-load/runs", headers=viewer()).status_code == 403
    assert c.post("/api/local-load/inventory/check", files=files(), headers=viewer()).status_code == 403
    assert c.post("/api/local-load/inventory", files=files(), headers={**viewer(), "Idempotency-Key": "k1"}).status_code == 403


def test_check_forwards_the_file_and_returns_the_counts():
    loader = FakeLoader()
    r = TestClient(app_with(loader)).post("/api/local-load/inventory/check", files=files(), headers=buyer())
    assert r.status_code == 200 and r.json()["rows"] == 3
    assert loader.calls[0][0:2] == ("POST", "/check/inventory")


def test_load_needs_an_idempotency_key_and_forwards_the_acknowledgement():
    loader = FakeLoader()
    c = TestClient(app_with(loader))
    assert c.post("/api/local-load/inventory", files=files(), headers=buyer()).status_code == 400
    r = c.post("/api/local-load/inventory", params={"acknowledge_interpretation": "true"}, files=files(), headers={**buyer(), "Idempotency-Key": "k-1"})
    assert r.status_code == 200
    assert loader.calls[0][2]["params"] == {"acknowledge_interpretation": "true"}


def test_a_repeated_load_with_the_same_key_is_answered_from_memory():
    loader = FakeLoader()
    c = TestClient(app_with(loader))
    h = {**buyer(), "Idempotency-Key": "same-key"}
    a = c.post("/api/local-load/inventory", params={"acknowledge_interpretation": "true"}, files=files(), headers=h)
    b = c.post("/api/local-load/inventory", params={"acknowledge_interpretation": "true"}, files=files(), headers=h)
    assert a.json() == b.json() and len(loader.calls) == 1


@pytest.mark.parametrize(("status", "body", "expected"), [
    (415, {"code": "local_load_type_not_allowed", "message": "x"}, ("local_load_type_not_allowed", 415)),
    (422, {"code": "local_load_signature_mismatch", "message": "x", "missing": ["Lote"], "unexpected": []}, ("local_load_signature_mismatch", 422)),
    (409, {"code": "local_load_interpretation_not_acknowledged", "message": "x"}, ("local_load_interpretation_not_acknowledged", 409)),
])
def test_loader_refusals_keep_their_stable_codes(status, body, expected):
    r = TestClient(app_with(FakeLoader(status=status, body=body))).post("/api/local-load/inventory/check", files=files(), headers=buyer())
    assert (r.json()["detail"], r.status_code) == expected
    if "missing" in body:
        assert r.json()["missing"] == ["Lote"]


def test_oversized_files_are_refused_before_reaching_the_loader(monkeypatch):
    monkeypatch.setenv("MMI_UPLOAD_MAX_BYTES", "1024")
    loader = FakeLoader()
    r = TestClient(app_with(loader)).post("/api/local-load/inventory/check", files=files(content=b"x" * 2048), headers=buyer())
    assert r.status_code == 413 and r.json()["detail"] == "local_load_file_too_large" and loader.calls == []


def test_unsupported_types_and_kinds_are_refused_early():
    loader = FakeLoader()
    c = TestClient(app_with(loader))
    assert c.post("/api/local-load/inventory/check", files=files("a.xlsm"), headers=buyer()).json()["detail"] == "local_load_type_not_allowed"
    assert c.post("/api/local-load/tickets/check", files=files(), headers=buyer()).status_code == 404
    assert loader.calls == []


def test_an_unreachable_loader_gives_a_stable_code():
    r = TestClient(app_with(FakeLoader(body=httpx.ConnectError("down")))).post("/api/local-load/inventory/check", files=files(), headers=buyer())
    assert r.status_code == 502 and r.json()["detail"] == "local_load_unreachable"


def test_the_supplier_file_is_one_of_the_loadable_kinds():
    loader = FakeLoader()
    c = TestClient(app_with(loader))
    assert c.post("/api/local-load/suppliers/check", files=files("proveedores.csv"), headers=buyer()).status_code == 200
    r = c.post("/api/local-load/suppliers", files=files("proveedores.csv"), headers={**buyer(), "Idempotency-Key": "sup-1"})
    assert r.status_code == 200 and [c_[1] for c_ in loader.calls] == ["/check/suppliers", "/load/suppliers"]


def test_runs_review_and_differences_are_proxied():
    loader = FakeLoader(body=[{"kind": "movements", "row": 4, "code": "unknown_sku", "detail": "", "source": "loader"}])
    c = TestClient(app_with(loader))
    assert c.get("/api/local-load/review", headers=buyer()).json()[0]["source"] == "loader"
    c.get("/api/local-load/runs", headers=buyer())
    c.get("/api/local-load/differences", headers=buyer())
    assert [call[1] for call in loader.calls] == ["/review", "/runs", "/differences"]


def test_differences_can_be_accepted_or_ignored_by_buyers_only():
    loader = FakeLoader(body={})
    c = TestClient(app_with(loader))
    assert c.post("/api/local-load/differences/abc-123/accept", headers=viewer()).status_code == 403
    assert c.post("/api/local-load/differences/abc-123/accept", headers=buyer()).status_code == 204
    assert c.post("/api/local-load/differences/abc-123/ignore", headers=buyer()).status_code == 204
    assert c.post("/api/local-load/differences/../accept", headers=buyer()).status_code in (404, 422)


def test_every_load_is_recorded_in_the_audit_without_content(role_store):
    c = TestClient(app_with(FakeLoader()))
    c.post("/api/local-load/inventory", params={"acknowledge_interpretation": "true"}, files=files(), headers={**buyer(), "Idempotency-Key": "audit-1"})
    from routes.admin_roles import get_store

    entry = [e for e in get_store().audit_view() if e.get("action") == "local_load.load"]
    assert entry and "SKU" not in str(entry[-1])


def test_the_bff_calls_the_loader_with_its_own_service_identity(monkeypatch):
    from clients import loader as client_module

    seen = {}

    def fake_token(audience, roles=None, subject=None, auth_time=None):
        seen.update(audience=audience, roles=roles, subject=subject)
        return "tok"

    monkeypatch.setattr(client_module, "get_downstream_token", fake_token)
    headers = client_module.LoaderClient("http://local-loader:8091")._headers()
    assert headers["Authorization"] == "Bearer tok"
    assert seen == {"audience": "api://mmi-local-loader", "roles": ["bff"], "subject": "svc-api-bff"}
