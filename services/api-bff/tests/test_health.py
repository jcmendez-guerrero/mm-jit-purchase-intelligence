from fastapi.testclient import TestClient
from main import app


def test_health_and_auth_required():
    c = TestClient(app)
    assert c.get("/healthz").json()["service"] == "api-bff"
    assert c.get("/whoami").status_code == 401
