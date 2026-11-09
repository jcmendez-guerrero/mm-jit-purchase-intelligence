"""T019 (FR-014): a retried terms save with the same Idempotency-Key creates one version and returns the original result.

The key is checked before the If-Match precondition, because a retry after a lost response carries a version that is already stale.
"""

from __future__ import annotations

from conftest import add_supplier, auth
from db.tables import terms_idempotency
from sqlalchemy import func, select
from terms.service import history
from test_terms_api import BODY, seed

OVERRIDE = {"lead_time_days": 5, "pack_multiple": 6, "reason": "alta"}


def put(client, sid, body=BODY, etag=None, key=None):
    headers = auth("buyer")
    if etag is not None:
        headers["If-Match"] = f'"{etag}"'
    if key is not None:
        headers["Idempotency-Key"] = key
    return client.put(f"/suppliers/{sid}/terms", json=body, headers=headers)


def put_override(client, sid, body=OVERRIDE, etag=None, key=None, variant=1):
    headers = auth("buyer")
    if etag is not None:
        headers["If-Match"] = f'"{etag}"'
    if key is not None:
        headers["Idempotency-Key"] = key
    return client.put(f"/product-suppliers/{variant}/{sid}/terms", json=body, headers=headers)


def versions(engine, sid):
    with engine.begin() as c:
        return [h["version"] for h in history(c, sid)]


def test_a_retry_with_the_same_key_returns_the_original_result_and_creates_no_second_version(client, engine):
    sid = seed(engine)
    first = put(client, sid, key="key-1")
    assert first.status_code == 200 and first.json() == {"version": 1} and "idempotent-replay" not in first.headers
    again = put(client, sid, key="key-1")                                      # no If-Match: it would be a 428 without the key
    assert again.status_code == 200 and again.json() == {"version": 1} and again.headers["idempotent-replay"] == "true"
    assert versions(engine, sid) == [1]


def test_a_retry_whose_if_match_is_already_stale_is_still_a_replay_not_a_conflict(client, engine):
    sid = seed(engine)
    put(client, sid)
    second = put(client, sid, {**BODY, "lead_time_days": 4}, etag=1, key="key-2")
    assert second.json() == {"version": 2}
    retry = put(client, sid, {**BODY, "lead_time_days": 4}, etag=1, key="key-2")   # the response was lost; version 1 is stale now
    assert retry.status_code == 200 and retry.json() == {"version": 2} and retry.headers["idempotent-replay"] == "true"
    assert versions(engine, sid) == [1, 2]


def test_the_same_key_with_other_content_is_refused_and_stores_nothing(client, engine):
    sid = seed(engine)
    put(client, sid, key="key-3")
    other = put(client, sid, {**BODY, "lead_time_days": 9}, key="key-3")
    assert other.status_code == 422 and other.json() == {"detail": "idempotency_key_reuse"}
    assert versions(engine, sid) == [1]


def test_the_same_key_for_another_supplier_is_refused(client, engine):
    sid = seed(engine)
    with engine.begin() as c:
        other_id = add_supplier(c, 2, "Proveedor Sintético B")
    put(client, sid, key="key-4")
    reused = put(client, other_id, key="key-4")
    assert reused.status_code == 422 and reused.json() == {"detail": "idempotency_key_reuse"}
    assert versions(engine, other_id) == []


def test_malformed_keys_are_refused(client, engine):
    sid = seed(engine)
    for bad in ("x" * 121, "   "):
        r = put(client, sid, key=bad)
        assert r.status_code == 422 and r.json() == {"detail": "invalid_idempotency_key"}, bad
    assert versions(engine, sid) == []


def test_a_refused_save_is_not_remembered_so_the_key_can_be_used_again(client, engine):
    sid = seed(engine)
    invalid = put(client, sid, {**BODY, "min_order_value": "-1"}, key="key-5")
    assert invalid.status_code == 422 and invalid.json() == {"detail": "terms_negative_amount"}
    ok = put(client, sid, key="key-5")
    assert ok.status_code == 200 and ok.json() == {"version": 1}


def test_without_a_key_behaviour_is_unchanged(client, engine):
    sid = seed(engine)
    put(client, sid)
    assert put(client, sid, {**BODY, "lead_time_days": 4}, etag=1).json() == {"version": 2}
    assert put(client, sid, {**BODY, "lead_time_days": 4}, etag=2).json() == {"version": 3}      # identical content, new version: no hidden dedupe
    with engine.begin() as c:
        assert c.execute(select(func.count()).select_from(terms_idempotency)).scalar() == 0


def test_the_remembered_key_records_who_and_the_resulting_version(client, engine):
    sid = seed(engine)
    put(client, sid, key="key-6")
    with engine.begin() as c:
        row = c.execute(select(terms_idempotency)).one()
    assert (row.scope, row.key, row.result_version, row.actor) == ("supplier_terms", "key-6", 1, "user-buyer") and len(row.request_hash) == 64


def test_product_overrides_are_retry_safe_too(client, engine):
    sid = seed(engine)
    first = put_override(client, sid, key="ov-1")
    assert first.status_code == 200 and first.json() == {"version": 1}
    again = put_override(client, sid, key="ov-1")
    assert again.json() == {"version": 1} and again.headers["idempotent-replay"] == "true"
    reused = put_override(client, sid, {**OVERRIDE, "lead_time_days": 7}, key="ov-1")
    assert reused.status_code == 422 and reused.json() == {"detail": "idempotency_key_reuse"}
    assert put_override(client, sid, key="   ").json() == {"detail": "invalid_idempotency_key"}


def test_a_supplier_key_and_an_override_key_do_not_collide(client, engine):
    sid = seed(engine)
    assert put(client, sid, key="shared").json() == {"version": 1}
    assert put_override(client, sid, key="shared").json() == {"version": 1}                  # different scope, own record
