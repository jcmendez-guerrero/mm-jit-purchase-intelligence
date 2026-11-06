"""T045 (behavioural): saving and resolving terms never opens a network connection."""

import socket

import httpx
from conftest import NOW, add_supplier
from terms.overrides import OverrideTerms, save_override
from terms.resolve import resolve_effective
from terms.service import Terms, save_terms


def test_saving_and_resolving_terms_makes_no_http_or_socket_call(conn, monkeypatch):
    def tripwire(*a, **k):
        raise AssertionError("terms must stay local: a network call was attempted")

    monkeypatch.setattr(httpx.Client, "send", tripwire)
    monkeypatch.setattr(httpx.AsyncClient, "send", tripwire)
    monkeypatch.setattr(socket, "create_connection", tripwire)
    sid = add_supplier(conn, 1, "Proveedor Sintético A")
    save_terms(conn, sid, Terms(lead_time_days=3, preferred=True), "buyer-1", NOW)
    save_override(conn, 9001, sid, OverrideTerms(pack_multiple=6), "buyer-1", NOW)
    assert resolve_effective(conn, sid, 9001, NOW).pack_multiple == 6
