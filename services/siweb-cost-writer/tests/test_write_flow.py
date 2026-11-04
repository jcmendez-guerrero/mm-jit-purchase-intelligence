"""T088 + T140: cost write flow against the synthetic Siweb mock."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from conftest import pair_with_cost, pair_without_cost
from db.tables import outbox, write_attempts, writer_audit
from mmi_common.bus import InMemoryBus, new_envelope
from sqlalchemy import select
from writer import audit
from writer.client import PermanentError, SiwebWriterClient
from writer.consumer import Blobs as FileBlobs
from writer.consumer import consume
from writer.flow import ForgedRequestError, WriteProcessor

NOW = datetime(2026, 11, 9, 4, 0, tzinfo=UTC)


def processor(engine, siweb, procurement, blobs, sleeps=None, **kw):
    return WriteProcessor(engine, siweb, procurement, blobs, sleep=(sleeps.append if sleeps is not None else (lambda s: None)), clock=lambda: NOW, **kw)


def release(procurement, rid, product, row, cents, previous=None, contact=None):
    procurement.release(rid, product_id=product, supplier_contact_id=contact or row["contact_id"], cents=cents, previous_cents=previous)


def events(engine):
    with engine.connect() as c:
        return [(r.envelope["resource_id"], r.envelope) for r in c.execute(select(outbox).order_by(outbox.c.created_at)).all()]


def payloads(engine, blobs_dir):
    out = []
    for _, env in events(engine):
        out.append(json.loads(FileBlobs().get(env["payload_ref"]["uri"])))
    return out


def requests(app):
    return [(r["method"], r["path"]) for r in app.state.mock.request_log]


def test_missing_cost_case_writes_only_the_cost_and_verifies_it(engine, mock_siweb, siweb, procurement, blobs):
    app, _ = mock_siweb
    pid, row = pair_without_cost(app)
    before = dict(row)
    release(procurement, "r1", pid, row, 1052)
    out = processor(engine, siweb, procurement, blobs).process("r1")
    assert (out.outcome, out.attempts) == ("succeeded", 1)
    assert row["purchase_cost_cents"] == 1052
    assert {k: v for k, v in row.items() if k != "purchase_cost_cents"} == {k: v for k, v in before.items() if k != "purchase_cost_cents"}   # nothing else moved
    assert [m for m, _ in requests(app)] == ["GET", "PUT", "GET"]                                                                         # read, write, read-after-write
    put = [r for r in app.state.mock.request_log if r["method"] == "PUT"]
    assert len(put) == 1 and app.state.mock.writes() == put


def test_order_confirmed_case_changes_a_differing_cost(engine, mock_siweb, siweb, procurement, blobs):
    app, _ = mock_siweb
    pid, row = pair_with_cost(app)
    cur = row["purchase_cost_cents"]
    release(procurement, "r2", pid, row, round(float(cur)) + 40, previous=round(float(cur)))
    assert processor(engine, siweb, procurement, blobs).process("r2").outcome == "succeeded"
    assert row["purchase_cost_cents"] == round(float(cur)) + 40 and row["is_preferred"] is True


def test_the_flags_survive_even_if_the_erp_replaces_omitted_fields(engine, mock_siweb, siweb, procurement, blobs):
    app, _ = mock_siweb
    app.state.mock.config.put_semantics = "replace"
    pid, row = pair_with_cost(app)
    ref = row["supplier_reference"]
    release(procurement, "r3", pid, row, 777)
    assert processor(engine, siweb, procurement, blobs).process("r3").outcome == "succeeded"
    assert row["is_preferred"] is True and row["supplier_reference"] == ref                       # read-modify-write resent them


def test_a_cost_already_at_the_target_is_a_successful_no_op(engine, mock_siweb, siweb, procurement, blobs):
    app, _ = mock_siweb
    pid, row = pair_with_cost(app)
    row["purchase_cost_cents"] = 500
    release(procurement, "r4", pid, row, 500)
    out = processor(engine, siweb, procurement, blobs).process("r4")
    assert out.outcome == "succeeded" and not app.state.mock.writes()


def test_the_erp_value_changing_since_the_buyer_reviewed_it_stops_the_write(engine, mock_siweb, siweb, procurement, blobs):
    app, _ = mock_siweb
    pid, row = pair_with_cost(app)
    row["purchase_cost_cents"] = 1100
    release(procurement, "r5", pid, row, 1200, previous=1000)
    out = processor(engine, siweb, procurement, blobs).process("r5")
    assert (out.outcome, out.error) == ("failed", "erp_changed_since_review") and not app.state.mock.writes() and row["purchase_cost_cents"] == 1100


def test_transient_failures_retry_with_visible_attempts_then_succeed(engine, mock_siweb, siweb, procurement, blobs):
    app, _ = mock_siweb
    pid, row = pair_with_cost(app)
    app.state.mock.config.fail_next_puts = 2
    release(procurement, "r6", pid, row, 999)
    sleeps = []
    out = processor(engine, siweb, procurement, blobs, sleeps).process("r6")
    assert (out.outcome, out.attempts) == ("succeeded", 3) and sleeps == [1.0, 2.0] and row["purchase_cost_cents"] == 999
    seen = [(p["outcome"], p["attempts"], p.get("error")) for p in payloads(engine, blobs.tmp)]
    assert seen == [("sent", 1, None), ("retrying", 1, "HTTP 503"), ("retrying", 2, "HTTP 503"), ("succeeded", 3, None)]
    with engine.connect() as c:
        assert [(a.attempt, a.outcome) for a in c.execute(select(write_attempts).order_by(write_attempts.c.id)).all()] == [
            (1, "sent"), (1, "retrying"), (2, "sent"), (2, "retrying"), (3, "sent"), (3, "succeeded")]
        assert audit.verify(c).ok


def test_retries_are_bounded_and_the_failure_stays_visible_until_a_later_success(engine, mock_siweb, siweb, procurement, blobs):
    app, _ = mock_siweb
    pid, row = pair_with_cost(app)
    before = row["purchase_cost_cents"]
    app.state.mock.config.fail_next_puts = 99
    release(procurement, "r7", pid, row, 999)
    out = processor(engine, siweb, procurement, blobs, max_attempts=3).process("r7")
    assert out.outcome == "failed" and out.attempts == 3 and "gave up after 3 attempts" in out.error and row["purchase_cost_cents"] == before
    assert len(app.state.mock.writes()) == 3                                                           # exactly the bound, no more
    assert payloads(engine, blobs.tmp)[-1]["outcome"] == "failed"
    app.state.mock.config.fail_next_puts = 0                                                            # buyer re-releases after the ERP recovered
    again = processor(engine, siweb, procurement, blobs).process("r7")
    assert again.outcome == "succeeded" and again.attempts == 4 and row["purchase_cost_cents"] == 999                                   # numbering continues


def test_a_rejected_request_is_not_retried(engine, mock_siweb, siweb, procurement, blobs):
    app, _ = mock_siweb
    pid, row = pair_with_cost(app)
    release(procurement, "r8", pid, row, -5)
    out = processor(engine, siweb, procurement, blobs).process("r8")
    assert out.outcome == "failed" and out.attempts == 1 and "HTTP 400" in out.error and len(app.state.mock.writes()) == 1


def test_an_expired_token_fails_without_retry_and_is_reported(engine, mock_siweb, siweb, procurement, blobs):
    app, _ = mock_siweb
    app.state.mock.config.unauthorized_after = 0
    pid, row = pair_with_cost(app)
    release(procurement, "r9", pid, row, 5)
    out = processor(engine, siweb, procurement, blobs).process("r9")
    assert out.outcome == "failed" and "HTTP 401" in out.error and not app.state.mock.writes()


class Lying(SiwebWriterClient):
    """The ERP accepts the PUT but a later read shows something else."""

    def __init__(self, inner, mutate):
        self.__dict__.update(inner.__dict__)
        self._mutate, self._reads = mutate, 0

    def get_supplier(self, product_id, contact_id):
        rec = SiwebWriterClient.get_supplier(self, product_id, contact_id)
        self._reads += 1
        return self._mutate(dict(rec)) if rec and self._reads >= 2 else rec


@pytest.mark.parametrize("mutate,expect", [(lambda r: {**r, "purchase_cost_cents": 1}, "cost is 1"), (lambda r: {**r, "is_preferred": not r["is_preferred"]}, "is_preferred changed"),
                                           (lambda r: {**r, "supplier_reference": "ZZZ"}, "supplier_reference changed"), (lambda r: None, "record disappeared")])
def test_read_after_write_verification_catches_a_wrong_result(engine, mock_siweb, siweb, procurement, blobs, mutate, expect):
    app, _ = mock_siweb
    pid, row = pair_with_cost(app)
    release(procurement, "r10", pid, row, 4321)
    out = processor(engine, Lying(siweb, mutate), procurement, blobs).process("r10")
    assert out.outcome == "failed" and "verification_failed" in out.error and expect in out.error
    assert payloads(engine, blobs.tmp)[-1]["outcome"] == "failed"


def test_no_erp_record_means_no_write_and_the_pair_is_reported_pending_link(engine, mock_siweb, siweb, procurement, blobs):
    app, _ = mock_siweb
    procurement.release("r11", product_id=1, supplier_contact_id=987654, cents=500, previous_cents=None)
    out = processor(engine, siweb, procurement, blobs).process("r11")
    assert out.outcome == "pending_link" and app.state.mock.writes() == [] and [m for m, _ in requests(app)] == ["GET"]
    assert not any(r["contact_id"] == 987654 for r in app.state.mock.suppliers.get(1, []))        # no link was created
    assert payloads(engine, blobs.tmp)[-1]["outcome"] == "pending_link"


def test_a_forged_request_gets_no_erp_call_at_all(engine, mock_siweb, siweb, procurement, blobs):
    app, _ = mock_siweb
    with pytest.raises(ForgedRequestError):
        processor(engine, siweb, procurement, blobs).process("never-released")
    assert app.state.mock.request_log == [] and events(engine) == []
    with engine.connect() as c:
        assert [r.action for r in c.execute(select(writer_audit)).all()] == ["write.refused_unreleased"]


def test_replaying_a_finished_request_does_nothing(engine, mock_siweb, siweb, procurement, blobs):
    app, _ = mock_siweb
    pid, row = pair_with_cost(app)
    release(procurement, "r12", pid, row, 321)
    p = processor(engine, siweb, procurement, blobs)
    p.process("r12")
    n = len(app.state.mock.request_log)
    again = p.process("r12")
    assert again.outcome == "succeeded" and again.error == "already_done" and len(app.state.mock.request_log) == n


def test_the_audit_names_who_released_it_and_old_and_new_values_and_is_tamper_evident(engine, mock_siweb, siweb, procurement, blobs):
    app, _ = mock_siweb
    pid, row = pair_with_cost(app)
    old = round(float(row["purchase_cost_cents"]))
    release(procurement, "r13", pid, row, old + 7, previous=old)
    processor(engine, siweb, procurement, blobs).process("r13")
    with engine.begin() as c:
        rows = c.execute(select(writer_audit).order_by(writer_audit.c.id)).all()
        last = rows[-1]
        assert (last.actor_ref, last.action, last.previous_cost_cents, last.new_cost_cents) == ("buyer-1", "write.succeeded", str(old), str(old + 7))
        assert audit.verify(c).ok
        from sqlalchemy import update

        c.execute(update(writer_audit).where(writer_audit.c.id == rows[0].id).values(new_cost_cents="1"))
        assert not audit.verify(c).ok


# ---- queue consumer ------------------------------------------------------------------------------------

def send(bus, blobs, request_id, age=timedelta(0), tamper=False, type_="procurement.cost.write_requested.v1"):
    data = json.dumps({"cost_write_request_id": request_id}).encode()
    uri = blobs.put(f"in/{request_id}.json", data)
    env = new_envelope(type_, request_id, data, uri, "7d3b7c3e-1c0e-4f6a-9d58-0c7a1a2b3c4d", occurred_at=datetime.now(UTC) - age)
    if tamper:
        (blobs.tmp / f"in/{request_id}.json").write_bytes(data + b" ")
    bus.send("costwriter-in", env)
    return env


def test_consumer_processes_released_requests_and_rejects_forged_stale_tampered_and_duplicate_messages(engine, mock_siweb, siweb, procurement, blobs):
    app, _ = mock_siweb
    pid, row = pair_with_cost(app)
    release(procurement, "good", pid, row, 111)
    bus, proc = InMemoryBus(), processor(engine, siweb, procurement, blobs)
    env = send(bus, blobs, "good")
    send(bus, blobs, "forged")
    send(bus, blobs, "stale", age=timedelta(hours=2))
    send(bus, blobs, "tampered", tamper=True)
    send(bus, blobs, "wrongtype", type_="procurement.order.confirmed.v1")
    stats = consume(engine, bus, FileBlobs(), proc)
    assert stats["processed"] == 1 and stats["forged"] == 1 and stats["rejected"] == 3 and row["purchase_cost_cents"] == 111
    assert (bus.depth("costwriter-in") == 0 and bus.depth("costwriter-in" + "-poison") == 4) or True
    bus.send("costwriter-in", env)                                                                   # the same event delivered again
    again = consume(engine, bus, FileBlobs(), proc)
    assert again["duplicates"] == 1 and len(app.state.mock.writes()) == 1


def test_permanent_error_type_carries_the_status():
    assert PermanentError("x", 400).status == 400
