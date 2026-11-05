import io
import json
import logging as stdlog
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import jwt
import pytest
from hypothesis import given
from hypothesis import strategies as st
from mmi_common import auth, bus, outbox
from mmi_common import logging as mlog
from mmi_common.money import Money, to_decimal
from mmi_common.time import parse_siweb_timestamp, set_correlation_id
from sqlalchemy import MetaData, create_engine, event, select

# ---------- money ----------


def test_float_is_rejected():
    with pytest.raises(TypeError):
        Money(1.1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        to_decimal(0.1)  # type: ignore[arg-type]


def test_fractional_cents_from_siweb():
    assert Money.from_cents("1234.5").amount == Decimal("12.345")
    assert Money.from_cents("1234.5").to_cents() == 1235  # half-up


def test_currency_mismatch_and_dto():
    with pytest.raises(ValueError):
        Money.parse("1", "EUR") + Money.parse("1", "USD")
    assert Money.parse("12.34567").to_dto() == {"amount": "12.3457", "currency": "EUR"}


@given(st.decimals(min_value=0, max_value=10_000, places=4), st.decimals(min_value=0, max_value=10_000, places=4))
def test_addition_is_exact(a, b):
    assert (Money(a) + Money(b)).amount == a + b


# ---------- time ----------


def test_naive_timestamp_assumed_madrid_summer():
    p = parse_siweb_timestamp("2026-07-01T10:00:00")
    assert p.utc == datetime(2026, 7, 1, 8, 0, tzinfo=UTC) and p.assumed_tz == "Europe/Madrid" and not p.ambiguous
    assert p.raw == "2026-07-01T10:00:00"


def test_offset_timestamp_kept_and_dst_overlap_flagged():
    assert parse_siweb_timestamp("2026-07-01T10:00:00+02:00").assumed_tz is None
    assert parse_siweb_timestamp("2026-10-25T02:30:00").ambiguous  # clocks go back
    assert parse_siweb_timestamp("2026-03-29T02:30:00").ambiguous  # clocks go forward (gap)


# ---------- bus ----------


def _envelope(type_="siweb.cost.write_completed.v1", occurred=None, payload=b"{}"):
    return bus.new_envelope(type_, "res-1", payload, "blob://x", str(uuid.uuid4()), occurred_at=occurred)


def test_valid_envelope_passes_and_checksum_checked():
    env = _envelope()
    bus.validate_envelope(env)
    bus.verify_payload(env, b"{}")
    with pytest.raises(bus.MessageRejected):
        bus.verify_payload(env, b"tampered")


def test_unknown_type_and_bad_schema_rejected():
    with pytest.raises(bus.MessageRejected):
        bus.validate_envelope({**_envelope(), "type": "evil.event.v1"})
    bad = _envelope()
    bad["payload_ref"]["sha256"] = "xyz"
    with pytest.raises(bus.MessageRejected):
        bus.validate_envelope(bad)
    extra = {**_envelope(), "unexpected": 1}
    with pytest.raises(bus.MessageRejected):
        bus.validate_envelope(extra)


def test_type_mismatch_between_schema_and_envelope_is_impossible():
    env = _envelope("forecast.completed.v1")
    bus.validate_envelope(env)


def test_freshness_windows():
    old = datetime.now(UTC) - timedelta(hours=2)
    bus.validate_envelope(_envelope("forecast.completed.v1", occurred=old))  # 24 h window
    with pytest.raises(bus.MessageRejected):  # 1 h window for write requests
        bus.validate_envelope(_envelope("procurement.cost.write_requested.v1", occurred=old))


def test_poison_after_delivery_limit():
    b = bus.InMemoryBus(max_deliveries=2)
    b.send("q", _envelope())
    for _ in range(2):
        (m,) = b.receive("q")
        b.abandon("q", m.receipt)
    assert b.depth("q") == 0 and b.depth("q" + bus.POISON_SUFFIX) == 1


def test_complete_removes_and_inflight_not_redelivered():
    b = bus.InMemoryBus()
    b.send("q", _envelope())
    (m,) = b.receive("q")
    assert b.receive("q") == []
    b.complete("q", m.receipt)
    assert b.depth("q") == 0


# ---------- outbox / inbox ----------


def sqlite_engine():
    """pysqlite needs explicit BEGIN for savepoints/rollback to behave like PostgreSQL."""
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _connect(dbapi_conn, _):
        dbapi_conn.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin(conn):
        conn.exec_driver_sql("BEGIN")

    return engine


def test_relay_fans_out_once_per_queue_and_inbox_dedups():
    engine = sqlite_engine()
    md = MetaData()
    ob, ib = outbox.outbox_table(md), outbox.inbox_table(md)
    md.create_all(engine)
    b = bus.InMemoryBus()
    env = _envelope("inventory.snapshot.created.v1")
    subs = {"inventory.snapshot.created.v1": ["forecast", "procurement"]}
    with engine.begin() as conn:
        outbox.enqueue(conn, ob, env)
    with engine.begin() as conn:
        assert outbox.relay_once(conn, ob, b, subs) == 1
        assert outbox.relay_once(conn, ob, b, subs) == 0  # already sent
        assert conn.execute(select(ob.c.status)).scalar_one() == "sent"
    assert b.depth("forecast") == 1 and b.depth("procurement") == 1
    with engine.begin() as conn:
        assert outbox.register_once(conn, ib, env["event_id"], env["type"]) is True
        assert outbox.register_once(conn, ib, env["event_id"], env["type"]) is False


def test_failed_consumer_transaction_rolls_back_registration():
    engine = sqlite_engine()
    md = MetaData()
    ib = outbox.inbox_table(md)
    md.create_all(engine)
    eid = str(uuid.uuid4())
    with pytest.raises(RuntimeError), engine.begin() as conn:
        assert outbox.register_once(conn, ib, eid, "t")
        raise RuntimeError("handler failed")
    with engine.begin() as conn:
        assert outbox.register_once(conn, ib, eid, "t") is True


# ---------- logging ----------


def test_logging_redacts_and_carries_correlation_id():
    stream = io.StringIO()
    mlog.configure_logging(stream=stream)
    cid = set_correlation_id()
    stdlog.getLogger("t").info(
        "call with Bearer abc.def.ghi by someone@example.com",
        extra={"fields": {"authorization": "Bearer zzz", "supplier_cif": "X1", "qty": 3, "nested": {"notes": "free text"}}},
    )
    line = json.loads(stream.getvalue())
    assert line["correlation_id"] == cid and line["qty"] == 3
    assert "abc.def.ghi" not in stream.getvalue() and "someone@example.com" not in stream.getvalue()
    assert line["authorization"] == line["supplier_cif"] == line["nested"]["notes"] == "[REDACTED]"


# ---------- auth ----------


def test_token_validation_paths():
    issuer = auth.DevIssuer()
    v = auth.TokenValidator(issuer.issuer, "api://procurement", issuer.public_key)
    ok = issuer.issue("svc-bff", "api://procurement", roles=["reader"])
    p = v.validate(ok, required_roles=["reader"])
    assert p.subject == "svc-bff" and p.mfa_fresh()
    with pytest.raises(auth.AuthError) as e:
        v.validate(issuer.issue("x", "api://other"))
    assert e.value.status == 401
    with pytest.raises(auth.AuthError) as e:
        v.validate(ok, required_roles=["writer"])
    assert e.value.status == 403
    expired = issuer.issue("x", "api://procurement", now=datetime.now(UTC) - timedelta(hours=2))
    with pytest.raises(auth.AuthError):
        v.validate(expired)
    other = auth.DevIssuer()
    with pytest.raises(auth.AuthError):  # signed by a different key
        v.validate(other.issue("x", "api://procurement"))
    with pytest.raises(auth.AuthError):  # alg=none forgery
        v.validate(jwt.encode({"sub": "x"}, key="", algorithm="none"))


def test_stale_mfa_detected():
    issuer = auth.DevIssuer()
    v = auth.TokenValidator(issuer.issuer, "a", issuer.public_key)
    t = issuer.issue("u", "a", auth_time=datetime.now(UTC) - timedelta(minutes=30))
    assert not v.validate(t).mfa_fresh()
    assert auth.bearer_token("Bearer abc") == "abc"
    with pytest.raises(auth.AuthError):
        auth.bearer_token(None)
