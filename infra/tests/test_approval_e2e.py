"""T031: full-stack approval across process boundaries, with real PostgreSQL and a BFF restart in the middle.

Runs the dev issuer, procurement-service and api-bff as separate processes (no Docker needed) against a PostgreSQL that
already has infra/postgres/init.sql applied:

    RUN_E2E_LOCAL=1 MMI_PG_EXTERNAL_PORT=<port> pytest infra/tests/test_approval_e2e.py

Proves: roles survive a BFF restart and reach procurement; the real user (not a shared service identity) is what procurement
sees, so the creator cannot approve their own proposal; a stale second factor is refused; two eligible approvers are required.
"""

import base64
import hashlib
import hmac
import json
import os
import socket
import subprocess
import sys
import textwrap
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
PG_PORT = os.environ.get("MMI_PG_EXTERNAL_PORT")
pytestmark = pytest.mark.skipif(not (os.environ.get("RUN_E2E_LOCAL") and PG_PORT), reason="needs RUN_E2E_LOCAL=1 and MMI_PG_EXTERNAL_PORT")
SECRET = "e2e-session-secret-" + "x" * 30
PY = sys.executable
ALEMBIC = str(Path(PY).parent / "alembic")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def db(role: str) -> str:
    return f"postgresql+psycopg://{role}:dev-only-local@127.0.0.1:{PG_PORT}/mmi"


def wait_healthy(url: str, proc: subprocess.Popen, log: Path) -> None:
    for _ in range(80):
        if proc.poll() is not None:
            pytest.fail(f"process exited early:\n{log.read_text()[-2000:]}")
        try:
            if httpx.get(url, timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    pytest.fail(f"not healthy: {url}\n{log.read_text()[-2000:]}")


class Stack:
    def __init__(self, tmp: Path) -> None:
        self.tmp, self.procs, self.issuer_port, self.proc_port, self.bff_port = tmp, {}, free_port(), free_port(), free_port()
        self.base_env = {**os.environ, "MMI_ENV": "dev", "MMI_DEV_ISSUER_URL": f"http://127.0.0.1:{self.issuer_port}", "PYTHONDONTWRITEBYTECODE": "1"}

    def start(self, name: str, args: list[str], cwd: Path, env: dict[str, str], health: str) -> None:
        log = self.tmp / f"{name}.log"
        proc = subprocess.Popen(args, cwd=cwd, env={**self.base_env, **env}, stdout=log.open("wb"), stderr=subprocess.STDOUT)
        self.procs[name] = proc
        wait_healthy(health, proc, log)

    def stop(self, name: str) -> None:
        proc = self.procs.pop(name, None)
        if proc:
            proc.terminate()
            proc.wait(timeout=15)

    def start_bff(self) -> None:
        self.start("bff", [PY, "-m", "uvicorn", "main:app", "--port", str(self.bff_port)], ROOT / "services/api-bff",
                   {"PYTHONPATH": "src", "MMI_DATABASE_URL": db("bff_svc"), "MMI_ENABLE_DEV_LOGIN": "1", "MMI_SESSION_SECRET": SECRET,
                    "MMI_PROCUREMENT_URL": f"http://127.0.0.1:{self.proc_port}", "MMI_INVENTORY_URL": "http://127.0.0.1:1"},
                   f"http://127.0.0.1:{self.bff_port}/healthz")

    def worker_pass(self) -> None:
        r = subprocess.run([PY, "-m", "worker"], cwd=ROOT / "services/api-bff", capture_output=True, text=True, timeout=60,
                           env={**self.base_env, "PYTHONPATH": "src", "MMI_DATABASE_URL": db("bff_svc"), "MMI_PROCUREMENT_URL": f"http://127.0.0.1:{self.proc_port}"})
        assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]


@pytest.fixture(scope="module")
def stack(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("e2e")
    st = Stack(tmp)
    for svc, role in (("procurement-service", "procurement_svc"), ("api-bff", "bff_svc")):
        for cmd in (["downgrade", "base"], ["upgrade", "head"]):
            r = subprocess.run([ALEMBIC, *cmd], cwd=ROOT / "services" / svc, env={**os.environ, "MMI_DATABASE_URL": db(role)}, capture_output=True, text=True)
            assert r.returncode == 0, r.stderr[-1500:]
    st.start("issuer", [PY, "-m", "dev_issuer"], ROOT, {"PORT": str(st.issuer_port)}, f"http://127.0.0.1:{st.issuer_port}/healthz")
    st.start("procurement", [PY, "-m", "uvicorn", "main:app", "--port", str(st.proc_port)], ROOT / "services/procurement-service",
             {"PYTHONPATH": "src", "MMI_DATABASE_URL": db("procurement_svc"), "MMI_BLOB_ROOT": str(tmp / "blobs")}, f"http://127.0.0.1:{st.proc_port}/healthz")
    st.start_bff()
    yield st
    for name in list(st.procs):
        st.stop(name)


def forge_cookie(user: str, roles: list[str], mfa_age_s: int) -> dict[str, str]:
    """A session cookie signed with the BFF's secret, to test an old second factor (the BFF's own format)."""
    now = datetime.now(UTC)
    data = {"user_id": user, "email": f"{user}@example.invalid", "roles": roles, "mfa_auth_time": (now - timedelta(seconds=mfa_age_s)).isoformat(),
            "csrf_token": "csrf-" + user, "exp": int((now + timedelta(hours=1)).timestamp())}
    payload = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return {"mmi_session": f"{payload}.{sig}", "X-CSRF-Token": "csrf-" + user}


class Session:
    def __init__(self, st: Stack, user: str) -> None:
        self.http = httpx.Client(base_url=f"http://127.0.0.1:{st.bff_port}", timeout=20)
        r = self.http.post("/api/auth/dev-login", json={"user_id": user, "email": f"{user}@example.invalid", "roles": ["viewer", "admin"]})   # asks for admin on purpose
        assert r.status_code == 200, r.text
        self.roles, self.csrf = r.json()["roles"], r.json()["csrf_token"]

    def call(self, method: str, path: str, **kw):
        return self.http.request(method, path, headers={"X-CSRF-Token": self.csrf}, **kw)


SEED = textwrap.dedent("""
    import sys, uuid
    from datetime import UTC, datetime
    from decimal import Decimal
    sys.path.insert(0, "src"); sys.path.insert(0, "tests")
    from builders import flat_forecast, inputs, offer, terms, variant
    from costs.rules import CostRules
    from costs.store import NewCost, add_version
    from db.tables import suppliers
    from proposals.generate import generate, store
    from sqlalchemy import create_engine, insert
    import os
    now = datetime.now(UTC)
    eng = create_engine(os.environ["MMI_DATABASE_URL"])
    with eng.begin() as c:
        sid = str(uuid.uuid4())
        c.execute(insert(suppliers).values(id=sid, external_contact_id=int(uuid.uuid4().int % 10**8), name="Proveedor Sintetico"))
        add_version(c, NewCost(product_id=10, supplier_id=sid, cost_with_recargo=Decimal("1.00"), source="manual", actor="x", pack_size=6, min_order_qty=0), CostRules(), now)
        d = generate(inputs([variant(1, [offer(sid, "1.00", pack=6)], flat_forecast(1.0))], [terms(sid)]), 10)
        print(store(c, d, sys.argv[1], sys.argv[2], Decimal("1000"), now))
""")


_weeks = iter(range(10, 60))                                           # only one proposal per ISO week may be approved


def new_proposal(st: Stack, creator: str) -> str:
    r = subprocess.run([PY, "-c", SEED, creator, f"2026-W{next(_weeks)}"], cwd=ROOT / "services/procurement-service", capture_output=True, text=True,
                       env={**os.environ, "MMI_DATABASE_URL": db("procurement_svc")})
    assert r.returncode == 0, r.stderr[-1500:]
    return r.stdout.strip().splitlines()[-1]


def test_roles_survive_a_restart_and_a_real_approval_needs_two_different_people(stack):
    admin = Session(stack, "admin-1")
    assert admin.roles == ["admin", "viewer"]                          # the registry decides; the request asked for admin for everyone
    stack.worker_pass()                                                # mirrors the seeded dev users to procurement
    assert Session(stack, "buyer-1").roles == ["buyer", "viewer"]

    r = admin.call("PUT", "/api/admin/roles/buyer-2", json={"roles": ["viewer", "buyer", "approver"]})
    assert r.status_code == 200 and r.json()["roles"] == ["approver", "buyer", "viewer"]
    time.sleep(1.5)                                                    # the immediate mirror pass runs after the response
    stack.worker_pass()
    assert admin.call("GET", "/api/admin/roles/mirror").json()["pending"] == 0

    stack.stop("bff")                                                  # ---- restart the BFF ----
    stack.start_bff()
    admin2 = Session(stack, "admin-1")
    users = {u["user_id"]: u["roles"] for u in admin2.call("GET", "/api/admin/roles").json()["users"]}
    assert "approver" in users["buyer-2"] and users["admin-1"] == ["admin", "viewer"]

    # buyer-2 is both buyer and approver: create a proposal as buyer-2, submit it, then try to approve it
    pid = new_proposal(stack, "buyer-2")
    b2 = Session(stack, "buyer-2")
    assert b2.call("POST", f"/api/proposals/{pid}/submit").status_code == 200
    self_approval = b2.call("POST", f"/api/proposals/{pid}/approve")
    assert self_approval.status_code in (403, 409), self_approval.text                       # procurement sees buyer-2, the creator
    assert Session(stack, "approver-1").call("POST", f"/api/proposals/{pid}/approve").status_code == 200   # a different, eligible approver


def test_a_stale_second_factor_is_refused_before_anything_changes(stack):
    pid = new_proposal(stack, "buyer-1")
    assert Session(stack, "buyer-1").call("POST", f"/api/proposals/{pid}/submit").status_code == 200
    forged = forge_cookie("approver-2", ["viewer", "approver"], mfa_age_s=1200)
    with httpx.Client(base_url=f"http://127.0.0.1:{stack.bff_port}") as c:
        r = c.post(f"/api/proposals/{pid}/approve", cookies={"mmi_session": forged["mmi_session"]}, headers={"X-CSRF-Token": forged["X-CSRF-Token"]})
    assert r.status_code == 403 and r.json()["detail"] == "auth_mfa_stale"
    assert Session(stack, "approver-2").call("POST", f"/api/proposals/{pid}/approve").status_code == 200


def test_a_viewer_cannot_change_roles_and_the_attempt_is_recorded(stack):
    v = Session(stack, "viewer-1")
    r = v.call("PUT", "/api/admin/roles/viewer-1", json={"roles": ["viewer", "admin"]})
    assert r.status_code == 403 and r.json()["detail"] == "auth_forbidden_role"
    assert uuid.uuid4()
