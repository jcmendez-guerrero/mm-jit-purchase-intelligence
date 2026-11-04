"""T087: the writer's allowlist permits only the supplier-cost PUT (and the supplier list read it needs) and refuses everything else."""

import httpx
import pytest
from writer.allowlist import AllowlistViolation, WriterAllowlist
from writer.client import SiwebWriterClient, StaticToken

HOST = "siweb.example.test"
PUT = f"https://{HOST}/api/public/inventory/products/5/suppliers/7"
LIST = f"https://{HOST}/api/public/inventory/products/5/suppliers"


def test_the_two_permitted_requests_pass():
    a = WriterAllowlist(HOST)
    a.check("PUT", PUT)
    a.check("GET", LIST + "?x=1")
    assert a.refusals == []


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE", "HEAD", "OPTIONS"])
def test_every_other_method_is_refused_on_the_permitted_paths(method):
    for url in (PUT, LIST):
        with pytest.raises(AllowlistViolation) as e:
            WriterAllowlist(HOST).check(method, url)
        assert e.value.reason == "method_not_allowed"


@pytest.mark.parametrize("method,path", [
    ("PUT", "/api/public/inventory/variants/5"), ("PUT", "/api/public/inventory/variants/5/price"), ("PUT", "/api/public/inventory/adjustments"),
    ("PUT", "/api/public/inventory/transfers/1"), ("PUT", "/api/public/purchases/1"), ("PUT", "/api/public/invoices/1"), ("PUT", "/api/public/tickets/1"),
    ("PUT", "/api/public/contacts/1"), ("PUT", "/api/public/inventory/products/5"), ("PUT", "/api/public/inventory/products/5/suppliers"),
    ("PUT", "/api/public/inventory/products/5/suppliers/7/extra"), ("PUT", "/api/public/inventory/products/x/suppliers/7"), ("PUT", "/api/public/inventory/products/5/suppliers/x"),
    ("GET", "/api/public/inventory/movements"), ("GET", "/api/public/inventory/products"), ("GET", "/api/public/inventory/products/5"),
    ("GET", "/api/public/inventory/products/5/suppliers/7"), ("GET", "/api/public/purchases"), ("GET", "/"),
    ("PUT", "/api/public/inventory/products/5/../6/suppliers/7"), ("PUT", "/api/public/inventory/products/%2e%2e/suppliers/7"), ("PUT", "/api/public//inventory/products/5/suppliers/7"),
])
def test_every_other_path_is_refused(method, path):
    with pytest.raises(AllowlistViolation):
        WriterAllowlist(HOST).check(method, f"https://{HOST}{path}")


@pytest.mark.parametrize("url", [
    PUT.replace(HOST, "evil.example.test"), PUT.replace(HOST, HOST + ".evil.test"), PUT.replace("https://", "https://user:pw@"), PUT.replace("https://", "http://"),
    PUT.replace(HOST, f"{HOST}@evil.test"),
])
def test_other_hosts_schemes_and_credentials_are_refused(url):
    with pytest.raises(AllowlistViolation):
        WriterAllowlist(HOST).check("PUT", url)


def test_refusal_is_recorded_for_the_alert_without_the_url():
    a = WriterAllowlist(HOST)
    with pytest.raises(AllowlistViolation):
        a.check("DELETE", PUT + "?token=secret")
    assert a.refusals == [("method_not_allowed", "DELETE")] and "secret" not in str(a.refusals)


def client(handler):
    return SiwebWriterClient(httpx.Client(transport=httpx.MockTransport(handler)), f"https://{HOST}", WriterAllowlist(HOST), StaticToken("t"))


def test_a_refused_request_is_never_sent():
    sent = []
    c = client(lambda r: sent.append(r) or httpx.Response(200, json={"data": []}))
    for call in (lambda: c._send("DELETE", "/api/public/inventory/products/5/suppliers/7"), lambda: c._send("PUT", "/api/public/purchases/1", {}),
                 lambda: c._send("GET", "/api/public/inventory/movements")):
        with pytest.raises(AllowlistViolation):
            call()
    assert sent == [] and c.requests_made == 0


def test_a_redirect_is_never_followed():
    seen = []

    def handler(r):
        seen.append(str(r.url))
        return httpx.Response(307, headers={"location": "https://evil.example.test/steal"})

    c = client(handler)
    with pytest.raises(AllowlistViolation):
        c.put_supplier(5, 7, {"purchase_cost_cents": 1})
    assert seen == [PUT]
