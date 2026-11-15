import pytest
from fastapi.testclient import TestClient
from mmi_common.auth import DevIssuer, TokenValidator
from mmi_common.service import create_service_app, validator_from_env
from starlette.requests import Request


@pytest.fixture
def setup():
    issuer = DevIssuer()
    app = create_service_app("demo", validator=TokenValidator(issuer.issuer, "api://mmi-demo", issuer.public_key))
    return issuer, TestClient(app)


def test_health_endpoints_need_no_auth(setup):
    _, c = setup
    assert c.get("/healthz").json() == {"status": "ok", "service": "demo"}
    assert c.get("/readyz").status_code == 200


def test_whoami_requires_valid_token(setup):
    issuer, c = setup
    assert c.get("/whoami").status_code == 401
    assert c.get("/whoami", headers={"Authorization": "Bearer junk"}).status_code == 401
    wrong_aud = issuer.issue("u", "api://other")
    assert c.get("/whoami", headers={"Authorization": f"Bearer {wrong_aud}"}).status_code == 401
    ok = issuer.issue("svc", "api://mmi-demo", roles=["reader"])
    r = c.get("/whoami", headers={"Authorization": f"Bearer {ok}"})
    assert r.status_code == 200 and r.json() == {"subject": "svc", "roles": ["reader"]}


def test_readiness_failure_is_503():
    app = create_service_app("demo", validator=None, readiness=[lambda: False])
    assert TestClient(app).get("/readyz").status_code == 503


def test_dev_issuer_refused_outside_dev(monkeypatch):
    monkeypatch.setenv("MMI_DEV_ISSUER_URL", "http://x")
    monkeypatch.setenv("MMI_ENV", "production")
    with pytest.raises(RuntimeError):
        validator_from_env("api://a")


@pytest.mark.parametrize("path", ["/items/%00", "/items/a%00b", "/items/x?q=%00", "/%00"])
def test_a_nul_byte_in_the_path_or_query_is_refused_before_any_route_runs(path):
    """T081: PostgreSQL cannot store a NUL byte, so an id carrying one would reach the database and come back as a server error."""
    app = create_service_app("demo", validator=None)
    reached = []

    @app.get("/items/{item_id}")
    def item(item_id: str):
        reached.append(item_id)
        return {"id": item_id}

    res = TestClient(app).get(path)
    assert res.status_code == 422 and res.json() == {"detail": "invalid_input"} and not reached
    assert TestClient(app).get("/items/ok").json() == {"id": "ok"}


def _echo_app():
    app = create_service_app("demo", validator=None)
    reached = []

    @app.post("/echo")
    def echo(body: dict):
        reached.append(body)
        return {"ok": True}

    return app, reached


@pytest.mark.parametrize("raw", [
    b'{"a": "x\\u0000y"}',                       # an escaped NUL inside a string
    b'{"a": {"b": ["fine", "\\u0000"]}}',        # nested
    b'{"a": "x\x00y"}',                          # a raw NUL byte
    b'{"a": "\\\\\\u0000"}',                     # an escaped backslash followed by an escaped NUL: still a NUL
])
def test_a_nul_byte_in_a_json_body_is_refused_before_the_route_runs(raw):
    """T082: the same refusal as for the path, because a JSON string can carry the NUL that PostgreSQL cannot store."""
    app, reached = _echo_app()
    res = TestClient(app).post("/echo", content=raw, headers={"Content-Type": "application/json"})
    assert res.status_code == 422 and res.json() == {"detail": "invalid_input"} and not reached


@pytest.mark.parametrize("raw", [
    b'{"a": "plain"}',
    b'{"a": "\\\\u0000"}',                       # a backslash followed by the text u0000: not a NUL
    b'{"a": "caf\\u00e9"}',
])
def test_a_body_without_a_nul_reaches_the_route_unchanged(raw):
    app, reached = _echo_app()
    res = TestClient(app).post("/echo", content=raw, headers={"Content-Type": "application/json"})
    assert res.status_code == 200 and len(reached) == 1


def test_only_json_bodies_are_inspected():
    """An upload is not JSON: its bytes are the route's business."""
    app = create_service_app("demo", validator=None)

    @app.post("/upload")
    async def upload(request: Request):
        return {"size": len(await request.body())}

    res = TestClient(app).post("/upload", content=b"a\x00b", headers={"Content-Type": "application/octet-stream"})
    assert res.status_code == 200 and res.json() == {"size": 3}


@pytest.mark.parametrize("content_type", ["Application/JSON", "application/json; charset=utf-8", "APPLICATION/JSON;charset=UTF-8", "application/vnd.api+json"])
def test_the_nul_guard_reads_a_json_content_type_whatever_its_case_or_suffix(content_type):
    """Agent 00 review of PR 22: the content type is case-insensitive, and a +json media type is JSON too."""
    app, reached = _echo_app()
    res = TestClient(app).post("/echo", content=b'{"a": "x\\u0000y"}', headers={"Content-Type": content_type})
    assert res.status_code == 422 and res.json() == {"detail": "invalid_input"} and not reached


def test_a_body_declared_larger_than_the_inspection_cap_is_left_to_the_route_and_never_read_by_the_guard():
    """Agent 00 review of PR 22: the guard must not hold a very large body in memory; the route (or the service's own size limit) deals with it."""
    from mmi_common import service

    app, reached = _echo_app()
    big = b'{"a": "' + b"x" * (service.MAX_INSPECTED_BODY + 10) + b'"}'
    res = TestClient(app).post("/echo", content=big, headers={"Content-Type": "application/json"})
    assert res.status_code == 200 and len(reached) == 1
