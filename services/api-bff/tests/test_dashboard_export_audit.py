"""Feature 014 (T043, US5): the gateway lets buyers, approvers and admins export the dashboard, refuses a viewer, and audits every attempt (who, what, filters; never rows)."""

from unittest.mock import AsyncMock

import httpx
from db.tables import audit_events
from routes.admin_roles import get_store
from sqlalchemy import select
from test_dashboard_orchestration import call
from tests_support import headers_for

CSV = "﻿Informe;Prueba\r\n\r\nSKU;Producto;Valor (EUR)\r\nSYN-001;Producto;40,00\r\n".encode()


def inventory_returning(response: httpx.Response) -> AsyncMock:
    inv = AsyncMock()
    inv.get.return_value = response
    return inv


def ok(rows="1") -> httpx.Response:
    return httpx.Response(200, content=CSV, headers={"content-type": "text/csv; charset=utf-8", "x-export-rows": rows})


def entries(action):
    with get_store().engine.connect() as c:
        return list(c.execute(select(audit_events).where(audit_events.c.action == action)).all())


def test_a_buyer_gets_the_file_and_one_audit_entry_with_who_what_and_filters_but_no_rows(role_store):
    inv = inventory_returning(ok("1"))
    res = call("/api/dashboard/export?kind=drilldown&drill_kind=inventory_value&supplier_id=sup-a&date_from=2026-10-01", headers_for("buyer-7", ["buyer"]), inv)
    assert res.status_code == 200 and res.content == CSV and res.headers["content-type"].startswith("text/csv")
    assert "attachment" in res.headers["content-disposition"]
    sent = inv.get.call_args
    assert sent.args[0] == "/dashboard/export" and sent.kwargs["params"] == {"kind": "drilldown", "drill_kind": "inventory_value", "supplier_id": "sup-a", "date_from": "2026-10-01"}
    [entry] = entries("dashboard.exported")
    assert entry.actor == "buyer-7" and entry.after == {"kind": "drilldown", "view": "inventory_value", "filters": {"supplier_id": "sup-a", "date_from": "2026-10-01"}, "rows": 1}
    assert "SYN-001" not in str(entry.after) and "40,00" not in str(entry.after)


def test_approvers_and_admins_may_export_too(role_store):
    for role in ("approver", "admin"):
        assert call("/api/dashboard/export?kind=cards", headers_for("u-" + role, [role]), inventory_returning(ok())).status_code == 200


def test_a_viewer_is_refused_before_inventory_is_asked_and_the_refusal_is_audited(role_store):
    inv = inventory_returning(ok())
    res = call("/api/dashboard/export?kind=cards", headers_for("viewer-1", ["viewer"]), inv)
    assert res.status_code == 403
    inv.get.assert_not_called()
    assert any(r["action"] == "access.refused" and r["actor"] == "viewer-1" for r in get_store().audit_view())


def test_a_result_that_is_too_large_is_refused_with_a_clear_code_and_audited(role_store):
    inv = inventory_returning(httpx.Response(413, json={"detail": "export_too_large"}))
    res = call("/api/dashboard/export?kind=drilldown&drill_kind=inventory_value", headers_for("buyer-7", ["buyer"]), inv)
    assert res.status_code == 413 and res.json()["detail"] == "export_too_large"
    assert not entries("dashboard.exported")
    [entry] = entries("dashboard.export.refused")
    assert entry.actor == "buyer-7" and entry.after["reason"] == "export_too_large" and entry.after["view"] == "inventory_value"


def test_an_unsupported_format_is_refused_without_asking_inventory_and_audited(role_store):
    inv = inventory_returning(ok())
    res = call("/api/dashboard/export?kind=cards&format=xlsx", headers_for("buyer-7", ["buyer"]), inv)
    assert res.status_code == 400 and res.json()["detail"] == "format_unsupported"
    inv.get.assert_not_called()
    assert entries("dashboard.export.refused")[0].after["reason"] == "format_unsupported"


def test_a_bad_request_is_refused_by_shape_and_a_downstream_failure_shows_no_downstream_text(role_store):
    inv = inventory_returning(ok())
    for bad in ("kind=tabloid", "kind=chart&chart=Bad;Key", "kind=cards&format=pdf", "kind=cards&category=Z", "kind=cards&date_from=soon"):
        assert call("/api/dashboard/export?" + bad, headers_for("buyer-7", ["buyer"]), inv).status_code == 422, bad
    inv.get.assert_not_called()
    broken = inventory_returning(httpx.Response(500, text="Traceback secret-host-name"))
    res = call("/api/dashboard/export?kind=cards", headers_for("buyer-7", ["buyer"]), broken)
    assert res.status_code == 502 and "secret-host-name" not in res.text and not entries("dashboard.exported")


def test_a_double_click_is_two_independent_requests_each_audited_once(role_store):
    inv = inventory_returning(ok())
    for _ in range(2):
        assert call("/api/dashboard/export?kind=cards", headers_for("buyer-7", ["buyer"]), inv).status_code == 200
    assert len(entries("dashboard.exported")) == 2
