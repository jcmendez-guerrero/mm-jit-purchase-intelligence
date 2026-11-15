"""T156 (procurement part): scenario identifiers are not paths; unknown ids get one stable answer; roles are enforced per action."""

import pytest
from test_scenarios_api import api, h  # noqa: F401  (the same app fixture and headers)

PROBES = ["nope", "0" * 36, "%00", "a" * 300, "..%2F..%2Fetc%2Fpasswd"]


@pytest.mark.parametrize("bad_id", PROBES)
def test_unknown_scenario_ids_get_a_plain_refusal_on_every_scenario_route(api, bad_id):  # noqa: F811
    for method, tail in (("get", ""), ("post", "/promote"), ("get", "/export?format=csv"), ("get", "/export?format=xlsx")):
        res = getattr(api, method)(f"/scenarios/{bad_id}{tail}", headers=h("buyer"))
        detail = res.json().get("detail") if res.headers.get("content-type", "").startswith("application/json") else None
        assert res.status_code in (404, 422), (tail, res.status_code)
        assert detail in ("unknown_scenario", "Not Found", "invalid_input", None) or isinstance(detail, list), (tail, detail)
        if "%00" in bad_id:                                      # a NUL byte never reaches the database (PostgreSQL would answer a server error)
            assert res.status_code == 422 and detail == "invalid_input", (tail, res.status_code)
        assert "Traceback" not in res.text and "/etc/" not in res.text


def test_a_viewer_cannot_create_or_promote(api):  # noqa: F811
    assert api.post("/scenarios", json={"name": "x"}, headers=h("viewer", **{"Idempotency-Key": "abcdefgh1"})).status_code == 403
    assert api.post("/scenarios/anything/promote", json={}, headers=h("viewer")).status_code == 403


def test_a_nul_byte_in_a_body_string_is_refused_not_a_server_error(api):  # noqa: F811
    """T082: PostgreSQL cannot store U+0000, so a name carrying one must be refused before any query (also when the suite runs on PostgreSQL)."""
    res = api.post("/scenarios", content=b'{"name": "a\\u0000b"}', headers={**h("buyer", **{"Idempotency-Key": "abcdefgh2"}), "Content-Type": "application/json"})
    assert res.status_code == 422 and res.json() == {"detail": "invalid_input"}
