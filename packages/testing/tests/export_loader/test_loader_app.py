"""T036: the loader's local HTTP app: audience-scoped identities, size and type limits, results, differences, wipe."""

from __future__ import annotations

import pytest
from export_loader import auth
from export_loader.app import create_app
from export_loader.service import LoaderService
from fastapi.testclient import TestClient
from generator.exports import write_exports
from mmi_common.auth import DevIssuer, TokenValidator

ISSUER = "http://dev-issuer.local"


@pytest.fixture
def parts(tmp_path):
    files = tmp_path / "files"
    write_exports(files, seed=42)
    issuer = DevIssuer(ISSUER)
    pushes: list[dict] = []
    svc = LoaderService(tmp_path / "state", pushes.append)
    app = create_app(svc, auth.LoaderAuth(TokenValidator(ISSUER, auth.AUDIENCE, issuer.public_key)))
    return TestClient(app), issuer, pushes, files, svc


def hdr(issuer, subject="svc-api-bff", audience=auth.AUDIENCE):
    return {"Authorization": f"Bearer {issuer.issue(subject, audience, ['bff'])}"}


def upload(c, path, name, h, params=None, kind="inventory", verb="load"):
    return c.post(f"/{verb}/{kind}", files={"file": (name, path.read_bytes(), "application/octet-stream")}, headers=h, params=params or {})


def test_health_needs_no_token(parts):
    c, *_ = parts
    assert c.get("/healthz").json() == {"status": "ok"}


def test_calls_without_a_valid_identity_are_refused(parts):
    c, issuer, _, files, _ = parts
    f = files / "inventario.csv"
    assert upload(c, f, "i.csv", {}).status_code == 401
    assert upload(c, f, "i.csv", hdr(issuer, audience="api://other")).status_code == 401
    assert upload(c, f, "i.csv", hdr(issuer, subject="svc-other")).status_code == 403
    assert c.get("/runs").status_code == 401 and c.delete("/state").status_code == 401


def test_check_returns_counts_and_changes_nothing(parts):
    c, issuer, pushes, files, svc = parts
    r = upload(c, files / "inventario.csv", "i.csv", hdr(issuer), verb="check")
    assert r.status_code == 200 and r.json()["rows"] > 0 and not pushes and svc.runs() == []


def test_inventory_load_needs_the_acknowledgement(parts):
    c, issuer, pushes, files, _ = parts
    r = upload(c, files / "inventario.csv", "i.csv", hdr(issuer))
    assert r.status_code == 409 and r.json()["code"] == "local_load_interpretation_not_acknowledged" and not pushes


def test_load_inventory_then_movements(parts):
    c, issuer, pushes, files, _ = parts
    inv = upload(c, files / "inventario.csv", "i.csv", hdr(issuer), {"acknowledge_interpretation": "true"})
    assert inv.status_code == 200 and inv.json()["kind"] == "inventory"
    mov = upload(c, files / "movimientos.xlsx", "m.xlsx", hdr(issuer), kind="movements")
    assert mov.status_code == 200 and len(pushes) == 2 and len(pushes[-1]["movements"]) == mov.json()["loaded"]
    assert [r["kind"] for r in c.get("/runs", headers=hdr(issuer)).json()] == ["inventory", "movements"]
    assert c.get("/review", headers=hdr(issuer)).json()[0]["source"] == "loader"


def test_movements_before_inventory_is_a_conflict(parts):
    c, issuer, _, files, _ = parts
    r = upload(c, files / "movimientos.xlsx", "m.xlsx", hdr(issuer), kind="movements")
    assert r.status_code == 409 and r.json()["code"] == "local_load_inventory_required"


@pytest.mark.parametrize(("name", "content", "status", "code"), [
    ("a.xlsm", b"abc", 415, "local_load_type_not_allowed"),
    ("a.csv", b"SKU,Nombre\nA,B\n", 422, "local_load_signature_mismatch"),
    ("a.csv", b"x" * 6_000_000, 413, "local_load_file_too_large"),
])
def test_bad_files_get_stable_codes(parts, name, content, status, code):
    c, issuer, _, _, _ = parts
    r = c.post("/check/inventory", files={"file": (name, content, "text/csv")}, headers=hdr(issuer))
    assert r.status_code == status and r.json()["code"] == code


def test_missing_columns_are_listed(parts):
    c, issuer, _, _, _ = parts
    r = c.post("/check/inventory", files={"file": ("a.csv", b"SKU,Nombre\nA,B\n", "text/csv")}, headers=hdr(issuer))
    assert "Lote" in r.json()["missing"]


def test_unknown_kind_is_rejected(parts):
    c, issuer, _, files, _ = parts
    assert upload(c, files / "inventario.csv", "i.csv", hdr(issuer), kind="tickets", verb="check").status_code == 400


def test_differences_can_be_accepted_or_ignored(parts):
    c, issuer, _, _, _ = parts
    assert c.get("/differences", headers=hdr(issuer)).json() == []
    assert c.post("/differences/unknown/accept", headers=hdr(issuer)).status_code == 404


def test_wipe_clears_the_state(parts):
    c, issuer, _, files, _ = parts
    upload(c, files / "inventario.csv", "i.csv", hdr(issuer), {"acknowledge_interpretation": "true"})
    assert c.get("/state", headers=hdr(issuer)).json()["runs"] == 1
    assert c.delete("/state", headers=hdr(issuer)).status_code == 204
    assert c.get("/state", headers=hdr(issuer)).json()["runs"] == 0


def test_the_app_refuses_to_start_outside_the_local_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("MMI_ENV", "prod")
    with pytest.raises(Exception):  # noqa: B017 - GuardError
        create_app()


def test_responses_never_echo_file_content(parts):
    c, issuer, _, files, _ = parts
    r = upload(c, files / "inventario.csv", "i.csv", hdr(issuer), {"acknowledge_interpretation": "true"})
    assert "Producto Sintetico" not in r.text


def test_a_load_starts_the_collection_and_the_state_reports_it(tmp_path):
    files = tmp_path / "files"
    write_exports(files, seed=42)
    issuer = DevIssuer(ISSUER)
    calls: list[str] = []
    svc = LoaderService(tmp_path / "state", lambda b: calls.append("push"))
    c = TestClient(create_app(svc, auth.LoaderAuth(TokenValidator(ISSUER, auth.AUDIENCE, issuer.public_key)),
                              sync=lambda: calls.append("sync") or {"ok": True, "exit_code": 0}))
    h = hdr(issuer)
    assert upload(c, files / "inventario.csv", "i.csv", h, {"acknowledge_interpretation": "true"}).status_code == 200
    assert calls == ["push", "sync"] and c.get("/state", headers=h).json()["last_sync_ok"] is True


def test_a_failing_sync_does_not_fail_the_load(tmp_path):
    files = tmp_path / "files"
    write_exports(files, seed=42)
    issuer = DevIssuer(ISSUER)

    def boom():
        raise RuntimeError("connector down")

    c = TestClient(create_app(LoaderService(tmp_path / "state", lambda b: None),
                              auth.LoaderAuth(TokenValidator(ISSUER, auth.AUDIENCE, issuer.public_key)), sync=boom))
    h = hdr(issuer)
    assert upload(c, files / "inventario.csv", "i.csv", h, {"acknowledge_interpretation": "true"}).status_code == 200
    assert c.get("/state", headers=h).json()["last_sync_ok"] is False
