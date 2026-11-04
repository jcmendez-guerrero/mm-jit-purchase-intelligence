"""T029: every method/path/host/redirect outside the reader allowlist is refused before sending."""

import httpx
import pytest
from allowlist.allowlist import Allowlist, AllowlistViolation
from client.reader import ReaderClient
from client.token import StaticTokenProvider
from ratelimit.bucket import TokenBucket

HOST = "siweb.example.test"
ALLOWED = [
    "/api/public/inventory/warehouses", "/api/public/inventory/products", "/api/public/inventory/products/5",
    "/api/public/inventory/products/5/suppliers", "/api/public/inventory/variants", "/api/public/inventory/variants/5",
    "/api/public/inventory/variants/5/stock", "/api/public/inventory/variants/5/lots", "/api/public/inventory/movements",
    "/api/public/inventory/variants/5/movements", "/api/public/purchases", "/api/public/purchases/9",
]


@pytest.mark.parametrize("path", ALLOWED)
def test_allowed_reads_pass(path):
    Allowlist(HOST).check("GET", f"https://{HOST}{path}?page=1&limit=200")


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
def test_every_non_get_method_is_refused_even_on_allowed_paths(method):
    for path in ALLOWED:
        with pytest.raises(AllowlistViolation) as e:
            Allowlist(HOST).check(method, f"https://{HOST}{path}")
        assert e.value.reason == "method_not_allowed"


def test_supplier_cost_put_is_not_reachable_from_the_reader():
    with pytest.raises(AllowlistViolation):
        Allowlist(HOST).check("PUT", f"https://{HOST}/api/public/inventory/products/5/suppliers/7")


@pytest.mark.parametrize("path", [
    "/api/public/inventory/products/5/suppliers/7", "/api/public/inventory/adjustments", "/api/public/inventory/transfers",
    "/api/public/invoices", "/api/public/tickets", "/api/public/contacts", "/api/public/inventory/products/abc",
    "/api/public/inventory/products/5/../6", "/api/public/inventory/products/%2e%2e/6", "/api/public//inventory/products",
    "/api/private/inventory/products", "/inventory/products", "/",
])
def test_other_paths_are_refused(path):
    with pytest.raises(AllowlistViolation):
        Allowlist(HOST).check("GET", f"https://{HOST}{path}")


@pytest.mark.parametrize("url", [
    "https://evil.example.test/api/public/inventory/products", f"https://{HOST}.evil.test/api/public/inventory/products",
    f"https://user:pw@{HOST}/api/public/inventory/products", f"https://{HOST}@evil.test/api/public/inventory/products",
    f"http://{HOST}/api/public/inventory/products",
])
def test_other_hosts_schemes_and_credentials_are_refused(url):
    with pytest.raises(AllowlistViolation):
        Allowlist(HOST).check("GET", url)


def test_refusals_are_recorded_without_query_strings():
    a = Allowlist(HOST)
    with pytest.raises(AllowlistViolation):
        a.check("GET", f"https://{HOST}/api/public/tickets?secret=1")
    assert a.refusals and "secret" not in str(a.refusals)


def _client(handler):
    return ReaderClient(
        http=httpx.Client(transport=httpx.MockTransport(handler)), base_url=f"https://{HOST}", allowlist=Allowlist(HOST),
        bucket=TokenBucket(), tokens=StaticTokenProvider("t"), sleep=lambda s: None,
    )


def test_refusal_happens_before_any_request_is_sent():
    sent = []
    c = _client(lambda r: sent.append(r) or httpx.Response(200, json={}))
    with pytest.raises(AllowlistViolation):
        c.get("/api/public/tickets")
    assert sent == [] and c.requests_made == 0 and c.bucket.used == 0


def test_redirect_to_another_host_is_refused_not_followed():
    seen = []

    def handler(r):
        seen.append(str(r.url))
        return httpx.Response(302, headers={"location": "https://evil.example.test/steal"})

    c = _client(handler)
    with pytest.raises(AllowlistViolation):
        c.get("/api/public/inventory/products")
    assert seen == [f"https://{HOST}/api/public/inventory/products"]  # the redirect target was never requested
