"""T035, T036, T043, T044, T061 (and T027..T029 below): snapshots, the alert evaluator and its de-duplication, the cards, the queue view."""

import json
import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from db.ops import DEFAULTS, OpsError, OpsStore
from ops.alerts import Facts, evaluate, sync
from ops.snapshots import SnapshotError, parse_snapshot
from routes.admin_roles import get_store
from tests_support import admin_headers, api, forward_by_path, headers_for

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def ops() -> OpsStore:
    return OpsStore(get_store().engine)


def iso(delta_hours: float) -> str:
    return (NOW - timedelta(hours=delta_hours)).isoformat()


def cost_snap(projected="85.00", budget="120.00", **kw):
    return {"kind": "cost", "captured_at": iso(1), "status": "ok",
            "cost": {"currency": "EUR", "budget": budget, "month_to_date": "40.00", "projected": projected, "partial_month": True, **kw}}


def backup_snap(hours_ago=3):
    return {"kind": "backup", "captured_at": iso(1), "status": "ok", "backup": {"last_success_at": iso(hours_ago), "last_restore_drill_at": None}}


def store_snapshot(raw):
    snap = parse_snapshot(raw, NOW)
    ops().add_snapshot(snap.kind, snap.captured_at, str(raw["captured_at"]), snap.payload(), snap.status)


# ---- T043 snapshots ----
@pytest.mark.parametrize("raw", [
    {**cost_snap(), "extra": 1},                                             # unknown field
    {**cost_snap(projected=85.5)},                                           # a float is not money
    {**cost_snap(projected="85,50")},                                        # not a decimal string
    {**cost_snap(), "captured_at": (NOW + timedelta(hours=2)).isoformat()},  # in the future
    {**cost_snap(), "captured_at": "2026-11-10T10:00:00"},                   # no time zone
    {"kind": "backup", "captured_at": iso(1), "status": "ok"},               # payload missing for its kind
    {"kind": "cost", "captured_at": iso(1), "status": "ok", "cost": {**cost_snap()["cost"], "currency": "USD"}},
    "not an object",
])
def test_an_invalid_snapshot_is_refused(raw):
    with pytest.raises(SnapshotError):
        parse_snapshot(raw, NOW)


def test_a_valid_snapshot_is_stored_once_with_its_original_timestamp(tmp_path):
    from worker import ingest_snapshots

    (tmp_path / "a.json").write_text(json.dumps(cost_snap()))
    (tmp_path / "bad.json").write_text(json.dumps({**cost_snap(), "extra": 1}))
    (tmp_path / "junk.json").write_text("{")
    assert ingest_snapshots(ops(), tmp_path, NOW) == {"stored": 1, "rejected": 2}
    assert ingest_snapshots(ops(), tmp_path, NOW) == {"stored": 0, "rejected": 2}          # re-reading is harmless
    snap = ops().latest_snapshot("cost")
    assert snap["captured_at_original"] == iso(1) and snap["payload"]["projected"] == "85.00"


# ---- T035 evaluator and de-duplication ----
def facts(**kw):
    return Facts(now=NOW, settings=dict(DEFAULTS), **kw)


def conditions(f):
    sigs, _ = evaluate(f)
    return {(s.condition_key, s.subject) for s in sigs}


def test_every_condition_is_raised_from_its_facts():
    store_snapshot(cost_snap("100.00"))              # 83 % of the budget
    f = facts(source_last={"snapshots": NOW - timedelta(hours=40), "movements": NOW, "aggregates": None},
              queue_items=[{"kind": "import", "id": "j1", "state": "failed"}, {"kind": "message", "id": "q1", "state": "dead_lettered"}, {"kind": "import", "id": "j2", "state": "succeeded"}],
              mirror_oldest_pending_seconds=16 * 60, backup=None, cost=ops().latest_snapshot("cost"), delivery_configured=False)
    got = conditions(f)
    assert got == {("source_stale", "snapshots"), ("source_stale", "aggregates"), ("job_failed", "import:j1"), ("message_dead_lettered", "message:q1"),
                   ("mirror_lag", "role_mirror"), ("backup_missing", "backup"), ("budget_warning", "azure_budget"), ("delivery_unconfigured", "email")}


def test_thresholds_decide_old_backup_and_budget_levels():
    store_snapshot(backup_snap(hours_ago=30))
    store_snapshot(cost_snap("120.00"))
    got = conditions(facts(backup=ops().latest_snapshot("backup"), cost=ops().latest_snapshot("cost")))
    assert ("backup_old", "backup") in got and ("budget_critical", "azure_budget") in got and ("budget_warning", "azure_budget") not in got


def test_unavailable_inputs_are_unknown_not_healthy():
    _sigs, evaluated = evaluate(facts(source_last=None, queue_items=None, mirror_oldest_pending_seconds=None, cost=None))
    assert not {"source_stale", "job_failed", "message_dead_lettered", "mirror_lag", "budget_warning", "budget_critical"} & evaluated


def test_a_persistent_condition_is_one_open_alert_across_twenty_evaluations_and_one_marker(caplog):
    caplog.set_level(logging.WARNING, logger="mmi.api_bff.alerts")
    f = facts(mirror_oldest_pending_seconds=3600)
    for i in range(20):
        sigs, ev = evaluate(Facts(**{**f.__dict__, "now": NOW + timedelta(minutes=i)}))
        sync(ops(), sigs, ev, NOW + timedelta(minutes=i), 24)
    live = [a for a in ops().list_alerts() if a["condition_key"] == "mirror_lag"]
    assert len(live) == 1 and live[0]["state"] == "open"
    assert caplog.text.count("ADMIN_ALERT_OPENED condition=mirror_lag subject=role_mirror") == 1


def test_an_alert_closes_when_the_condition_clears_and_a_flap_inside_the_interval_does_not_repeat_the_marker(caplog):
    caplog.set_level(logging.WARNING, logger="mmi.api_bff.alerts")
    bad, good = facts(mirror_oldest_pending_seconds=3600), facts(mirror_oldest_pending_seconds=0)
    for t, f in ((0, bad), (1, good), (2, bad)):
        sigs, ev = evaluate(Facts(**{**f.__dict__, "now": NOW + timedelta(hours=t)}))
        sync(ops(), sigs, ev, NOW + timedelta(hours=t), 24)
    rows = [a for a in ops().list_alerts() if a["condition_key"] == "mirror_lag"]
    assert sorted(a["state"] for a in rows) == ["closed", "open"]
    mirror = lambda: caplog.text.count("ADMIN_ALERT_OPENED condition=mirror_lag")  # noqa: E731
    assert mirror() == 1                                                     # the second opening is inside alert_repeat_hours
    sigs, ev = evaluate(Facts(**{**good.__dict__, "now": NOW + timedelta(days=3)}))
    sync(ops(), sigs, ev, NOW + timedelta(days=3), 24)
    sigs, ev = evaluate(Facts(**{**bad.__dict__, "now": NOW + timedelta(days=5)}))
    sync(ops(), sigs, ev, NOW + timedelta(days=5), 24)
    assert mirror() == 2                                                     # after the interval it is announced again


def test_the_marker_carries_only_codes(caplog):
    caplog.set_level(logging.WARNING, logger="mmi.api_bff.alerts")
    sigs, ev = evaluate(facts(queue_items=[{"kind": "import", "id": "J 1/../x", "state": "failed"}]))
    sync(ops(), sigs, ev, NOW, 24)
    line = next(r.getMessage() for r in caplog.records if "ADMIN_ALERT_OPENED" in r.getMessage())
    assert line == "ADMIN_ALERT_OPENED condition=job_failed subject=import:j_1_.._x"


def test_an_unevaluated_condition_keeps_its_alert():
    sigs, ev = evaluate(facts(mirror_oldest_pending_seconds=3600))
    sync(ops(), sigs, ev, NOW, 24)
    sigs, ev = evaluate(facts(mirror_oldest_pending_seconds=None))
    sync(ops(), sigs, ev, NOW, 24)
    assert [a["state"] for a in ops().list_alerts() if a["condition_key"] == "mirror_lag"] == ["open"]


# ---- T036 alerts API, thresholds ----
def downstream():
    inv = forward_by_path({"/status/sources": {"stock_snapshots": {"latest_day": "2026-11-10", "rows": 5}, "movements": {"rows": 9, "quarantined": 1, "latest_at": datetime.now(UTC).isoformat()},
                                                "aggregates": {"refreshed_at": datetime.now(UTC).isoformat()}}})
    fc = forward_by_path({"/imports/jobs": {"jobs": [{"id": "j1", "name": "d", "version": 1, "state": "failed", "error_key": "import_x"}]}, "/runs": {"runs": []}})
    return fc, inv


def test_alerts_list_acknowledge_and_close_flow():
    fc, inv = downstream()
    api("GET", "/api/admin/alerts", admin_headers(), fc=fc, inv=inv)              # first sighting of a failed job: not yet "repeatedly"
    res = api("GET", "/api/admin/alerts", admin_headers(), fc=fc, inv=inv).json()
    keys = {(a["condition_key"], a["subject"]) for a in res["items"]}
    assert ("job_failed", "import:j1") in keys and ("delivery_unconfigured", "email") in keys and res["delivery_configured"] is False
    alert = next(a for a in res["items"] if a["condition_key"] == "job_failed")
    ack = api("POST", f"/api/admin/alerts/{alert['id']}/acknowledge", admin_headers())
    assert ack.status_code == 200 and ack.json()["state"] == "acknowledged" and ack.json()["acknowledged_by"] == "admin-1"
    again = api("POST", f"/api/admin/alerts/{alert['id']}/acknowledge", headers_for("admin-1", ["viewer", "admin"]))
    assert again.json()["state"] == "acknowledged"                              # idempotent
    assert api("POST", "/api/admin/alerts/9999/acknowledge", admin_headers()).status_code == 404
    assert any(r["action"] == "alert.acknowledged" for r in get_store().audit_view())
    fc.forward.side_effect = None
    fc2 = forward_by_path({"/imports/jobs": {"jobs": []}, "/runs": {"runs": []}})
    res2 = api("GET", "/api/admin/alerts", admin_headers(), fc=fc2, inv=inv).json()
    assert next(a for a in res2["items"] if a["id"] == alert["id"])["state"] == "closed"


def test_an_unreachable_downstream_leaves_job_alerts_untouched():
    fc, inv = downstream()
    api("GET", "/api/admin/alerts", admin_headers(), fc=fc, inv=inv)
    api("GET", "/api/admin/alerts", admin_headers(), fc=fc, inv=inv)
    res = api("GET", "/api/admin/alerts", admin_headers(), fc=forward_by_path({}), inv=forward_by_path({})).json()
    assert [a["state"] for a in res["items"] if a["condition_key"] == "job_failed"] == ["open"]


def test_thresholds_are_validated_audited_and_used(monkeypatch):
    assert api("GET", "/api/admin/ops/settings", admin_headers()).json() == DEFAULTS
    ok = api("PUT", "/api/admin/ops/settings", admin_headers(), json={"source_stale_hours": 48, "budget_warn_pct": 70})
    assert ok.status_code == 200 and ok.json()["source_stale_hours"] == 48
    for bad in ({"source_stale_hours": 0}, {"budget_warn_pct": 150}, {"nope": 1}, {"source_stale_hours": "3"}, {"mirror_lag_minutes": True}, {}):
        assert api("PUT", "/api/admin/ops/settings", admin_headers(), json=bad).status_code == 422
    assert any(r["action"] == "ops.settings.changed" for r in get_store().audit_view())
    with pytest.raises(OpsError):
        ops().set_settings({"budget_critical_pct": 60}, "admin-1")               # warn must stay below critical
    assert not api("PUT", "/api/admin/ops/settings", headers_for("buyer-1", ["viewer", "buyer"]), json={"source_stale_hours": 5}).status_code == 200


# ---- T044 cards ----
def summary():
    return api("GET", "/api/admin/ops/summary", admin_headers()).json()


def test_cards_say_unavailable_when_nothing_was_supplied():
    assert summary() == {"backup": {"ok": False, "error": "snapshot_unavailable"}, "cost": {"ok": False, "error": "snapshot_unavailable"}}


def test_cards_show_old_backup_and_budget_levels_in_decimal():
    now = datetime.now(UTC)
    for projected, level in (("50.00", "ok"), ("96.00", "warning"), ("126.00", "critical")):
        ops().add_snapshot("cost", now + timedelta(seconds=len(projected) + int(float(projected))), now.isoformat(), {"currency": "EUR", "budget": "120.00", "month_to_date": "30.00",
                                                                                                                  "projected": projected, "partial_month": True}, "ok")
        c = summary()["cost"]["data"]
        assert c["level"] == level and c["projection_is_estimate"] is True and c["budget"] == "120.00"
    assert c["projected_pct"] == "105.0"
    ops().add_snapshot("backup", now, now.isoformat(), {"last_success_at": (now - timedelta(hours=30)).isoformat(), "last_restore_drill_at": None}, "ok")
    b = summary()["backup"]["data"]
    assert b["old"] is True and b["stale_snapshot"] is False


def test_a_stale_snapshot_is_flagged_not_shown_as_current():
    old = datetime.now(UTC) - timedelta(days=5)
    ops().add_snapshot("backup", old, old.isoformat(), {"last_success_at": old.isoformat(), "last_restore_drill_at": None}, "ok")
    assert summary()["backup"]["data"]["stale_snapshot"] is True


def test_the_status_page_no_longer_carries_a_static_spend_estimate():
    fc, inv = downstream()
    from main import app
    from routes.api import get_procurement_client

    proc = AsyncMock()
    proc.forward.return_value = []
    app.dependency_overrides[get_procurement_client] = lambda: proc
    try:
        cost = api("GET", "/api/admin/status", admin_headers(), fc=fc, inv=inv).json()["cost"]
    finally:
        app.dependency_overrides.pop(get_procurement_client, None)
    assert "estimate_eur" not in cost and cost["budget_eur"] == 120


# ---- T027, T028, T029 queue ----
def test_the_queue_unifies_mirror_jobs_runs_and_snapshot_dead_letters():
    store = get_store()
    store.set_roles("buyer-3", ["viewer", "buyer"], actor="admin-1")
    row = store.due_mirrors(datetime.now(UTC))[0]
    store.mark_attempt_failed(row.id, datetime.now(UTC), "role_mirror_failed", 1)             # one attempt allowed: dead-lettered
    ops().add_snapshot("queues", datetime.now(UTC), "x", {"dead_lettered": [{"queue": "inventory.projections", "count": 2, "reason_code": "poison"}, {"queue": "empty", "count": 0}]}, "ok")
    fc = forward_by_path({"/imports/jobs": {"jobs": [{"id": "j1", "name": "d", "version": 1, "state": "queued", "error_key": None},
                                                    {"id": "j2", "name": "d", "version": 2, "state": "done", "error_key": None},
                                                    {"id": "j3", "name": "d", "version": 3, "state": "failed", "error_key": "import_bad"}]},
                          "/runs": {"runs": [{"id": "r1", "status": "completed"}, {"id": "r2", "status": "running"}]}})
    items = api("GET", "/api/admin/ops/queue", admin_headers(), fc=fc).json()["items"]
    by = {(i["kind"], i["id"]): i for i in items}
    assert by[("mirror", str(row.id))]["state"] == "dead_lettered" and by[("mirror", str(row.id))]["reason_code"] == "role_mirror_failed"
    assert by[("message", "inventory.projections")] == {"kind": "message", "id": "inventory.projections", "state": "dead_lettered", "attempts": 2, "reason_code": "poison", "stale": False}
    assert ("message", "empty") not in by
    assert [by[("import", j)]["state"] for j in ("j1", "j2", "j3")] == ["waiting", "succeeded", "failed"] and by[("import", "j3")]["reason_code"] == "import_bad"
    assert [by[("forecast", r)]["state"] for r in ("r1", "r2")] == ["succeeded", "running"]


def test_retrying_a_dead_lettered_mirror_item_twice_has_one_effect_and_two_audit_entries():
    store = get_store()
    store.set_roles("buyer-3", ["viewer", "buyer"], actor="admin-1")
    row = store.due_mirrors(datetime.now(UTC))[0]
    store.mark_attempt_failed(row.id, datetime.now(UTC), "role_mirror_failed", 1)
    path = f"/api/admin/ops/queue/mirror/{row.id}/retry"
    assert api("POST", path, admin_headers()).json() == {"requeued": 1}
    assert api("POST", path, admin_headers()).json() == {"requeued": 0}
    assert len([r for r in store.audit_view() if r["action"] == "ops.queue.retry"]) == 2
    assert api("POST", "/api/admin/ops/queue/mirror/99999/retry", admin_headers()).status_code == 404


def test_retrying_jobs_goes_through_the_owning_service_and_bad_input_is_refused_before_any_call():
    fc = AsyncMock()
    fc.forward.return_value = {"job_id": "j1", "reused": True}
    assert api("POST", "/api/admin/ops/queue/import/5ba24d0e/retry", admin_headers(), fc=fc).status_code == 202
    assert fc.forward.call_args.args[:2] == ("POST", "/imports/jobs/5ba24d0e/rerun")
    assert api("POST", "/api/admin/ops/queue/forecast/r1/retry", admin_headers(), fc=fc).status_code == 202
    fc.reset_mock()
    for path in ("/api/admin/ops/queue/message/q/retry", "/api/admin/ops/queue/import/x%20y/retry", "/api/admin/ops/queue/mirror/abc/retry"):
        assert api("POST", path, admin_headers(), fc=fc).status_code == 422
    fc.forward.assert_not_called()


def test_a_job_that_cannot_be_rerun_returns_the_owning_services_code():
    import httpx

    fc = AsyncMock()
    fc.forward.side_effect = httpx.HTTPStatusError("x", request=httpx.Request("POST", "http://f"), response=httpx.Response(409, json={"detail": "import_job_not_rerunnable"}))
    res = api("POST", "/api/admin/ops/queue/import/5ba24d0e/retry", admin_headers(), fc=fc)
    assert res.status_code == 409 and res.json() == {"detail": "import_job_not_rerunnable"}


def test_the_freshness_limit_comes_from_settings():
    ops().set_settings({"source_stale_hours": 1}, "admin-1")
    fc, inv = downstream()
    inv = forward_by_path({"/status/sources": {"stock_snapshots": {"latest_day": "2026-11-10", "rows": 5}, "movements": {"rows": 9, "quarantined": 3, "latest_at": (datetime.now(UTC) - timedelta(hours=5)).isoformat()},
                                               "aggregates": {"refreshed_at": datetime.now(UTC).isoformat()}}})
    keys = {a["subject"] for a in api("GET", "/api/admin/alerts", admin_headers(), fc=fc, inv=inv).json()["items"] if a["condition_key"] == "source_stale"}
    assert "movements" in keys


# ---- T060 no ERP calls ----
def test_the_new_admin_code_never_touches_the_erp_client():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src"
    for f in ("routes/admin_ops.py", "routes/admin_audit.py", "db/ops.py", "ops/alerts.py", "ops/snapshots.py", "ops/summary.py"):
        text = (root / f).read_text(encoding="utf-8").lower()
        assert "siweb" not in text and "erp" not in text.replace("verp", ""), f


def test_the_synthetic_fixtures_load_and_the_float_money_one_is_rejected():
    from pathlib import Path

    from worker import ingest_snapshots

    fixtures = Path(__file__).resolve().parents[3] / "packages/testing/fixtures/ops"
    stats = ingest_snapshots(ops(), fixtures, NOW)
    assert stats["rejected"] == 1 and stats["stored"] >= 1                   # invalid_float_money.json; same-kind same-time files de-duplicate


# ---- convergence: T065 worker evaluation, T066 snapshot command, T067 bad timestamps, T068 repeated failures ----
def test_the_worker_pass_alone_opens_stale_source_and_failed_job_alerts_after_repeated_sightings(caplog):
    import asyncio

    from routes.admin_ops import refresh_all

    caplog.set_level(logging.WARNING, logger="mmi.api_bff.alerts")
    fc, inv = downstream()
    who = {"user_id": "svc-api-bff", "roles": ["viewer"]}
    inv = forward_by_path({"/status/sources": {"stock_snapshots": {"latest_day": "2020-01-01", "rows": 5}, "movements": {"rows": 9, "quarantined": 0, "latest_at": datetime.now(UTC).isoformat()},
                                               "aggregates": {"refreshed_at": datetime.now(UTC).isoformat()}}})
    asyncio.run(refresh_all(ops(), inv, fc, who, NOW))
    live = {(a["condition_key"], a["subject"]) for a in ops().list_alerts()}
    assert ("source_stale", "snapshots") in live and ("job_failed", "import:j1") not in live          # the job failed once only
    asyncio.run(refresh_all(ops(), inv, fc, who, NOW + timedelta(minutes=10)))
    live = {(a["condition_key"], a["subject"]) for a in ops().list_alerts()}
    assert ("job_failed", "import:j1") in live
    assert caplog.text.count("ADMIN_ALERT_OPENED condition=job_failed subject=import:j1") == 1
    assert caplog.text.count("ADMIN_ALERT_OPENED condition=source_stale subject=snapshots") == 1


def test_the_worker_asks_for_the_viewer_role_only():
    import asyncio
    from unittest.mock import AsyncMock

    from routes.admin_ops import refresh_all

    inv, fc = AsyncMock(), AsyncMock()
    inv.forward.return_value = {}
    fc.forward.return_value = {}
    asyncio.run(refresh_all(ops(), inv, fc, {"user_id": "svc-api-bff", "roles": ["viewer"]}, NOW))
    for call in (*inv.forward.call_args_list, *fc.forward.call_args_list):
        assert call.kwargs["roles"] == ["viewer"] and call.args[0] == "GET"


def test_a_failure_must_be_seen_repeatedly_and_a_recovery_resets_the_count():
    failed = [{"kind": "import", "id": "j9", "state": "failed"}]
    ok = [{"kind": "import", "id": "j9", "state": "succeeded"}]
    ops().set_settings({"job_failed_observations": 3}, "admin-1")

    def step(items, minutes):
        f = Facts(now=NOW + timedelta(minutes=minutes), settings=ops().settings(), queue_items=items)
        sigs, ev = evaluate(f)
        sync(ops(), sigs, ev, f.now, 24, {"job_failed": f.settings["job_failed_observations"]})
        return [a for a in ops().list_alerts() if a["condition_key"] == "job_failed" and a["state"] != "closed"]

    assert step(failed, 0) == [] and step(failed, 1) == []
    assert step(ok, 2) == []                                       # recovered: the count starts again
    assert step(failed, 3) == [] and step(failed, 4) == []
    assert len(step(failed, 5)) == 1                               # third consecutive sighting
    step(ok, 6)
    assert [a["state"] for a in ops().list_alerts() if a["condition_key"] == "job_failed"] == ["closed"]


def test_a_malformed_source_timestamp_is_flagged_not_a_server_error():
    fc, _ = downstream()
    inv = forward_by_path({"/status/sources": {"stock_snapshots": {"latest_day": "garbage", "rows": 5}, "movements": {"rows": 9, "quarantined": 0, "latest_at": "2026-13-45T99:00:00"},
                                               "aggregates": {"refreshed_at": datetime.now(UTC).isoformat()}}})
    res = api("GET", "/api/admin/alerts", admin_headers(), fc=fc, inv=inv)
    assert res.status_code == 200
    stale = {a["subject"] for a in res.json()["items"] if a["condition_key"] == "source_stale"}
    assert {"snapshots", "movements"} <= stale and "aggregates" not in stale
    odd = forward_by_path({"/status/sources": {"unexpected": True}})
    assert api("GET", "/api/admin/alerts", admin_headers(), fc=fc, inv=odd).status_code == 200


def test_the_snapshot_command_stores_one_valid_file_and_refuses_an_invalid_one(tmp_path, caplog):
    from worker import store_snapshot_file

    good, bad = tmp_path / "good.json", tmp_path / "bad.json"
    good.write_text(json.dumps(backup_snap()))
    bad.write_text(json.dumps({**cost_snap(projected=85.5)}))
    assert store_snapshot_file(ops(), good, NOW) == 0 and store_snapshot_file(ops(), good, NOW) == 0     # twice: stored once
    assert ops().latest_snapshot("backup")["payload"]["last_success_at"]
    caplog.set_level(logging.ERROR)
    assert store_snapshot_file(ops(), bad, NOW) == 1 and "SNAPSHOT_REJECTED" in caplog.text
    assert ops().latest_snapshot("cost") is None
    assert store_snapshot_file(ops(), tmp_path / "missing.json", NOW) == 1
