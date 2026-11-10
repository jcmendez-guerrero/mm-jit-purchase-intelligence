"""T018, T019, T020, T059: audit filters and paging, verification of a tampered chain, the capped export, UTC times, no sensitive output."""

import csv
import io
import logging

from db.tables import audit_events
from routes import admin_audit
from routes.admin_roles import get_store
from sqlalchemy import update
from tests_support import admin_headers, api, headers_for


def seed():
    s = get_store()
    s.set_roles("buyer-3", ["viewer", "buyer"], actor="admin-1")
    s.set_roles("buyer-3", ["viewer"], actor="admin-1")
    s.record_refusal("buyer-1", "access.refused", "PUT /api/admin/roles/x", after={"reason": "forbidden_missing_role"})
    s.record_action("admin-1", "admin.rerun", "forecast", after={"state": "queued"})


def test_filters_by_person_action_outcome_and_range_and_pages_with_a_cursor():
    seed()
    rows = api("GET", "/api/admin/audit", admin_headers()).json()["items"]
    assert [r["id"] for r in rows] == sorted((r["id"] for r in rows), reverse=True)           # newest first
    assert all(r["ts"].endswith("+00:00") for r in rows)                                       # UTC (FR-023)
    refused = api("GET", "/api/admin/audit?outcome=refused", admin_headers()).json()["items"]
    assert [r["actor"] for r in refused] == ["buyer-1"] and refused[0]["reason_code"] == "forbidden_missing_role"
    assert {r["action"] for r in api("GET", "/api/admin/audit?actor=admin-1&outcome=allowed", admin_headers()).json()["items"]} == {"roles.changed", "admin.rerun"}
    assert len(api("GET", "/api/admin/audit?action=roles.changed", admin_headers()).json()["items"]) == 2
    assert api("GET", "/api/admin/audit?from=2999-01-01T00:00:00Z", admin_headers()).json()["items"] == []
    first = api("GET", "/api/admin/audit?limit=2", admin_headers()).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    second = api("GET", f"/api/admin/audit?limit=2&cursor={first['next_cursor']}", admin_headers()).json()
    assert {r["id"] for r in first["items"]}.isdisjoint(r["id"] for r in second["items"])
    assert api("GET", "/api/admin/audit?outcome=weird", admin_headers()).status_code == 422
    assert api("GET", "/api/admin/audit?from=not-a-date", admin_headers()).status_code == 422


def test_only_admins_see_the_trail_and_the_refusal_is_audited():
    res = api("GET", "/api/admin/audit", headers_for("buyer-1", ["viewer", "buyer"]))
    assert res.status_code == 403
    assert any(r["action"] == "access.refused" and r["actor"] == "buyer-1" for r in get_store().audit_view())


def test_rows_never_carry_the_before_and_after_bodies():
    seed()
    for r in api("GET", "/api/admin/audit", admin_headers()).json()["items"]:
        assert set(r) == {"id", "ts", "actor", "action", "entity", "entity_id", "outcome", "reason_code"}


def test_verify_is_ok_then_reports_the_first_broken_row_on_tampering():
    seed()
    ok = api("GET", "/api/admin/audit/verify", admin_headers()).json()
    assert ok["ok"] is True and ok["checked"] >= 4 and ok["first_broken_id"] is None
    with get_store().engine.begin() as conn:
        conn.execute(update(audit_events).where(audit_events.c.id == 2).values(actor="mallory"))
    bad = api("GET", "/api/admin/audit/verify", admin_headers()).json()
    assert bad["ok"] is False and bad["first_broken_id"] == 2


def test_export_is_csv_audited_and_capped(monkeypatch):
    seed()
    monkeypatch.setattr(admin_audit, "EXPORT_CAP", 3)
    res = api("GET", "/api/admin/audit/export", admin_headers())
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv")
    assert res.headers["X-Export-Truncated"] == "true"
    rows = list(csv.DictReader(io.StringIO(res.text)))
    assert len(rows) == 3 and list(rows[0]) == list(admin_audit.FIELDS)
    assert any(r["action"] == "audit.exported" and r["actor"] == "admin-1" for r in get_store().audit_view())
    monkeypatch.setattr(admin_audit, "EXPORT_CAP", 10_000)
    assert api("GET", "/api/admin/audit/export", admin_headers()).headers["X-Export-Truncated"] == "false"


def test_a_cell_that_starts_like_a_formula_is_neutralised_in_the_export():
    get_store().record_action("=HYPERLINK(1)", "admin.rerun", "forecast")
    text = api("GET", "/api/admin/audit/export", admin_headers()).text
    assert ",'=HYPERLINK(1)," in text


def test_no_token_secret_address_or_free_text_in_rows_exports_or_logs(caplog):
    caplog.set_level(logging.DEBUG)
    seed()
    api("PUT", "/api/admin/roles/buyer-9", admin_headers(), json={"roles": ["viewer", "buyer"]})
    api("POST", "/api/admin/rerun/mirror", headers_for("admin-1", ["viewer", "admin"], mfa_age_seconds=999))
    rows = api("GET", "/api/admin/audit", admin_headers()).json()
    export = api("GET", "/api/admin/audit/export", admin_headers()).text
    blob = (str(rows) + export + caplog.text).lower()
    for needle in ("@", "bearer", "token=", "password", "secret", "note", "cookie", "csrf"):
        assert needle not in blob, needle


def test_audit_times_are_stored_in_utc():
    seed()
    with get_store().engine.connect() as conn:
        from sqlalchemy import select

        for r in conn.execute(select(audit_events.c.ts)).all():
            assert r.ts.tzinfo is None or r.ts.utcoffset().total_seconds() == 0
